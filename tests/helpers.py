"""Shared test helpers for the Journal Maintainer."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_atlas_tree(tmp: Path, *, with_opening_journal: bool = True) -> Path:
    site = tmp / "site"
    shutil.copytree(ROOT / "site", site)
    for relative in (
        "index.html",
        "404.html",
        "atlas.json",
        "robots.txt",
        "sitemap.xml",
        "assets/styles.css",
        "assets/app.js",
        "assets/journal.css",
        "schema/atlas.schema.json",
        "journal/index.html",
        "journal/2026-08-20-starting-the-development-journal.html",
    ):
        source = ROOT / "site" / relative
        target = tmp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            target.write_bytes(source.read_bytes())
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "check_site.py", tmp / "scripts" / "check_site.py")
    shutil.copy2(ROOT / "scripts" / "sync_pages_root.py", tmp / "scripts" / "sync_pages_root.py")
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
    if not with_opening_journal:
        for path in (site / "journal").glob("*.html"):
            if path.name != "index.html":
                path.unlink()
        (tmp / "journal").mkdir(exist_ok=True)
        for path in (tmp / "journal").glob("*.html"):
            if path.name != "index.html":
                path.unlink()
    return tmp


def evidence_item(
    *,
    item_id: str,
    title: str,
    summary: str,
    source_class: str = "owning-repository",
    kind: str = "merged-pr",
    repository: str = "epi13/mncs-atlas",
    signal: float = 8.0,
    noise: bool = False,
    negative: bool = False,
    unresolved: bool = False,
    files: list[str] | None = None,
) -> dict:
    return {
        "item_id": item_id,
        "title": title,
        "summary": summary,
        "kind": kind,
        "repository": repository,
        "project_id": repository.split("/")[-1],
        "signal": signal,
        "noise": noise,
        "negative": negative,
        "unresolved": unresolved,
        "files": files or ["docs/ARCHITECTURE.md"],
        "url": f"https://github.com/{repository}/pull/1",
        "provenance": {"locator": f"https://github.com/{repository}/pull/1"},
    }


def write_evidence(path: Path, sources: list[dict]) -> Path:
    write(path, json.dumps({"sources": sources}, indent=2))
    return path
