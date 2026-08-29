#!/usr/bin/env python3
"""Dependency-free integrity checks for the static MNCS Atlas site."""

from __future__ import annotations

import json
import hashlib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CANONICAL_URL = "https://epi13.github.io/mncs-atlas/"

MIRROR_PATHS = (
    "index.html",
    "experimental-atlas.html",
    "404.html",
    "atlas.json",
    "robots.txt",
    "sitemap.xml",
    "assets/styles.css",
    "assets/app.js",
    "assets/atlas-wasm.css",
    "assets/atlas-wasm.js",
    "assets/atlas-json-scan.wasm",
    "assets/atlas-json-projection.wasm",
    "assets/atlas-wasm-manifest.json",
    "assets/journal.css",
    "schema/atlas.schema.json",
)
MIRROR_TREES = ("journal",)
MIRRORS = {SITE / relative: ROOT / relative for relative in MIRROR_PATHS}
for _tree in MIRROR_TREES:
    _source_root = SITE / _tree
    if _source_root.is_dir():
        for _source in _source_root.rglob("*"):
            if _source.is_file():
                MIRRORS[_source] = ROOT / _source.relative_to(SITE)


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.add(element_id)
        for attr in ("href", "src"):
            value = values.get(attr)
            if value:
                self.refs.append((attr, value))


def load_html(path: Path) -> LinkCollector:
    parser = LinkCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")
        return None


def check_atlas(atlas: object, errors: list[str]) -> None:
    if not isinstance(atlas, dict):
        errors.append("site/atlas.json must contain a JSON object")
        return

    if atlas.get("non_normative") is not True:
        errors.append("site/atlas.json must explicitly declare non_normative=true")
    if atlas.get("authority") != "orientation-only":
        errors.append("site/atlas.json must explicitly declare authority=orientation-only")
    if not atlas.get("schema_version"):
        errors.append("site/atlas.json is missing schema_version")
    if atlas.get("canonical_human_guide") != CANONICAL_URL:
        errors.append("site/atlas.json canonical_human_guide does not match the Pages URL")

    maturity_model = atlas.get("maturity_model")
    if not isinstance(maturity_model, dict):
        errors.append("site/atlas.json must define maturity_model")
        maturity_levels: dict[str, object] = {}
    else:
        if maturity_model.get("semantics") != "descriptive-not-ranked":
            errors.append("site/atlas.json maturity_model must declare semantics=descriptive-not-ranked")
        maturity_levels = maturity_model.get("levels")
        if not isinstance(maturity_levels, dict) or not maturity_levels:
            errors.append("site/atlas.json maturity_model.levels must be a non-empty object")
            maturity_levels = {}
        else:
            for maturity_id, maturity in maturity_levels.items():
                if not isinstance(maturity, dict) or not maturity.get("meaning") or not maturity.get("dependency_policy"):
                    errors.append(f"site/atlas.json maturity level {maturity_id!r} must define meaning and dependency_policy")

    consumer_contract = atlas.get("consumer_contract")
    if not isinstance(consumer_contract, dict):
        errors.append("site/atlas.json must define consumer_contract")
    else:
        if not consumer_contract.get("version") or not consumer_contract.get("purpose"):
            errors.append("site/atlas.json consumer_contract must define version and purpose")
        for field in ("resolution_order", "rules"):
            values = consumer_contract.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
                errors.append(f"site/atlas.json consumer_contract.{field} must be a non-empty string list")

    projects = atlas.get("projects")
    operator_components = atlas.get("operator_components")
    relationships = atlas.get("relationships")
    entry_points = atlas.get("entry_points")

    if not isinstance(projects, list) or not projects:
        errors.append("site/atlas.json must contain a non-empty projects list")
        projects = []
    if not isinstance(operator_components, list):
        errors.append("site/atlas.json operator_components must be a list")
        operator_components = []
    if not isinstance(relationships, list):
        errors.append("site/atlas.json relationships must be a list")
        relationships = []
    if not isinstance(entry_points, list):
        errors.append("site/atlas.json entry_points must be a list")
        entry_points = []

    known_ids: set[str] = set()
    for collection_name, collection in (("projects", projects), ("operator_components", operator_components)):
        for index, component in enumerate(collection):
            if not isinstance(component, dict):
                errors.append(f"site/atlas.json {collection_name}[{index}] must be an object")
                continue
            component_id = component.get("id")
            if not isinstance(component_id, str) or not component_id:
                errors.append(f"site/atlas.json {collection_name}[{index}] is missing a stable id")
                continue
            if component_id in known_ids:
                errors.append(f"site/atlas.json duplicate component id: {component_id}")
            known_ids.add(component_id)
            if not component.get("name") or not component.get("role") or not component.get("responsibility"):
                errors.append(f"site/atlas.json component {component_id} is missing name, role, or responsibility")
            if not component.get("authority_class"):
                errors.append(f"site/atlas.json component {component_id} is missing authority_class")
            if collection_name == "projects":
                maturity = component.get("maturity")
                if maturity not in maturity_levels:
                    errors.append(f"site/atlas.json project {component_id} uses undefined maturity level: {maturity}")

    relation_keys: set[tuple[str, str, str]] = set()
    for index, relation in enumerate(relationships):
        if not isinstance(relation, dict):
            errors.append(f"site/atlas.json relationships[{index}] must be an object")
            continue
        source = relation.get("from")
        target = relation.get("to")
        kind = relation.get("kind")
        if source not in known_ids:
            errors.append(f"site/atlas.json relationship references unknown source: {source}")
        if target not in known_ids:
            errors.append(f"site/atlas.json relationship references unknown target: {target}")
        if source == target:
            errors.append(f"site/atlas.json relationship cannot self-reference: {source}")
        if not kind or not relation.get("description"):
            errors.append(f"site/atlas.json relationship {source}->{target} is missing kind or description")
        relation_key = (str(source), str(target), str(kind))
        if relation_key in relation_keys:
            errors.append(f"site/atlas.json duplicate relationship: {source}->{target} ({kind})")
        relation_keys.add(relation_key)

    for index, entry in enumerate(entry_points):
        if not isinstance(entry, dict):
            errors.append(f"site/atlas.json entry_points[{index}] must be an object")
            continue
        starts = entry.get("start_with")
        if not entry.get("goal") or not isinstance(starts, list) or not starts:
            errors.append(f"site/atlas.json entry_points[{index}] must define goal and non-empty start_with")
            continue
        unknown = [component_id for component_id in starts if component_id not in known_ids]
        if unknown:
            errors.append(
                f"site/atlas.json entry point {entry.get('goal')!r} references unknown component ids: {', '.join(unknown)}"
            )


