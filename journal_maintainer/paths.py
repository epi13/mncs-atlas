"""Authorized mutation surface and Pages mirror layout.

A routine Journal Maintainer publication may only change the journal
publication tree, journal discovery files required by Atlas publishing, and
the generated root compatibility mirrors of those canonical files.
"""

from __future__ import annotations

from pathlib import Path

MIRROR_PATHS = (
    "index.html",
    "404.html",
    "atlas.json",
    "robots.txt",
    "sitemap.xml",
    "assets/styles.css",
    "assets/app.js",
    "assets/journal.css",
    "schema/atlas.schema.json",
)

MIRROR_TREES = ("journal",)

# Routine publication writes. Implementation/CI/docs changes belong in a
# separate PR and are never auto-merge eligible for a journal run.
ROUTINE_WRITE_PREFIXES = (
    "site/journal/",
    "journal/",
    "site/sitemap.xml",
    "sitemap.xml",
)

ROUTINE_WRITE_EXACT = {
    "site/journal/index.html",
    "journal/index.html",
    "site/sitemap.xml",
    "sitemap.xml",
}

ROUTINE_ENTRY_PATTERN = r"^site/journal/\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.html$"
MIRROR_ENTRY_PATTERN = r"^journal/\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.html$"


def iter_mirror_pairs(root: Path):
    site = root / "site"
    for relative in MIRROR_PATHS:
        yield site / relative, root / relative
    for tree in MIRROR_TREES:
        source_root = site / tree
        if not source_root.is_dir():
            continue
        for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
            yield source, root / source.relative_to(site)


def posix_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def is_authorized_routine_path(relative: str) -> bool:
    path = relative.replace("\\", "/").lstrip("./")
    if path in ROUTINE_WRITE_EXACT:
        return True
    if path.startswith("site/journal/") and path.endswith(".html"):
        return True
    if path.startswith("journal/") and path.endswith(".html"):
        return True
    if path in {"site/sitemap.xml", "sitemap.xml"}:
        return True
    return False


def classify_changed_paths(root: Path, changed: list[str]) -> tuple[list[str], list[str]]:
    authorized: list[str] = []
    unexpected: list[str] = []
    for raw in changed:
        relative = raw.replace("\\", "/").lstrip("./")
        if is_authorized_routine_path(relative):
            authorized.append(relative)
        else:
            unexpected.append(relative)
    return authorized, unexpected
