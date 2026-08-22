#!/usr/bin/env python3
"""Thin wrapper so Atlas scripts/ remains the obvious entry point."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_maintainer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
