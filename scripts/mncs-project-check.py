#!/usr/bin/env python3
"""Run the bounded Atlas MNCS check suite and emit a check-result document.

This is an adapter for mncs-actions, not an MNCS conformance verifier. The
result is deliberately scoped to the repository's checkable surface: site
integrity (links, machine maps, admission sync, Pages mirror), the unit
suite including the admission/session/capability-broker tests, and journal
integrity. The full CI suite still runs in ci.yml.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


RESULT_ID = "project-tests"
PROVIDER = "mncs-atlas-project"
SCOPE = "mncs-atlas bounded check surface"

CHECKS = (
    ("site integrity", (sys.executable, "scripts/check_site.py")),
    ("admission sync", (sys.executable, "scripts/sync_admission.py", "--check")),
    ("mirror freshness", (sys.executable, "scripts/sync_pages_root.py", "--check")),
    (
        "unit suite",
        (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."),
    ),
    ("journal integrity", (sys.executable, "scripts/check_journal.py")),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=".mncs/project-check.json",
        help="path for the mncs.check-result/1 document",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result_path = Path(args.output)
    failures: list[str] = []
    for name, command in CHECKS:
        try:
            completed = subprocess.run(
                command,
                check=False,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
            )
        except OSError as error:
            failures.append(f"{name}: could not execute ({error})")
        else:
            if completed.returncode != 0:
                tail = (completed.stdout + completed.stderr).strip().splitlines()
                detail = tail[-1] if tail else f"exit {completed.returncode}"
                failures.append(f"{name}: {detail}")

    verdict = "PASS" if not failures else "FAIL"
    summary = (
        "Atlas bounded check suite passed."
        if not failures
        else f"Atlas bounded check suite failed: {'; '.join(failures)}"
    )
    result = {
        "schema_version": "mncs.check-result/1",
        "id": RESULT_ID,
        "provider": PROVIDER,
        "verdict": verdict,
        "scope": SCOPE,
        "claim": "The repository's site, admission-sync, mirror, unit, and journal checks completed successfully.",
        "summary": summary,
        "references": [
            {"kind": "check-script", "path": "scripts/check_site.py"},
            {"kind": "check-script", "path": "scripts/sync_admission.py"},
            {"kind": "check-script", "path": "scripts/sync_pages_root.py"},
            {"kind": "test-suite", "path": "tests/test_admission_core.py"},
            {"kind": "test-suite", "path": "tests/test_admission_orientation.py"},
            {"kind": "source", "path": "site/atlas.json"},
            {"kind": "source", "path": "site/admission.json"},
            {"kind": "source", "path": "mncs/admission-model.mncs"},
        ],
    }

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(summary)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
