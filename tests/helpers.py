"""Shared test helpers for the Journal Maintainer."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The synthetic opening entry used by test trees. Tests must not depend on how
# many entries the live site has already published, or every real publication
# would break CI assumptions.
OPENING_FILENAME = "2026-08-20-starting-the-development-journal.html"
OPENING_TITLE = "Starting the MNCS Development Journal"
OPENING_DATE = date(2026, 8, 20)


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _opening_entry_html() -> str:
    canonical = f"https://epi13.github.io/mncs-atlas/journal/{OPENING_FILENAME}"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="mncs:journal-number" content="1">
  <meta property="og:title" content="{OPENING_TITLE}">
  <meta property="og:type" content="article">
  <meta property="article:published_time" content="{OPENING_DATE.isoformat()}">
  <link rel="canonical" href="{canonical}">
  <title>{OPENING_TITLE} — MNCS Atlas</title>
</head>
<body>
  <h1>{OPENING_TITLE}</h1>
  <p>This Non-normative opening entry explains why the development journal exists and will be maintained as a dated record, not a specification. Journal · 001</p>
</body>
</html>
"""


def _index_html(entries: list[tuple[str, str, int]]) -> str:
    cards = []
    for filename, title, number in entries:
        cards.append(
            f"""          <a class="project-card" href="{filename}">
            <span class="project-type">Journal {number:03d}</span>
            <h3>{title}</h3>
          </a>"""
        )
    body = "\n".join(cards) if cards else "          <p>No journal entries have been published yet.</p>"
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Journal — MNCS Atlas</title></head>
<body>
  <main id="main">
    <section>
{body}
    </section>
  </main>
</body>
</html>
"""


def _sitemap_xml(entries: list[tuple[str, date]]) -> str:
    home = "https://epi13.github.io/mncs-atlas/"
    urls = [f"  <url><loc>{home}</loc></url>", f"  <url><loc>{home}journal/</loc></url>"]
    for filename, published in entries:
        urls.append(f"  <url><loc>{home}journal/{filename}</loc><lastmod>{published.isoformat()}</lastmod></url>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def make_atlas_tree(tmp: Path, *, with_opening_journal: bool = True) -> Path:
    """Build a controlled Atlas tree for tests.

    Site infrastructure is copied from the repository, but journal content is
    synthesized so tests stay independent of the number of entries that have
    actually been published.
    """

    shutil.copytree(ROOT / "site", tmp / "site")
    # Drop whatever journal history the live checkout currently has.
    for directory in (tmp / "site" / "journal", ROOT / "journal"):
        pass
    for relative in ("site/journal", "journal"):
        journal_dir = tmp / relative
        journal_dir.mkdir(parents=True, exist_ok=True)
        for path in journal_dir.glob("*.html"):
            path.unlink()
        (journal_dir / "index.html").unlink(missing_ok=True)
    (tmp / "sitemap.xml").unlink(missing_ok=True)
    (tmp / "site" / "sitemap.xml").unlink(missing_ok=True)

    entries: list[tuple[str, str, int]] = []
    sitemap_entries: list[tuple[str, date]] = []
    if with_opening_journal:
        html = _opening_entry_html()
        write(tmp / "site" / "journal" / OPENING_FILENAME, html)
        write(tmp / "journal" / OPENING_FILENAME, html)
        entries.append((OPENING_FILENAME, OPENING_TITLE, 1))
        sitemap_entries.append((OPENING_FILENAME, OPENING_DATE))

    index = _index_html(entries)
    sitemap = _sitemap_xml(sitemap_entries)
    write(tmp / "site" / "journal" / "index.html", index)
    write(tmp / "journal" / "index.html", index)
    write(tmp / "site" / "sitemap.xml", sitemap)
    write(tmp / "sitemap.xml", sitemap)

    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts" / "check_site.py", tmp / "scripts" / "check_site.py")
    shutil.copy2(ROOT / "scripts" / "sync_pages_root.py", tmp / "scripts" / "sync_pages_root.py")
    for relative in (
        "mncs/atlas-json-scan.mncs",
        "mncs/atlas-json-projection.mncs",
        "mncs/atlas-model.mncs",
        "mncs/mncs-language.lock.json",
        "tests/fixtures/atlas-model-corpus.json",
    ):
        destination = tmp / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
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
