"""Authorized mutation surface and Pages mirror layout.

A routine Journal Maintainer publication may only change the journal
publication tree, journal discovery files required by Atlas publishing, and
the generated root compatibility mirrors of those canonical files.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import PathCheckResult

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
CANONICAL_ENTRY_RE = re.compile(ROUTINE_ENTRY_PATTERN)
MIRROR_ENTRY_RE = re.compile(MIRROR_ENTRY_PATTERN)


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


def diff_paths(root: Path, *, base: str, head: str = "HEAD") -> tuple[list[str], list[str]]:
    """Return complete base..head paths and status records.

    ``git diff`` against a working tree is insufficient for CI: a clean
    checkout may already contain all PR commits.  The explicit two-revision
    range also includes deletions and rename destinations.
    """
    result = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", "--find-copies", f"{base}...{head}"],
        cwd=root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"unable to inspect diff {base}...{head}")
    statuses: list[str] = []
    names: list[str] = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        status = fields[0]
        statuses.append(line)
        # For renames/copies, inspect both old and new paths.
        names.extend(field for field in fields[1:] if field)
    return sorted(set(names)), statuses


def verify_append_only(
    root: Path, *, base: str, head: str = "HEAD", changed: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Verify the routine mutation contract against committed history."""
    names, statuses = diff_paths(root, base=base, head=head)
    if changed is not None:
        names = sorted(set(changed))
    errors: list[str] = []
    canonical_entries = [name for name in names if CANONICAL_ENTRY_RE.match(name)]
    mirror_entries = [name for name in names if MIRROR_ENTRY_RE.match(name)]
    status_by_name: dict[str, str] = {}
    for record in statuses:
        fields = record.split("\t")
        if len(fields) >= 2:
            status_by_name[fields[1]] = fields[0]
            if len(fields) >= 3:
                status_by_name[fields[2]] = fields[0]
    new_canonical = [name for name in canonical_entries if status_by_name.get(name, "").startswith(("A", "C", "R"))]
    if len(new_canonical) != 1:
        errors.append(f"routine publication must add exactly one new canonical article (found {len(new_canonical)})")
    for name in canonical_entries:
        if name not in new_canonical:
            errors.append(f"historical journal article changed or deleted: {name}")
    if new_canonical:
        expected_mirror = new_canonical[0].replace("site/", "", 1)
        if expected_mirror not in mirror_entries:
            errors.append(f"generated mirror missing for new article: {expected_mirror}")
        for required in ("site/journal/index.html", "journal/index.html", "site/sitemap.xml", "sitemap.xml"):
            if required not in names:
                errors.append(f"routine publication is missing required discovery update: {required}")
    expected_mirror = new_canonical[0].replace("site/", "", 1) if new_canonical else None
    for name in mirror_entries:
        if name != expected_mirror:
            errors.append(f"historical journal mirror changed or deleted: {name}")
    allowed_support = {"site/journal/index.html", "journal/index.html", "site/sitemap.xml", "sitemap.xml"}
    for name in names:
        if name in allowed_support or name in canonical_entries or name in mirror_entries:
            continue
        if not is_authorized_routine_path(name):
            errors.append(f"unexpected path in routine diff: {name}")
    return not errors, errors


def check_diff(
    root: Path, *, base: str, head: str = "HEAD",
) -> PathCheckResult:
    changed, _ = diff_paths(root, base=base, head=head)
    authorized, unexpected = classify_changed_paths(root, changed)
    append_only, history_errors = verify_append_only(root, base=base, head=head, changed=changed)
    return PathCheckResult(
        allowed=not unexpected and append_only,
        changed=changed,
        unexpected=unexpected,
        authorized=authorized,
        base=base,
        head=head,
        append_only=append_only,
        history_errors=history_errors,
    )
