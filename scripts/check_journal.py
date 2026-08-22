#!/usr/bin/env python3
"""Focused Journal Maintainer checks. Complements scripts/check_site.py."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_maintainer.publication import check_changed_paths  # noqa: E402
from journal_maintainer.validate import validate_journal  # noqa: E402


def main() -> int:
    errors = validate_journal(ROOT / "site" / "journal")
    if errors:
        print("Journal checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Journal filename, numbering, covered-period, index, and disclosure checks passed.")
    return 0


def check_paths() -> int:
    import os
    base = os.environ.get("JOURNAL_DIFF_BASE") or os.environ.get("GITHUB_BASE_SHA")
    head = os.environ.get("JOURNAL_DIFF_HEAD") or os.environ.get("GITHUB_SHA") or "HEAD"
    if base:
        result = check_changed_paths(ROOT, base=base, head=head)
    else:
        result = check_changed_paths(ROOT)
    if result.changed:
        print("Changed paths:")
        for path in result.changed:
            print(f"- {path}")
    if not result.allowed:
        print("Unauthorized journal publication paths:")
        for path in result.unexpected:
            print(f"- {path}")
        for error in result.history_errors:
            print(f"- {error}")
        return 1
    print("Changed paths are within the authorized journal publication surface.")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "journal"
    if command in {"--paths", "paths"}:
        raise SystemExit(check_paths())
    raise SystemExit(main())