def check_wasm_manifest(manifest: object, errors: list[str]) -> None:
    if not isinstance(manifest, dict):
        errors.append("site/assets/atlas-wasm-manifest.json must contain a JSON object")
        return
    if manifest.get("schema_version") != "0.2":
        errors.append("site/assets/atlas-wasm-manifest.json has an unsupported schema_version")
    if manifest.get("kind") != "mncs-atlas-wasm" or manifest.get("authority") != "orientation-only":
        errors.append("site/assets/atlas-wasm-manifest.json has contradictory identity metadata")

    lock_revision: object = None
    build = manifest.get("build")
    if not isinstance(build, dict):
        errors.append("WASM manifest is missing build provenance")
    else:
        lock_path = ROOT / "mncs/mncs-language.lock.json"
        lock = load_json(lock_path, errors) if lock_path.is_file() else None
        lock_revision = lock.get("revision") if isinstance(lock, dict) else None
        if not isinstance(lock_revision, str):
            errors.append("mncs/mncs-language.lock.json must declare a revision")
        if build.get("language_revision_lock") != lock_revision:
            errors.append("WASM manifest language revision does not match mncs-language.lock.json")
        if build.get("artifact_set") != [
            "atlas-json-scan",
            "atlas-json-projection",
            "atlas-model",
        ]:
            errors.append("WASM manifest build artifact_set is contradictory")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("WASM manifest is missing provenance")
    else:
        states = []
        for producer in ("atlas", "mncs_language"):
            value = provenance.get(producer)
            if not isinstance(value, dict) or not value.get("commit"):
                errors.append(f"WASM manifest is missing {producer} commit provenance")
                continue
            state = value.get("working_tree")
            states.append(state)
            if state not in {"clean", "dirty", "unknown"}:
                errors.append(f"WASM manifest has invalid {producer} working_tree state")
        library = provenance.get("standard_library")
        if not isinstance(library, dict) or not isinstance(library.get("sha256"), str) or len(library["sha256"]) != 64:
            errors.append("WASM manifest is missing standard-library source identity")
        reproducibility = provenance.get("reproducibility")
        if not isinstance(reproducibility, dict):
            errors.append("WASM manifest is missing reproducibility status")
        else:
            if len(states) != 2 or "unknown" in states:
                expected = "unknown"
            elif states == ["clean", "clean"]:
                expected = "reproducible"
            else:
                expected = "uncertain"
            if reproducibility.get("status") != expected:
                errors.append("WASM manifest reproducibility status contradicts producer tree state")

        language_revision = (
            provenance.get("mncs_language", {}).get("commit")
            if isinstance(provenance.get("mncs_language"), dict)
            else None
        )
        if isinstance(lock_revision, str) and language_revision != lock_revision:
            errors.append("WASM manifest mncs-language commit does not match the producer lock")

    artifacts = manifest.get("artifacts")
    expected_artifacts = {"atlas-json-scan", "atlas-json-projection", "atlas-model"}
    if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
        errors.append("WASM manifest artifact set is incomplete or contains unknown artifacts")
        return
    for name in sorted(expected_artifacts):
        value = artifacts[name]
        if not isinstance(value, dict):
            errors.append(f"WASM manifest entry {name} is not an object")
            continue
        relative = value.get("path")
        if relative != f"assets/{name}.wasm":
            errors.append(f"WASM manifest entry {name} has a contradictory path")
            continue
        artifact = SITE / relative
        if not artifact.is_file():
            errors.append(f"WASM manifest entry {name} points to a missing file")
            continue
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if value.get("sha256") != digest:
            errors.append(f"WASM manifest entry {name} has a stale SHA-256")
        if value.get("bytes") != artifact.stat().st_size:
            errors.append(f"WASM manifest entry {name} has a stale byte count")
        if not isinstance(value.get("source_sha256"), str) or len(value["source_sha256"]) != 64:
            errors.append(f"WASM manifest entry {name} is missing source SHA-256")
        if not isinstance(value.get("corpus_sha256"), str) or len(value["corpus_sha256"]) != 64:
            errors.append(f"WASM manifest entry {name} is missing corpus SHA-256")
        for field, digest_field in (("source", "source_sha256"), ("corpus", "corpus_sha256")):
            reference = value.get(field)
            if (
                not isinstance(reference, dict)
                or not isinstance(reference.get("repository"), str)
                or not isinstance(reference.get("path"), str)
                or not isinstance(reference.get("sha256"), str)
                or len(reference["sha256"]) != 64
            ):
                errors.append(f"WASM manifest entry {name} is missing {field} provenance")
            elif reference["sha256"] != value.get(digest_field):
                errors.append(f"WASM manifest entry {name} has contradictory {field} hashes")
            elif reference["repository"] == "mncs-atlas":
                referenced = (ROOT / reference["path"]).resolve()
                try:
                    referenced.relative_to(ROOT.resolve())
                except ValueError:
                    errors.append(f"WASM manifest entry {name} {field} escapes Atlas root")
                else:
                    if not referenced.is_file():
                        errors.append(f"WASM manifest entry {name} points to a missing {field} file")
                    elif hashlib.sha256(referenced.read_bytes()).hexdigest() != reference["sha256"]:
                        errors.append(f"WASM manifest entry {name} has a stale {field} hash")
        compiler = value.get("compiler")
        if (
            not isinstance(compiler, dict)
            or not compiler.get("language_profile")
            or not compiler.get("compiler_identity")
            or not compiler.get("pipeline_identity")
            or not compiler.get("compiler_schema_version")
            or not compiler.get("experiment_schema_version")
            or not compiler.get("selected_ssa_identity")
        ):
            errors.append(f"WASM manifest entry {name} is missing compiler identity")


