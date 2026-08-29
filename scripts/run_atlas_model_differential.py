#!/usr/bin/env python3
"""Run the bounded Atlas model probe across every executable backend.

The current experiment ABI exposes a single bounded sequence argument. This
runner therefore executes the same probe corpus on all five executable
adapters, compares normalized observations, and reports the full streamed
model cases separately as UNKNOWN until a stateful cross-backend runner exists.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any


BACKENDS = (
    "mncs-portable-wasm-mvp",
    "mncs-research-bytecode",
    "mncs-llvm-ir",
    "mncs-c11",
    "mncs-cranelift",
)


def byte_values(value: bytes) -> list[dict[str, dict[str, int]]]:
    return [{"byte": {"value": item}} for item in value]


def expected_value(value: int) -> list[dict[str, dict[str, object]]]:
    return [{"integer": {"value": value, "type": {"bits": 64, "signed": True}}}]


def make_corpus(fixture: dict[str, Any], case_limit: int | None = None) -> dict[str, Any]:
    probe = fixture["bounded_probe"]
    cases = []
    selected_cases = probe["cases"] if case_limit is None else probe["cases"][:case_limit]
    for case in selected_cases:
        if "text" in case:
            payload = case["text"].encode("utf-8")
        else:
            payload = bytes.fromhex(case["hex"])
        cases.append(
            {
                "id": case["id"],
                "request": {
                    "schema_version": "0.1",
                    "target": {"module": probe["module"], "function": probe["function"]},
                    "arguments": [{"sequence": {"values": byte_values(payload)}}],
                    "step_budget": 1_000_000,
                    "policy": {"effects": "unsupported"},
                },
                "expected": expected_value(case["expected"]),
                "expected_status": "returned",
            }
        )
    return {
        "schema_version": "0.2",
        "name": fixture["name"] + "-bounded",
        "description": fixture["description"],
        "cases": cases,
    }


def command_for(language_root: Path, backend: str, source: Path, corpus: Path, output: Path, binary: Path | None) -> list[str]:
    if binary is not None:
        command = [str(binary)]
    else:
        command = [
            "cargo",
            "run",
            "-q",
            "--manifest-path",
            str(language_root / "Cargo.toml"),
            "-p",
            "mncs-cli",
            "--",
        ]
    return command + [
        "experiment",
        "run",
        str(source),
        "--backend",
        backend,
        "--corpus",
        str(corpus),
        "--output-dir",
        str(output),
        "--validation-profile",
        "artifact-build",
    ]


def run_backend(
    language_root: Path,
    source: Path,
    corpus: Path,
    backend: str,
    binary: Path | None,
    timeout: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"mncs-atlas-diff-{backend}-") as output_dir:
        command = command_for(language_root, backend, source, corpus, Path(output_dir), binary)
        environment = os.environ.copy()
        environment["MNCS_LIBRARY_PATH"] = str(language_root / "library")
        process = subprocess.Popen(
            command,
            cwd=language_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            return {
                "backend": backend,
                "status": "UNKNOWN",
                "reason": f"timed out after {timeout}s",
                "command": command,
            }
        except BaseException:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        if process.returncode != 0:
            return {
                "backend": backend,
                "status": "UNKNOWN",
                "reason": f"command exited {process.returncode}",
                "stderr": stderr[-4000:],
                "command": command,
            }
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as error:
            return {
                "backend": backend,
                "status": "UNKNOWN",
                "reason": f"stdout was not a JSON experiment result: {error}",
                "stdout": stdout[-4000:],
                "stderr": stderr[-4000:],
                "command": command,
            }
        observations = [
            {
                "case_id": case.get("case_id"),
                "status": case.get("status"),
                "returned": case.get("returned"),
                "expectation_met": case.get("expectation_met"),
            }
            for case in result.get("cases", [])
            if isinstance(case, dict)
        ]
        return {
            "backend": backend,
            "status": result.get("status", "UNKNOWN"),
            "observations": observations,
            "all_expectations_met": bool(observations) and all(
                item["expectation_met"] is True for item in observations
            ),
            "unresolved_reasons": result.get("unresolved_reasons", []),
            "command": command,
        }


def compare(results: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        result
        for result in results
        if result.get("observations") and result.get("all_expectations_met")
    ]
    if len(usable) != len(BACKENDS):
        return {
            "status": "UNKNOWN",
            "reason": "At least one executable backend did not produce a usable bounded observation.",
        }
    signatures = {
        json.dumps(result["observations"], sort_keys=True, separators=(",", ":"))
        for result in usable
    }
    if len(signatures) != 1:
        return {
            "status": "UNKNOWN",
            "reason": "Executable backends returned different bounded observations.",
        }
    return {
        "status": "PASS",
        "reason": "All five executable backends returned the same bounded observations and met every expectation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--language-root", type=Path)
    parser.add_argument(
        "--binary",
        type=Path,
        help="use an existing mncs binary instead of cargo run (useful after a local build)",
    )
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument(
        "--case-limit",
        type=int,
        help="limit the executed bounded cases for a quick adapter smoke; the fixture remains complete",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    atlas_root = args.atlas_root.resolve()
    language_root = (args.language_root or atlas_root.parent / "mncs-language").resolve()
    fixture_path = atlas_root / "tests/fixtures/atlas-model-differential-corpus.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    source = atlas_root / fixture["source"]
    with tempfile.TemporaryDirectory(prefix="mncs-atlas-diff-corpus-") as directory:
        corpus_path = Path(directory) / "bounded-corpus.json"
        corpus_path.write_text(
            json.dumps(make_corpus(fixture, args.case_limit), indent=2) + "\n",
            encoding="utf-8",
        )
        results = [
            run_backend(
                language_root,
                source,
                corpus_path,
                backend,
                args.binary.resolve() if args.binary else None,
                args.timeout_seconds,
            )
            for backend in fixture["backends"]
        ]

    bounded = compare(results)
    report = {
        "schema_version": "0.1",
        "name": fixture["name"],
        "status": "UNKNOWN",
        "bounded_probe": {
            **bounded,
            "backends": results,
        },
        "full_stream": {
            "status": "UNKNOWN",
            "cases": fixture["full_input"]["cases"],
            "reason": fixture["unresolved"][0],
            "unresolved": fixture["unresolved"][1:],
        },
        "interpretation": "Bounded cross-backend agreement is empirical evidence. The full streamed Atlas model remains UNKNOWN and is not a production cutover or conformance claim.",
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
