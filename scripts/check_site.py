#!/usr/bin/env python3
"""Dependency-free integrity checks for the static MNCS Atlas site."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CANONICAL_URL = "https://epi13.github.io/mncs-atlas/"

MIRROR_PATHS = (
    "index.html",
    "404.html",
    "atlas.json",
    "robots.txt",
    "sitemap.xml",
    "assets/styles.css",
    "assets/app.js",
    "schema/atlas.schema.json",
)
MIRRORS = {SITE / relative: ROOT / relative for relative in MIRROR_PATHS}


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

    for index, relation in enumerate(relationships):
        if not isinstance(relation, dict):
            errors.append(f"site/atlas.json relationships[{index}] must be an object")
            continue
        source = relation.get("from")
        target = relation.get("to")
        if source not in known_ids:
            errors.append(f"site/atlas.json relationship references unknown source: {source}")
        if target not in known_ids:
            errors.append(f"site/atlas.json relationship references unknown target: {target}")
        if not relation.get("kind") or not relation.get("description"):
            errors.append(f"site/atlas.json relationship {source}->{target} is missing kind or description")

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

    print("MNCS Atlas site checks passed, including topology, discovery files, and root Pages compatibility mirror.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