def check() -> list[str]:
    errors: list[str] = []
    html_files = sorted(SITE.rglob("*.html"))
    if not html_files:
        return ["site/ contains no HTML files"]

    parsed = {path: load_html(path) for path in html_files}

    for page, collector in parsed.items():
        for attr, raw_ref in collector.refs:
            ref = raw_ref.strip()
            parts = urlsplit(ref)

            if parts.scheme or parts.netloc or ref.startswith(("mailto:", "tel:", "javascript:")):
                continue

            target_path = page if not parts.path else (page.parent / unquote(parts.path)).resolve()
            try:
                target_path.relative_to(SITE.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(ROOT)}: {attr} escapes site/: {ref}")
                continue

            if parts.path and not target_path.exists():
                errors.append(f"{page.relative_to(ROOT)}: missing local target: {ref}")
                continue

            if parts.fragment:
                fragment = unquote(parts.fragment)
                if target_path.suffix.lower() == ".html" or target_path == page.resolve():
                    target_page = target_path if target_path.suffix.lower() == ".html" else page
                    target = parsed.get(target_page)
                    if target is None and target_page.exists():
                        target = load_html(target_page)
                    if target is not None and fragment not in target.ids:
                        errors.append(
                            f"{page.relative_to(ROOT)}: missing fragment #{fragment} in {target_page.relative_to(ROOT)}"
                        )

    required = [SITE / relative for relative in MIRROR_PATHS]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required site file: {path.relative_to(ROOT)}")

    atlas_path = SITE / "atlas.json"
    if atlas_path.is_file():
        atlas = load_json(atlas_path, errors)
        if atlas is not None:
            check_atlas(atlas, errors)

    manifest_path = SITE / "assets" / "atlas-wasm-manifest.json"
    if manifest_path.is_file():
        manifest = load_json(manifest_path, errors)
        if manifest is not None:
            check_wasm_manifest(manifest, errors)

    schema_path = SITE / "schema" / "atlas.schema.json"
    if schema_path.is_file():
        schema = load_json(schema_path, errors)
        if isinstance(schema, dict):
            if schema.get("$id") != f"{CANONICAL_URL}schema/atlas.schema.json":
                errors.append("site/schema/atlas.schema.json has an unexpected $id")
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                errors.append("site/schema/atlas.schema.json must declare JSON Schema draft 2020-12")

    robots_path = SITE / "robots.txt"
    if robots_path.is_file():
        robots = robots_path.read_text(encoding="utf-8")
        if f"Sitemap: {CANONICAL_URL}sitemap.xml" not in robots:
            errors.append("site/robots.txt must advertise the canonical sitemap")

    sitemap_path = SITE / "sitemap.xml"
    if sitemap_path.is_file():
        try:
            sitemap_root = ET.fromstring(sitemap_path.read_text(encoding="utf-8"))
        except (ET.ParseError, OSError) as exc:
            errors.append(f"site/sitemap.xml is not valid XML: {exc}")
        else:
            namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            locations = {node.text for node in sitemap_root.findall("sm:url/sm:loc", namespace)}
            if CANONICAL_URL not in locations:
                errors.append("site/sitemap.xml must contain the canonical Pages URL")

    if not (ROOT / ".nojekyll").is_file():
        errors.append("missing .nojekyll required for legacy main:/ Pages compatibility")

    for source, target in MIRRORS.items():
        if not target.is_file():
            errors.append(f"missing root Pages compatibility file: {target.relative_to(ROOT)}")
        elif source.is_file() and source.read_bytes() != target.read_bytes():
            errors.append(
                f"root Pages compatibility mirror is stale: {target.relative_to(ROOT)} != {source.relative_to(ROOT)}"
            )

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("MNCS Atlas site checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("MNCS Atlas site checks passed, including topology, maturity, authority classes, consumer contract, discovery files, and root Pages compatibility mirror.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
