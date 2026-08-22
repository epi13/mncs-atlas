"""Journal Maintainer and site validation."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

from .journal_html import ENTRY_NAME, load_journal_entries
from .models import CANONICAL_PAGES_URL, DraftEntry
from .paths import MIRROR_PATHS, MIRROR_TREES
from .sanitize import slugify


def validate_site(root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(_run_script(root, "scripts/sync_pages_root.py", ["--check"]))
    errors.extend(_run_script(root, "scripts/check_site.py"))
    errors.extend(validate_journal(root / "site" / "journal"))
    errors.extend(_validate_mirrors(root))
    return errors


def validate_journal(journal_dir: Path) -> list[str]:
    errors: list[str] = []
    if not journal_dir.is_dir():
        return ["missing site/journal directory"]
    entries = load_journal_entries(journal_dir)
    names = [path.name for path in journal_dir.glob("*.html") if path.name != "index.html"]
    for name in names:
        if ENTRY_NAME.match(name) is None:
            errors.append(f"invalid journal filename: {name}")
    numbers = [entry.number for entry in entries if entry.number]
    duplicates = [str(number) for number, count in Counter(numbers).items() if count > 1]
    if duplicates:
        errors.append("duplicate journal numbers: " + ", ".join(duplicates))
    covered_keys = [entry.covered.key for entry in entries if entry.covered is not None]
    duplicate_keys = [key for key, count in Counter(covered_keys).items() if count > 1]
    if duplicate_keys:
        errors.append("duplicate covered periods: " + ", ".join(duplicate_keys))
    ordered = sorted(entries, key=lambda item: (item.number, item.published, item.filename))
    if ordered != entries and entries:
        # load_journal_entries already sorts; compare publication chronology vs numbers.
        pass
    previous_number = 0
    previous_date = None
    for entry in ordered:
        if entry.number and entry.number < previous_number:
            errors.append(f"journal numbers are not nondecreasing: {entry.filename}")
        if previous_date and entry.published < previous_date and entry.number >= previous_number:
            errors.append(f"journal dates recede at {entry.filename}")
        previous_number = max(previous_number, entry.number)
        previous_date = entry.published
        if not entry.canonical_url.startswith(CANONICAL_PAGES_URL + "journal/"):
            errors.append(f"{entry.filename} has unexpected canonical URL")
        html = Path(entry.path).read_text(encoding="utf-8")
        if "Non-normative" not in html:
            errors.append(f"{entry.filename} is missing non-normative labeling")
        if entry.machine_maintained:
            if "Atlas Journal Maintainer" not in html or "machine-maintained" not in html.lower():
                errors.append(f"{entry.filename} is missing machine-maintained disclosure")
            if 'name="mncs:covered-start"' not in html or 'name="mncs:covered-end"' not in html:
                errors.append(f"{entry.filename} is missing covered-period metadata")
        if f'href="{entry.filename}"' not in (journal_dir / "index.html").read_text(encoding="utf-8"):
            errors.append(f"journal index does not list {entry.filename}")
    return errors


def validate_draft(draft: DraftEntry, existing_slugs: set[str]) -> list[str]:
    errors: list[str] = []
    if draft.number < 1:
        errors.append("journal number must be positive")
    if slugify(draft.slug) != draft.slug:
        errors.append("journal slug is not normalized")
    if draft.filename in existing_slugs:
        errors.append(f"duplicate journal filename {draft.filename}")
    if not draft.sections:
        errors.append("draft has no sections")
    if "non-normative" not in draft.disclosure.lower() and "not a specification" not in draft.disclosure.lower():
        errors.append("draft disclosure does not mark the entry as non-normative")
    if draft.machine_maintained and "Atlas Journal Maintainer" not in draft.disclosure and "machine-maintained" not in draft.disclosure.lower():
        errors.append("machine-maintained draft is missing disclosure")
    return errors


def _validate_mirrors(root: Path) -> list[str]:
    errors: list[str] = []
    site = root / "site"
    for relative in MIRROR_PATHS:
        source = site / relative
        target = root / relative
        if source.is_file() and target.is_file() and source.read_bytes() != target.read_bytes():
            errors.append(f"stale root mirror: {relative}")
    for tree in MIRROR_TREES:
        source_root = site / tree
        if not source_root.is_dir():
            continue
        for source in source_root.rglob("*"):
            if not source.is_file():
                continue
            target = root / source.relative_to(site)
            if not target.is_file() or source.read_bytes() != target.read_bytes():
                errors.append(f"stale root mirror: {source.relative_to(site).as_posix()}")
    return errors


def _run_script(root: Path, relative: str, extra: list[str] | None = None) -> list[str]:
    command = [sys.executable, str(root / relative), *(extra or [])]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True)
    if result.returncode == 0:
        return []
    output = (result.stdout or "") + (result.stderr or "")
    lines = [line.lstrip("- ").strip() for line in output.splitlines() if line.strip()]
    return lines or [f"{relative} failed"]
