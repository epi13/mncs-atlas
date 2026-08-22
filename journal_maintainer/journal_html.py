"""Parse existing Development Journal HTML without rewriting it."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from .models import CoveredInterval, PreviousPublication
from .sanitize import scrub_text

ENTRY_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9-]+)\.html$")
NUMBER_RE = re.compile(r"(?:Journal|Development Journal)\s*[·•-]?\s*0*(\d+)", re.I)
META_RE = re.compile(
    r'<meta\s+[^>]*name=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\'][^>]*>',
    re.I,
)
META_RE_SWAP = re.compile(
    r'<meta\s+[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']([^"\']+)["\'][^>]*>',
    re.I,
)
TITLE_RE = re.compile(r"<h1>(.*?)</h1>", re.I | re.S)
CANONICAL_RE = re.compile(
    r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']',
    re.I,
)
PUBLISHED_RE = re.compile(r'article:published_time["\']\s+content=["\']([^"\']+)["\']', re.I)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._chunks.append(data)

    def text(self) -> str:
        return scrub_text(" ".join(self._chunks), limit=20000)


def _meta(html: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in META_RE.finditer(html):
        values[match.group(1).lower()] = match.group(2)
    for match in META_RE_SWAP.finditer(html):
        values[match.group(2).lower()] = match.group(1)
    return values


def parse_entry_filename(name: str) -> tuple[str, str] | None:
    match = ENTRY_NAME.match(name)
    if not match:
        return None
    return match.group(1), match.group(2)


def extract_visible_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def parse_journal_entry(path: Path) -> PreviousPublication | None:
    parsed_name = parse_entry_filename(path.name)
    if parsed_name is None:
        return None
    published_text, slug = parsed_name
    html = path.read_text(encoding="utf-8")
    meta = _meta(html)
    title_match = TITLE_RE.search(html)
    title = scrub_text(re.sub(r"<[^>]+>", "", title_match.group(1)) if title_match else slug, limit=200)
    number = None
    if meta.get("mncs:journal-number"):
        try:
            number = int(meta["mncs:journal-number"])
        except ValueError:
            number = None
    if number is None:
        match = NUMBER_RE.search(html)
        number = int(match.group(1)) if match else 0
    published = datetime.strptime(published_text, "%Y-%m-%d").date()
    if meta.get("article:published_time"):
        try:
            published = datetime.strptime(meta["article:published_time"][:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    else:
        published_meta = PUBLISHED_RE.search(html)
        if published_meta:
            try:
                published = datetime.strptime(published_meta.group(1)[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
    covered = None
    start_text = meta.get("mncs:covered-start")
    end_text = meta.get("mncs:covered-end")
    if start_text and end_text:
        try:
            start = datetime.strptime(start_text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.combine(
                datetime.strptime(end_text[:10], "%Y-%m-%d").date(),
                time(23, 59, 59),
                tzinfo=timezone.utc,
            )
            covered = CoveredInterval(start=start, end=end, previous_publication_id=None)
        except ValueError:
            covered = None
    machine = meta.get("mncs:maintainer") == "atlas-journal-maintainer" or "machine-maintained" in html.lower()
    canonical = meta.get("og:url") or ""
    canonical_match = CANONICAL_RE.search(html)
    if canonical_match:
        canonical = canonical_match.group(1)
    if not canonical:
        canonical = f"https://epi13.github.io/mncs-atlas/journal/{path.name}"
    return PreviousPublication(
        number=number,
        slug=slug,
        filename=path.name,
        title=title,
        published=published,
        covered=covered,
        machine_maintained=machine,
        canonical_url=canonical,
        path=str(path),
    )


def load_journal_entries(journal_dir: Path) -> list[PreviousPublication]:
    entries: list[PreviousPublication] = []
    if not journal_dir.is_dir():
        return entries
    for path in sorted(journal_dir.glob("*.html")):
        if path.name == "index.html":
            continue
        parsed = parse_journal_entry(path)
        if parsed is not None:
            entries.append(parsed)
    entries.sort(key=lambda item: (item.number, item.published, item.filename))
    return entries


def next_journal_number(entries: list[PreviousPublication]) -> int:
    if not entries:
        return 1
    return max(entry.number for entry in entries) + 1


def previous_successful_publication(entries: list[PreviousPublication]) -> PreviousPublication | None:
    if not entries:
        return None
    return max(entries, key=lambda item: (item.number, item.published, item.filename))


def interval_already_published(entries: list[PreviousPublication], key: str) -> PreviousPublication | None:
    for entry in entries:
        if entry.covered is not None and entry.covered.key == key:
            return entry
    return None


def uncovered_start(previous: PreviousPublication) -> datetime:
    """Start of the next uncovered interval: after the previous publication's covered end, or next UTC day."""
    if previous.covered is not None:
        return previous.covered.end + timedelta(seconds=1)
    published = datetime.combine(previous.published, time.min, tzinfo=timezone.utc)
    return published + timedelta(days=1)
