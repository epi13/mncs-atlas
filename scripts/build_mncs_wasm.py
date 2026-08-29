#!/usr/bin/env python3
"""Build the production Atlas MNCS/WASM artifacts from the sibling language checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    name: str, result: dict[str, object], asset_dir: Path
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
    digest = hashlib.sha256(wasm_bytes).hexdigest()
    if digest != artifact.get("bytes_sha256"):
        raise RuntimeError(f"{name}: artifact digest does not match its bytes")

    output_path = asset_dir / f"{name}.wasm"
    output_path.write_bytes(wasm_bytes)
    return {
        "path": f"assets/{output_path.name}",
        "sha256": digest,
        "bytes": len(wasm_bytes),
        "status": status,
        "exports": artifact.get("exports", []),
        "corpus_cases": [
            {
                "id": case.get("case_id"),
                "expectation_met": case.get("expectation_met"),
            }
            for case in cases
            if isinstance(case, dict)
        ],
    }


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
    asset_dir = atlas_root / "site/assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    built: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="mncs-atlas-wasm-") as temporary:
        temporary_root = Path(temporary)
        for name, source_relative, corpus_relative in ARTIFACTS:
            source = atlas_root / source_relative
            atlas_corpus = atlas_root / corpus_relative
            corpus = atlas_corpus if atlas_corpus.is_file() else language_root / corpus_relative
            result = run_experiment(
                language_root,
                source,
                corpus,
                temporary_root / name,
            )
            built[name] = materialize_artifact(name, result, asset_dir)

    manifest = {
        "schema_version": "0.1",
        "kind": "mncs-atlas-wasm",
        "authority": "orientation-only",
        "backend": BACKEND,
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
            ],
            "unresolved": [
                "cross-backend equivalence for the full Atlas model",
                "formal conformance/cutover review",
            ],
        },
        "memory_export": "memory",
        "artifacts": built,
    }
    (asset_dir / "atlas-wasm-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, str(atlas_root / "scripts/sync_pages_root.py")],
        cwd=atlas_root,
        check=True,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
