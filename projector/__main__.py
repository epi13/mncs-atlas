"""Command entry points for the deterministic Atlas projector.

``python -m projector project`` regenerates ``site/dashboard.json`` from
canonical state.  ``--check`` performs a dry run: it reports whether the
semantic output would change without writing anything.
``python -m projector check`` validates an existing projection file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import PROJECTOR_ID, PROJECTOR_VERSION
from .discover import discover
from .project import project
from .render import (
    DASHBOARD_HTML,
    DASHBOARD_JSON,
    envelope,
    envelope_bytes,
    read_previous,
    refresh_noscript,
    semantic_changed,
    verify_envelope,
)
from .validate import sanitize, validate


def _atlas_root() -> Path:
    return Path(__file__).resolve().parents[1]


def cmd_project(output: Path | None, check: bool, root: Path) -> int:
    bundle = discover(atlas_root=root)
    payload = project(bundle)
    errors = validate(payload)
    if errors:
        for error in errors:
            print(f"projector: invalid: {error}", file=sys.stderr)
        return 2
    clean = sanitize(payload)
    target = output or (root / DASHBOARD_JSON)
    previous = read_previous(target)
    changed = semantic_changed(previous, clean["semantic_hash"])
    status = {
        "projector": PROJECTOR_ID,
        "projector_version": PROJECTOR_VERSION,
        "semantic_hash": clean["semantic_hash"],
        "changed": changed,
        "sources": [
            {"id": source["id"], "status": source["status"]} for source in clean["sources"]
        ],
        "freshness": clean["freshness"],
    }
    print(json.dumps(status, indent=2, sort_keys=True))
    if check:
        return 0 if changed else 0
    data = envelope(clean)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(envelope_bytes(data))
    refresh_noscript(root / DASHBOARD_HTML, clean)
    return 0


def cmd_check(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"projector: unreadable {path}: {error}", file=sys.stderr)
        return 2
    if not isinstance(data, dict) or "projection" not in data:
        print(f"projector: {path} is not a dashboard envelope", file=sys.stderr)
        return 2
    errors = validate(data["projection"])
    if errors:
        for error in errors:
            print(f"projector: invalid: {error}", file=sys.stderr)
        return 2
    if not verify_envelope(data):
        print("projector: invalid: semantic hash mismatch", file=sys.stderr)
        return 2
    print(f"projector: {path} valid ({data['semantic_hash']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="projector")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("project", help="regenerate the dashboard projection")
    build.add_argument("--output", type=Path, default=None)
    build.add_argument("--check", action="store_true", help="dry run: report change only")
    build.add_argument("--atlas-root", type=Path, default=_atlas_root())
    check = sub.add_parser("check", help="validate an existing projection file")
    check.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "project":
        return cmd_project(args.output, args.check, args.atlas_root.resolve())
    return cmd_check(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
