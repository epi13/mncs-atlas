#!/usr/bin/env python3
"""Synchronize the canonical site/ tree into the root GitHub Pages compatibility mirror."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

MIRRORS = {
    SITE / "index.html": ROOT / "index.html",
    SITE / "404.html": ROOT / "404.html",
    SITE / "atlas.json": ROOT / "atlas.json",
    SITE / "assets" / "styles.css": ROOT / "assets" / "styles.css",
    SITE / "assets" / "app.js": ROOT / "assets" / "app.js",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail instead of writing when the mirror is stale")
    args = parser.parse_args()

    stale: list[str] = []
    for source, target in MIRRORS.items():
        if not source.is_file():
            print(f"missing canonical site file: {source.relative_to(ROOT)}")
            return 1

        source_bytes = source.read_bytes()
        if target.is_file() and target.read_bytes() == source_bytes:
            continue

        if args.check:
            stale.append(str(target.relative_to(ROOT)))
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_bytes)
        print(f"synced {source.relative_to(ROOT)} -> {target.relative_to(ROOT)}")

    if stale:
        print("GitHub Pages root compatibility mirror is stale:")
        for path in stale:
            print(f"- {path}")
        print("Run: python scripts/sync_pages_root.py")
        return 1

    if args.check:
        print("GitHub Pages root compatibility mirror is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
