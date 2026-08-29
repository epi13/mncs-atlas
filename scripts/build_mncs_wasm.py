#!/usr/bin/env python3
"""Build the production Atlas MNCS/WASM artifacts from the sibling language checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BACKEND = "mncs-portable-wasm-mvp"
ARTIFACTS = (
    (
        "atlas-json-scan",
        Path("mncs/atlas-json-scan.mncs"),
        Path("examples/execution/atlas-json-scan-corpus.json"),
    ),
    (
        "atlas-json-projection",
        Path("mncs/atlas-json-projection.mncs"),
        Path("examples/execution/atlas-json-projection-corpus.json"),
    ),
    (
        "atlas-model",
        Path("mncs/atlas-model.mncs"),
        Path("tests/fixtures/atlas-model-corpus.json"),
    ),
)

MANIFEST_NAME = "atlas-wasm-manifest.json"
MANIFEST_SCHEMA_VERSION = "0.2"
LANGUAGE_LOCK = Path("mncs/mncs-language.lock.json")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source_tree_sha256(root: Path, suffixes: set[str]) -> str:
    """Return a stable content identity for a source subtree."""

    digest = hashlib.sha256()
    for path in sorted(
        path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes
    ):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            while block := handle.read(1024 * 1024):
                digest.update(block)
    return digest.hexdigest()


def file_reference(path: Path, root: Path, repository: str) -> dict[str, str]:
    return {
        "repository": repository,
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def git_output(root: Path, *arguments: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if os.environ.get("MNCS_TIMINGS") and completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def is_derived_atlas_output(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    return normalized in {
        "assets/atlas-json-scan.wasm",
        "assets/atlas-json-projection.wasm",
        "assets/atlas-model.wasm",
        "assets/atlas-wasm-manifest.json",
        "site/assets/atlas-json-scan.wasm",
        "site/assets/atlas-json-projection.wasm",
        "site/assets/atlas-model.wasm",
        "site/assets/atlas-wasm-manifest.json",
    } or normalized.startswith("site/mncs-atlas-wasm-")


def git_provenance(root: Path, name: str) -> dict[str, object]:
    """Capture the state of producer inputs, excluding derived build outputs."""

    commit = git_output(root, "rev-parse", "HEAD")
    raw_status = git_output(root, "status", "--porcelain=v1", "--untracked-files=all")
    if commit is None or raw_status is None:
        return {
            "name": name,
            "commit": None,
            "working_tree": "unknown",
            "working_tree_hash": None,
            "reproducibility": "unknown",
        }

    status_lines = []
    ignored_paths = []
    for line in raw_status.splitlines():
        relative = line[3:] if len(line) > 3 else ""
        if name == "mncs-atlas" and is_derived_atlas_output(relative):
            ignored_paths.append(relative)
        else:
            status_lines.append(line)
    status = "\n".join(status_lines)
    digest = hashlib.sha256()
    diff_arguments = ["diff", "--binary", "HEAD", "--", "."]
    if name == "mncs-atlas":
        diff_arguments.extend(
            [
                ":(exclude)assets/atlas-json-scan.wasm",
                ":(exclude)assets/atlas-json-projection.wasm",
                ":(exclude)assets/atlas-model.wasm",
                ":(exclude)assets/atlas-wasm-manifest.json",
                ":(exclude)site/assets/atlas-json-scan.wasm",
                ":(exclude)site/assets/atlas-json-projection.wasm",
                ":(exclude)site/assets/atlas-model.wasm",
                ":(exclude)site/assets/atlas-wasm-manifest.json",
            ]
        )
    diff = git_output(root, *diff_arguments) or ""
    digest.update(diff.encode("utf-8"))
    digest.update(status.encode("utf-8"))
    for line in status_lines:
        relative = line[3:] if len(line) > 3 else ""
        path = root / relative
        if relative and path.is_file() and "??" in line[:2]:
            digest.update(relative.encode("utf-8"))
            digest.update(path.read_bytes())
    clean = not status
    return {
        "name": name,
        "commit": commit,
        "working_tree": "clean" if clean else "dirty",
        "working_tree_hash": digest.hexdigest(),
        "ignored_derived_paths": sorted(set(ignored_paths)),
        "reproducibility": "reproducible" if clean else "uncertain",
    }


def compiler_provenance(result: dict[str, object]) -> dict[str, object]:
    definition = result.get("definition")
    study = result.get("compiler_study")
    definition = definition if isinstance(definition, dict) else {}
    study = study if isinstance(study, dict) else {}
    return {
        "language_profile": definition.get("source_profile") or definition.get("language_version"),
        "compiler_identity": study.get("compiler_identity"),
        "pipeline_identity": study.get("pipeline_identity"),
        "compiler_schema_version": study.get("schema_version"),
        "experiment_schema_version": result.get("schema_version"),
        "selected_ssa_identity": study.get("selected_ssa_identity"),
    }


def read_language_lock(atlas_root: Path, language_root: Path) -> dict[str, object]:
    path = atlas_root / LANGUAGE_LOCK
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"unable to read language producer lock {path}: {error}") from error
    if not isinstance(lock, dict) or not isinstance(lock.get("revision"), str):
        raise RuntimeError("language producer lock must declare a Git revision")
    actual = git_output(language_root, "rev-parse", "HEAD")
    if actual != lock["revision"]:
        raise RuntimeError(
            "mncs-language checkout does not match the pinned Atlas producer revision: "
            f"expected {lock['revision']}, found {actual or 'UNKNOWN'}"
        )
    return lock


def run_experiment(
    language_root: Path, source: Path, corpus: Path, output_dir: Path
) -> dict[str, object]:
    environment = os.environ.copy()
    environment["MNCS_LIBRARY_PATH"] = str(language_root / "library")
    command = [
        "cargo",
        "run",
        "-q",
        "--manifest-path",
        str(language_root / "Cargo.toml"),
        "-p",
        "mncs-cli",
        "--",
        "experiment",
        "run",
        str(source),
        "--backend",
        BACKEND,
        "--corpus",
        str(corpus),
        "--output-dir",
        str(output_dir),
        "--validation-profile",
        "artifact-build",
    ]
    completed = subprocess.run(
        command,
        cwd=language_root,
        env=environment,
        capture_output=True,
        text=True,
        # The bounded Atlas model is intentionally larger than the small
        # language fixtures; keep the build bounded without making a cold
        # compiler run fail before it can materialize the artifact.
        timeout=900,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"experiment failed for {source}: exit={completed.returncode}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"experiment did not emit JSON for {source}: {error}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        ) from error
    if not isinstance(result, dict):
        raise RuntimeError(f"experiment result for {source} is not an object")
    return result


def materialize_artifact(
    name: str,
    result: dict[str, object],
    asset_dir: Path,
    *,
    source: Path | None = None,
    corpus: Path | None = None,
    source_reference: dict[str, str] | None = None,
    corpus_reference: dict[str, str] | None = None,
) -> dict[str, object]:
    status = result.get("status")
    if status not in {"PASS", "UNKNOWN"}:
        raise RuntimeError(f"{name}: refusing result with status {status!r}")
    cases = result.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError(f"{name}: result has no execution cases")
    failures = [case for case in cases if not isinstance(case, dict) or case.get("expectation_met") is not True]
    if failures:
        raise RuntimeError(f"{name}: corpus expectations were not met: {failures!r}")
    stateful_cases = result.get("stateful_cases", [])
    if not isinstance(stateful_cases, list):
        raise RuntimeError(f"{name}: stateful_cases is not a list")
    if name == "atlas-model" and not stateful_cases:
        raise RuntimeError(f"{name}: production model corpus has no stateful cases")
    stateful_failures = [
        case
        for case in stateful_cases
        if not isinstance(case, dict)
        or case.get("step_expectations_met") is not True
        or case.get("final_expectation_met") is False
        or case.get("final_status_met") is False
        or case.get("call_bound_met") is not True
        or case.get("step_bound_met") is False
    ]
    if stateful_failures:
        raise RuntimeError(
            f"{name}: stateful corpus expectations were not met: {stateful_failures!r}"
        )

    artifact = result.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("artifact_kind") != "wasm_module":
        raise RuntimeError(f"{name}: result does not contain a WASM module artifact")
    encoded = artifact.get("bytes_hex")
    if not isinstance(encoded, str):
        raise RuntimeError(f"{name}: artifact has no bytes_hex payload")
    try:
        wasm_bytes = bytes.fromhex(encoded)
    except ValueError as error:
        raise RuntimeError(f"{name}: artifact bytes_hex is invalid: {error}") from error
    if not wasm_bytes.startswith(b"\x00asm"):
        raise RuntimeError(f"{name}: artifact is not a WASM binary")
    digest = sha256_bytes(wasm_bytes)
    if digest != artifact.get("bytes_sha256"):
        raise RuntimeError(f"{name}: artifact digest does not match its bytes")

    output_path = asset_dir / f"{name}.wasm"
    output_path.write_bytes(wasm_bytes)
    return {
        "path": f"assets/{output_path.name}",
        "sha256": digest,
        "bytes": len(wasm_bytes),
        "status": status,
        "source": source_reference,
        "source_sha256": sha256_file(source) if source is not None else None,
        "corpus": corpus_reference,
        "corpus_sha256": sha256_file(corpus) if corpus is not None else None,
        "compiler": compiler_provenance(result),
        "exports": artifact.get("exports", []),
        "corpus_cases": [
            {
                "id": case.get("case_id"),
                "expectation_met": case.get("expectation_met"),
            }
            for case in cases
            if isinstance(case, dict)
        ],
        "stateful_cases": [
            {
                "id": case.get("case_id"),
                "step_expectations_met": case.get("step_expectations_met"),
                "final_expectation_met": case.get("final_expectation_met"),
                "final_status_met": case.get("final_status_met"),
                "call_bound_met": case.get("call_bound_met"),
                "step_bound_met": case.get("step_bound_met"),
            }
            for case in stateful_cases
            if isinstance(case, dict)
        ],
    }


def validate_manifest(manifest: dict[str, object], staged_asset_dir: Path) -> None:
    """Validate every staged artifact before any live asset is replaced."""

    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError("manifest schema version is not the current producer schema")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise RuntimeError("manifest is missing producer provenance")
    for producer in ("atlas", "mncs_language"):
        metadata = provenance.get(producer)
        if not isinstance(metadata, dict):
            raise RuntimeError(f"manifest is missing {producer} provenance")
        if metadata.get("reproducibility") not in {"reproducible", "uncertain", "unknown"}:
            raise RuntimeError(f"manifest has invalid {producer} reproducibility state")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {name for name, _, _ in ARTIFACTS}:
        raise RuntimeError("manifest artifact set does not match the declared build set")
    for name, metadata in artifacts.items():
        if not isinstance(metadata, dict):
            raise RuntimeError(f"{name}: manifest metadata is not an object")
        relative = metadata.get("path")
        if relative != f"assets/{name}.wasm":
            raise RuntimeError(f"{name}: manifest path is contradictory")
        artifact = staged_asset_dir / f"{name}.wasm"
        if not artifact.is_file():
            raise RuntimeError(f"{name}: staged artifact is missing")
        if metadata.get("bytes") != artifact.stat().st_size:
            raise RuntimeError(f"{name}: manifest byte count is stale")
        if metadata.get("sha256") != sha256_file(artifact):
            raise RuntimeError(f"{name}: manifest SHA-256 is stale")
        if not isinstance(metadata.get("source_sha256"), str) or len(metadata["source_sha256"]) != 64:
            raise RuntimeError(f"{name}: source SHA-256 is missing")
        if not isinstance(metadata.get("corpus_sha256"), str) or len(metadata["corpus_sha256"]) != 64:
            raise RuntimeError(f"{name}: corpus SHA-256 is missing")
        for field in ("source", "corpus"):
            reference = metadata.get(field)
            if (
                not isinstance(reference, dict)
                or not isinstance(reference.get("repository"), str)
                or not isinstance(reference.get("path"), str)
                or not isinstance(reference.get("sha256"), str)
                or len(reference["sha256"]) != 64
            ):
                raise RuntimeError(f"{name}: {field} provenance is missing")
            if reference["sha256"] != metadata[f"{field}_sha256"]:
                raise RuntimeError(f"{name}: {field} provenance hash is contradictory")
        stateful_cases = metadata.get("stateful_cases", [])
        if name == "atlas-model" and (
            not isinstance(stateful_cases, list) or not stateful_cases
        ):
            raise RuntimeError(f"{name}: manifest has no stateful corpus evidence")
        compiler = metadata.get("compiler")
        if (
            not isinstance(compiler, dict)
            or not compiler.get("language_profile")
            or not compiler.get("compiler_identity")
            or not compiler.get("pipeline_identity")
            or not compiler.get("compiler_schema_version")
            or not compiler.get("experiment_schema_version")
            or not compiler.get("selected_ssa_identity")
        ):
            raise RuntimeError(f"{name}: compiler identity is missing")


def publish_artifact_set(staged_asset_dir: Path, destinations: list[Path]) -> None:
    """Publish a complete generated set with rollback on publication failure.

    All expensive and fallible work occurs in the staging directory. The
    replacement phase only moves already-validated files and restores every
    previous file if any move fails, so a failed build cannot leave a
    mixed-generation set behind.
    """

    names = [f"{name}.wasm" for name, _, _ in ARTIFACTS] + [MANIFEST_NAME]
    for destination in destinations:
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            if not (staged_asset_dir / name).is_file():
                raise RuntimeError(f"staged publication is missing {name}")

    backup_root = Path(
        tempfile.mkdtemp(prefix="mncs-atlas-wasm-backup-", dir=staged_asset_dir.parent)
    )
    publication_root = backup_root / "new"
    publication_root.mkdir()
    backups: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        publication_sources: list[tuple[Path, Path]] = []
        for index, destination in enumerate(destinations):
            copy_dir = publication_root / str(index)
            copy_dir.mkdir()
            for name in names:
                source = staged_asset_dir / name
                copy = copy_dir / name
                shutil.copy2(source, copy)
                publication_sources.append((copy, destination / name))
        for copy, target in publication_sources:
            backup_dir = backup_root / "old" / str(len(backups))
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / target.name
            if target.exists():
                target.replace(backup)
                backups.append((backup, target))
            copy.replace(target)
            published.append(target)
    except Exception:
        for target in reversed(published):
            target.unlink(missing_ok=True)
        for backup, target in reversed(backups):
            if backup.exists():
                backup.replace(target)
        raise
    finally:
        shutil.rmtree(backup_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--language-root",
        type=Path,
        help="sibling mncs-language checkout (defaults to ../mncs-language)",
    )
    parser.add_argument(
        "--atlas-root",
        type=Path,
        help="Atlas checkout (defaults to this script's parent checkout)",
    )
    args = parser.parse_args()

    atlas_root = (args.atlas_root or Path(__file__).resolve().parents[1]).resolve()
    language_root = (
        args.language_root or atlas_root.parent / "mncs-language"
    ).resolve()
    language_lock = read_language_lock(atlas_root, language_root)
    asset_dir = atlas_root / "site/assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    root_asset_dir = atlas_root / "assets"
    if root_asset_dir.is_dir():
        mirror_check = subprocess.run(
            [sys.executable, str(atlas_root / "scripts/sync_pages_root.py"), "--check"],
            cwd=atlas_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if mirror_check.returncode != 0:
            raise RuntimeError(
                "refusing to build while the Pages compatibility mirror is stale:\n"
                f"{mirror_check.stdout}{mirror_check.stderr}"
            )

    # Snapshot producer inputs before creating the in-checkout staging tree.
    # Derived WASM/manifest paths are excluded by git_provenance so a clean
    # source checkout remains reproducible while those tracked outputs are
    # being regenerated.
    atlas_provenance = git_provenance(atlas_root, "mncs-atlas")
    language_provenance = git_provenance(language_root, "mncs-language")

    built: dict[str, object] = {}
    temporary_context = tempfile.TemporaryDirectory(
        prefix="mncs-atlas-wasm-", dir=asset_dir.parent
    )
    temporary_root = Path(temporary_context.name)
    staged_asset_dir = temporary_root / "assets"
    staged_asset_dir.mkdir()
    try:
        for name, source_relative, corpus_relative in ARTIFACTS:
            source = atlas_root / source_relative
            atlas_corpus = atlas_root / corpus_relative
            corpus = atlas_corpus if atlas_corpus.is_file() else language_root / corpus_relative
            corpus_root = atlas_root if atlas_corpus.is_file() else language_root
            corpus_repository = "mncs-atlas" if atlas_corpus.is_file() else "mncs-language"
            result = run_experiment(
                language_root,
                source,
                corpus,
                temporary_root / name,
            )
            built[name] = materialize_artifact(
                name,
                result,
                staged_asset_dir,
                source=source,
                corpus=corpus,
                source_reference=file_reference(source, atlas_root, "mncs-atlas"),
                corpus_reference=file_reference(corpus, corpus_root, corpus_repository),
            )
    except BaseException:
        temporary_context.cleanup()
        raise

    reproducibility_states = [
        atlas_provenance["reproducibility"],
        language_provenance["reproducibility"],
    ]
    if "unknown" in reproducibility_states:
        reproducibility_status = "unknown"
    elif all(state == "reproducible" for state in reproducibility_states):
        reproducibility_status = "reproducible"
    else:
        reproducibility_status = "uncertain"

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "kind": "mncs-atlas-wasm",
        "authority": "orientation-only",
        "backend": BACKEND,
        "build": {
            "mode": "cargo experiment run",
            "command": "cargo run -q --manifest-path <mncs-language>/Cargo.toml -p mncs-cli -- experiment run <source.mncs> --backend mncs-portable-wasm-mvp --corpus <corpus.json> --output-dir <staging> --validation-profile artifact-build",
            "language_root": "../mncs-language",
            "language_revision_lock": language_lock["revision"],
            "artifact_set": [name for name, _, _ in ARTIFACTS],
        },
        "provenance": {
            "atlas": atlas_provenance,
            "mncs_language": language_provenance,
            "standard_library": {
                "path": "library",
                "sha256": source_tree_sha256(language_root / "library", {".mncs"}),
            },
            "reproducibility": {
                "status": reproducibility_status,
                "reason": "Both producer working trees were clean at build time"
                if reproducibility_status == "reproducible"
                else "At least one producer working tree was dirty or unavailable; exact regeneration is not certified",
            },
        },
        "input": {
            "atlas_data": "atlas.json",
            "transport": "fetch-arraybuffer-to-Uint8Array",
            "json_semantics": "owned by MNCS/WASM substrate; JavaScript does not parse atlas.json",
            "application_semantics": "owned by mncs_atlas.model; the host interprets only typed render commands",
        },
        "chunking": {"max_bytes": 64, "host_may_stream": True},
        "view_descriptor": {
            "type": "i64",
            "offset_bits": "low32",
            "length_bits": "high32",
            "internal_byte_cell_marker": "low32 bit0; masked before host-visible byte reads",
        },
        "host_buffer_abi": {
            "function": "mncs_host_buffer",
            "reset_function": "mncs_host_buffer_reset",
            "version": "mncs.host-buffer.v1",
            "parameter": "i32 capacity",
            "result": "i64 packed low32=offset high32=capacity",
            "lifetime": "reserved region remains host-owned until module instance is dropped",
            "reuse": "scalar consumers reset after each call; the typed model retains immutable state cells and must not reset until its instance is dropped",
        },
        "typed_model_abi": {
            "module": "mncs_atlas.model",
            "stream_functions": ["atlas_model_init", "atlas_model_chunk", "atlas_model_finish"],
            "render_function": "atlas_render",
            "text_view": {
                "fields": ["encoded", "length", "start", "utf8_valid"],
                "representation": "borrowed byte span into the original atlas.json input",
                "layout": {"encoded": 0, "length": 8, "start": 16, "utf8_valid": 24},
            },
            "render_plan": {
                "fields": ["complete", "maturity_counts", "node_count", "nodes", "project_count", "relationship_count", "valid"],
                "layout": {
                    "complete": 0,
                    "maturity_counts": 8,
                    "node_count": 16,
                    "nodes": 24,
                    "project_count": 32,
                    "relationship_count": 40,
                    "valid": 48,
                },
                "node_operations": {
                    "1": "append_project_and_status",
                    "2": "clear_target",
                    "3": "render_summary",
                    "4": "render_maturity_level",
                    "5": "render_consumer_contract_header",
                    "6": "render_consumer_contract_resolution_step",
                    "7": "render_consumer_contract_rule",
                    "8": "render_institutional_layer",
                },
                "targets": {
                    "1": "project_grid",
                    "2": "status_grid",
                    "3": "summary",
                    "4": "project_and_status_pair",
                    "5": "maturity_model",
                    "6": "consumer_contract_header",
                    "7": "consumer_contract_resolution_order",
                    "8": "consumer_contract_rules",
                    "9": "institutional_layer",
                },
                "node_layout": {
                    "stride_bytes": 88,
                    "operation": 0,
                    "primary": 8,
                    "quaternary": 16,
                    "secondary": 24,
                    "slot": 32,
                    "target": 40,
                    "tertiary": 48,
                    "value": 56,
                    "value_aux": 64,
                    "value_text": 72,
                    "value_text_aux": 80,
                },
            },
            "capacities": {
                "projects": 32,
                "operator_components": 8,
                "relationships": 64,
                "maturity_levels": 5,
                "consumer_contract_items": 8,
                "render_nodes": 64,
            },
            "max_input_bytes": 65536,
            "arena_pages": 512,
            "arena_bytes": 33554432,
        },
        "validation": {
            "status": "UNKNOWN",
            "automated_checks": [
                "wasm_magic",
                "sha256",
                "corpus_expectations",
                "bounded_capacity_declarations",
                "production_static_fallback",
                "staged_publication",
                "manifest_internal_hashes",
                "producer_provenance",
            ],
            "unresolved": [
                "cross-backend equivalence for the full Atlas model",
                "formal conformance/cutover review",
            ],
        },
        "memory_export": "memory",
        "artifacts": built,
    }
    (staged_asset_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    try:
        validate_manifest(manifest, staged_asset_dir)
        destinations = [asset_dir]
        if root_asset_dir.is_dir():
            destinations.append(root_asset_dir)
        publish_artifact_set(staged_asset_dir, destinations)
    finally:
        temporary_context.cleanup()
    subprocess.run(
        [sys.executable, str(atlas_root / "scripts/sync_pages_root.py")],
        cwd=atlas_root,
        check=True,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
