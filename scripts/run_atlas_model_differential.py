#!/usr/bin/env python3
"""Run the Atlas bounded and stateful model corpus across executable backends.

The stateful corpus is deliberately represented as a sequence of language
calls. The language runner retains logical returned values and resolves them
into the next call, while this script only generates deterministic byte-stream
fixtures and compares the resulting evidence.
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

# The Atlas finalizer is intentionally a large bounded aggregate computation;
# keep its per-call resource budget explicit rather than allowing an unbounded
# interpreter run.
ATLAS_EXECUTION_STEP_BUDGET = 8_000_000


def byte_values(value: bytes) -> list[dict[str, dict[str, int]]]:
    return [{"byte": {"value": item}} for item in value]


def expected_value(value: int) -> list[dict[str, dict[str, object]]]:
    return [{"integer": {"value": value, "type": {"bits": 64, "signed": True}}}]


def literal(value: object) -> dict[str, object]:
    return {"literal": value}


def previous(step_id: str, result_index: int = 0) -> dict[str, object]:
    return {"previous_result": {"step_id": step_id, "result_index": result_index}}


def stateful_case(case_id: str, payload: bytes, chunk_bytes: int = 64) -> dict[str, object]:
    steps: list[dict[str, object]] = [
        {
            "id": "init",
            "target": {"module": "mncs_atlas.model", "function": "atlas_model_init"},
            "arguments": [],
            "step_budget": ATLAS_EXECUTION_STEP_BUDGET,
            "policy": {"effects": "unsupported"},
            "expected_status": "returned",
        }
    ]
    last = "init"
    for index in range(0, len(payload), chunk_bytes):
        step_id = f"chunk-{index // chunk_bytes:04d}"
        chunk = payload[index : index + chunk_bytes]
        steps.append(
            {
                "id": step_id,
                "target": {"module": "mncs_atlas.model", "function": "atlas_model_chunk"},
                "arguments": [
                    previous(last),
                    literal({"sequence": {"values": byte_values(chunk)}}),
                ],
                "step_budget": ATLAS_EXECUTION_STEP_BUDGET,
                "policy": {"effects": "unsupported"},
                "expected_status": "returned",
            }
        )
        last = step_id
    steps.append(
        {
            "id": "finish",
            "target": {"module": "mncs_atlas.model", "function": "atlas_model_finish"},
            "arguments": [previous(last)],
            "step_budget": ATLAS_EXECUTION_STEP_BUDGET,
            "policy": {"effects": "unsupported"},
            "expected_status": "returned",
            "observe_returned": True,
        }
    )
    return {
        "id": case_id,
        "steps": steps,
        "maximum_calls": len(steps),
        "expected_final_status": "returned",
    }


def json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def reverse_object_members(value: object) -> object:
    if isinstance(value, dict):
        return {key: reverse_object_members(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reverse_object_members(item) for item in value]
    return value


def with_unknown_fields(value: object) -> object:
    if isinstance(value, dict):
        output = {key: with_unknown_fields(item) for key, item in value.items()}
        output["mncs_unknown_field"] = "ignored"
        return output
    if isinstance(value, list):
        return [with_unknown_fields(item) for item in value]
    return value


def integer_value(value: object) -> int | None:
    if isinstance(value, dict):
        integer = value.get("integer")
        if isinstance(integer, dict) and isinstance(integer.get("value"), int):
            return integer["value"]
    return None


def logical_model_summary(returned: object) -> dict[str, object]:
    """Keep the differential report compact while comparing typed model facts."""

    if not isinstance(returned, list) or not returned or not isinstance(returned[0], dict):
        return {"shape": "unexpected"}
    record = returned[0].get("record")
    if not isinstance(record, dict) or not isinstance(record.get("fields"), list):
        return {"shape": "unexpected"}
    fields = {
        item[0]: item[1]
        for item in record["fields"]
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str)
    }
    summary: dict[str, object] = {
        "shape": record.get("name"),
        "project_count": integer_value(fields.get("project_count")),
        "operator_count": integer_value(fields.get("operator_count")),
        "relationship_count": integer_value(fields.get("relationship_count")),
        "maturity_level_count": integer_value(fields.get("maturity_level_count")),
        "institutional_layer": fields.get("institutional_layer"),
        "valid": fields.get("valid"),
        "complete": fields.get("complete"),
        "maturity_counts": fields.get("maturity_counts"),
    }
    return summary


def full_case_payloads(atlas_root: Path, fixture: dict[str, Any]) -> list[tuple[str, bytes]]:
    base = (atlas_root / "site/atlas.json").read_bytes()
    document = json.loads(base)
    first_project = document["projects"][0]
    first_relationship = document["relationships"][0]
    payloads: list[tuple[str, bytes]] = []
    for case in fixture["full_input"]["cases"]:
        case_id = case["id"]
        mutation = case.get("mutation", "")
        if case_id == "complete-atlas":
            value = base
        elif case_id == "truncated-atlas":
            value = base[:-1]
        elif case_id == "truncated-at-chunk-boundaries":
            boundaries = fixture["full_input"]["chunk_boundaries"]
            for boundary in boundaries:
                if 0 < boundary <= len(base):
                    cut = min(boundary, len(base))
                    payloads.append((f"{case_id}-{boundary}", base[: cut - 1] + base[cut:]))
            continue
        elif case_id == "malformed-json-structure":
            changed = dict(document)
            changed["projects"] = {}
            value = json_bytes(changed)
        elif case_id == "malformed-utf8-atlas":
            value = base.replace(b'"mncs"', b'"\xc0\xaf"', 1)
        elif case_id == "escaped-unicode":
            value = base.replace(b'"MNCS"', b'"\\u004dNCS"', 1)
        elif case_id == "surrogate-pair":
            value = base.replace(b'"MNCS"', b'"\\ud83d\\ude00"', 1)
        elif case_id == "lone-surrogate":
            value = base.replace(b'"MNCS"', b'"\\ud800"', 1)
        elif case_id == "long-unknown-key":
            changed = dict(document)
            changed["u" * 128] = True
            value = json_bytes(changed)
        elif case_id == "missing-required-sections":
            changed = dict(document)
            changed.pop("relationships", None)
            value = json_bytes(changed)
        elif case_id == "malformed-project-record":
            changed = json.loads(base)
            changed["projects"][0]["id"] = 7
            value = json_bytes(changed)
        elif case_id == "malformed-relationship":
            changed = json.loads(base)
            changed["relationships"][0].pop("from", None)
            value = json_bytes(changed)
        elif case_id == "capacity-boundary":
            changed = json.loads(base)
            changed["projects"] = [first_project] * 32
            changed["relationships"] = [first_relationship] * 64
            value = json_bytes(changed)
        elif case_id == "one-over-capacity":
            changed = json.loads(base)
            changed["projects"] = [first_project] * 33
            changed["relationships"] = [first_relationship] * 65
            value = json_bytes(changed)
        elif case_id == "reordered-object-members":
            value = json_bytes(reverse_object_members(document))
        elif case_id == "unknown-fields":
            value = json_bytes(with_unknown_fields(document))
        elif case_id == "incomplete-root":
            value = base[:-1]
        elif case_id == "empty-collections":
            changed = dict(document)
            changed["projects"] = []
            changed["relationships"] = []
            value = json_bytes(changed)
        else:
            raise ValueError(f"no deterministic mutator for {case_id}: {mutation}")
        payloads.append((case_id, value))
    return payloads


def make_corpus(
    fixture: dict[str, Any],
    atlas_root: Path,
    case_limit: int | None = None,
    stateful_case_limit: int | None = None,
) -> dict[str, Any]:
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
                    "step_budget": ATLAS_EXECUTION_STEP_BUDGET,
                    "policy": {"effects": "unsupported"},
                },
                "expected": expected_value(case["expected"]),
                "expected_status": "returned",
            }
        )
    stateful_payloads = full_case_payloads(atlas_root, fixture)
    if stateful_case_limit is not None:
        stateful_payloads = stateful_payloads[:stateful_case_limit]
    return {
        "schema_version": "0.3",
        "name": fixture["name"] + "-bounded",
        "description": fixture["description"],
        "cases": cases,
        "stateful_cases": [
            stateful_case(case_id, payload)
            for case_id, payload in stateful_payloads
        ],
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
        cost_report_path = Path(output_dir) / "cost-report.json"
        cost_report = None
        if cost_report_path.is_file():
            try:
                cost_report = json.loads(cost_report_path.read_text())
            except json.JSONDecodeError:
                cost_report = {"status": "UNKNOWN", "reason": "invalid cost-report.json"}
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
        stateful_observations = []
        for case in result.get("stateful_cases", []):
            if not isinstance(case, dict):
                continue
            execution = case.get("execution", {})
            calls = execution.get("observations", []) if isinstance(execution, dict) else []
            stateful_observations.append(
                {
                    "case_id": case.get("case_id"),
                    "status": execution.get("status"),
                    "returned": logical_model_summary(execution.get("returned")),
                    "final_returned_digest": calls[-1].get("returned_digest")
                    if calls and isinstance(calls[-1], dict)
                    else None,
                    "calls": [
                        {
                            "step_id": call.get("step_id"),
                            "status": call.get("status"),
                            "returned_digest": call.get("returned_digest"),
                            "effects": call.get("effects", []),
                        }
                        for call in calls
                        if isinstance(call, dict)
                    ],
                    "final_expectation_met": case.get("final_expectation_met"),
                    "final_status_met": case.get("final_status_met"),
                    "step_expectations_met": case.get("step_expectations_met"),
                    "call_bound_met": case.get("call_bound_met"),
                    "step_bound_met": case.get("step_bound_met"),
                    "trace_identity": execution.get("trace_identity"),
                }
            )
        all_expectations_met = bool(observations) and all(
            item["expectation_met"] is True for item in observations
        )
        stateful_expectations_met = bool(stateful_observations) and all(
            item["final_expectation_met"] is not False
            and item["final_status_met"] is not False
            and item["step_expectations_met"] is True
            and item["call_bound_met"] is True
            and item["step_bound_met"] is not False
            for item in stateful_observations
        )
        return {
            "backend": backend,
            "status": result.get("status", "UNKNOWN"),
            "observations": observations,
            "stateful_observations": stateful_observations,
            "all_expectations_met": all_expectations_met and stateful_expectations_met,
            "unresolved_reasons": result.get("unresolved_reasons", []),
            "cost_report": cost_report,
            "command": command,
        }


def compare(results: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [
        result
        for result in results
        if result.get("observations")
        and result.get("stateful_observations")
        and result.get("all_expectations_met")
    ]
    if len(usable) != len(BACKENDS):
        return {
            "status": "UNKNOWN",
            "reason": "At least one executable backend did not produce usable bounded and stateful observations.",
        }
    signatures = {
        logical_observation_signature(result)
        for result in usable
    }
    if len(signatures) != 1:
        return {
            "status": "UNKNOWN",
            "reason": "Executable backends returned different logical bounded/stateful observations.",
        }
    return {
        "status": "PASS",
            "reason": "All five executable backends returned the same bounded and stateful logical observations and met every expectation.",
    }


def logical_observation_signature(result: dict[str, Any]) -> str:
    """Compare behavior while retaining backend-specific trace provenance."""

    stateful = [
        {
            key: value
            for key, value in observation.items()
            if key != "trace_identity"
        }
        for observation in result["stateful_observations"]
    ]
    return json.dumps(
        (result["observations"], stateful),
        sort_keys=True,
        separators=(",", ":"),
    )


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
    parser.add_argument(
        "--stateful-case-limit",
        type=int,
        help="limit generated stateful cases for a quick adapter smoke; the fixture remains complete",
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
            json.dumps(
                make_corpus(
                    fixture,
                    atlas_root,
                    args.case_limit,
                    args.stateful_case_limit,
                ),
                indent=2,
            )
            + "\n",
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
    full_corpus_executed = args.case_limit is None and args.stateful_case_limit is None
    coverage_reason = None
    if not full_corpus_executed:
        coverage_reason = "report is a smoke run with an explicit corpus limit"
    evidence_pass = bounded.get("status") == "PASS" and full_corpus_executed
    report = {
        "schema_version": "0.1",
        "name": fixture["name"],
        "status": "PASS" if evidence_pass else "UNKNOWN",
        "coverage": {
            "bounded_case_limit": args.case_limit,
            "stateful_case_limit": args.stateful_case_limit,
            "full_corpus_executed": full_corpus_executed,
        },
        "bounded_probe": {
            **bounded,
            "backends": results,
        },
        "full_stream": {
            "status": "PASS" if evidence_pass else "UNKNOWN",
            "cases": fixture["full_input"]["cases"],
            "executed_case_ids": [
                item.get("case_id")
                for item in results[0].get("stateful_observations", [])
            ]
            if results
            else [],
            "reason": coverage_reason or bounded.get("reason"),
            "unresolved": []
            if evidence_pass
            else fixture["unresolved"]
            + ([coverage_reason] if coverage_reason else []),
        },
        "interpretation": "Bounded cross-backend agreement is empirical logical trace evidence, not a conformance or production cutover decision.",
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
