"""Write canonical journal files and synchronize the Pages root mirror."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import MaintainerConfig
from .journal_html import load_journal_entries
from .models import CANONICAL_PAGES_URL, PathCheckResult, RenderedEntry
from .paths import classify_changed_paths, posix_relative
from .render import render_index, render_sitemap


def publish_to_site(config: MaintainerConfig, rendered: RenderedEntry) -> list[Path]:
    journal_dir = config.journal_dir
    journal_dir.mkdir(parents=True, exist_ok=True)
    entry_path = journal_dir / rendered.draft.filename
    entry_path.write_text(rendered.html, encoding="utf-8")

    entries = load_journal_entries(journal_dir)
    cards: list[tuple[str, str, str, object, int]] = []
    sitemap_entries: list[tuple[str, object]] = []
    for entry in sorted(entries, key=lambda item: (item.number, item.published, item.filename), reverse=True):
        parsed = Path(entry.path)
        html = parsed.read_text(encoding="utf-8")
        summary = _index_summary(html, entry.title)
        cards.append((entry.filename, entry.title, summary, entry.published, entry.number))
        sitemap_entries.append((entry.filename, entry.published))

    latest = cards[0][0] if cards else "index.html"
    index_html = render_index(cards, latest)
    index_path = journal_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    sitemap_entries.sort(key=lambda item: item[1])
    sitemap = render_sitemap(CANONICAL_PAGES_URL, sitemap_entries)
    config.sitemap.write_text(sitemap, encoding="utf-8")

    _sync_pages_root(config.root)
    written = [entry_path, index_path, config.sitemap]
    return written


def _index_summary(html: str, fallback: str) -> str:
    from html.parser import HTMLParser

    class LedeParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self._in = False
            self.text = ""

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            values = dict(attrs)
            if tag == "p" and values.get("class") == "lede-small":
                self._in = True
            if tag == "meta" and values.get("name") == "description" and values.get("content"):
                if not self.text:
                    self.text = values["content"]

        def handle_endtag(self, tag: str) -> None:
            if tag == "p":
                self._in = False

        def handle_data(self, data: str) -> None:
            if self._in:
                self.text += data

    parser = LedeParser()
    parser.feed(html)
    text = " ".join(parser.text.split())
    if len(text) > 240:
        text = text[:237].rstrip() + "…"
    return text or fallback


def _sync_pages_root(root: Path) -> None:
    script = root / "scripts" / "sync_pages_root.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=root)


def git_changed_paths(root: Path, base: str | None = None) -> list[str]:
    commands = [["git", "diff", "--name-only"], ["git", "diff", "--name-only", "--cached"]]
    if base:
        commands.append(["git", "diff", "--name-only", base])
    names: set[str] = set()
    for command in commands:
        result = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                names.add(line)
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if untracked.returncode == 0:
        for line in untracked.stdout.splitlines():
            line = line.strip()
            if line:
                names.add(line)
    return sorted(names)


def check_changed_paths(root: Path, changed: list[str] | None = None) -> PathCheckResult:
    paths = changed if changed is not None else git_changed_paths(root)
    authorized, unexpected = classify_changed_paths(root, paths)
    return PathCheckResult(
        allowed=not unexpected,
        changed=paths,
        unexpected=unexpected,
        authorized=authorized,
    )


def relative_written(root: Path, paths: list[Path]) -> list[str]:
    return [posix_relative(root, path) for path in paths]
