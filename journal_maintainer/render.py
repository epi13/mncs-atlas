"""Render journal HTML matching the existing Atlas journal architecture."""

from __future__ import annotations

import json
import re
from datetime import date

from .editorial import format_pretty_date
from .models import CANONICAL_PAGES_URL, DraftEntry, JournalRun, MAINTAINER_IDENTITY, RenderedEntry
from .sanitize import escape_html

JOURNAL_INDEX = "index.html"


def render_entry(draft: DraftEntry, run: JournalRun | None = None) -> RenderedEntry:
    filename = draft.filename
    canonical = f"{CANONICAL_PAGES_URL}journal/{filename}"
    published_pretty = format_pretty_date(draft.published)
    covered = ""
    if draft.covered.start_date == draft.covered.end_date:
        covered = format_pretty_date(draft.covered.start_date)
    else:
        covered = f"{format_pretty_date(draft.covered.start_date)} – {format_pretty_date(draft.covered.end_date)}"
    provenance_json = ""
    if run is not None:
        provenance_json = (
            '\n  <script type="application/json" id="journal-maintainer-provenance">\n'
            f"{_inert_json(run, draft)}\n"
            "  </script>"
        )

    body_sections = []
    body_sections.append(
        f"""          <div class="journal-note journal-disclosure">
            <p class="card-kicker">Machine-maintained entry</p>
            <p>{escape_html(draft.disclosure)}</p>
          </div>"""
    )
    for paragraph in _split_lede(draft.lede):
        body_sections.append(f"          <p>{escape_html(paragraph)}</p>")
    for section in draft.sections:
        body_sections.append(f"          <h2>{escape_html(section.heading)}</h2>")
        for paragraph in section.paragraphs:
            if paragraph.startswith("The inspectable trail includes:"):
                body_sections.append(f"          <p>{escape_html(paragraph)}</p>")
            elif section.heading.lower().startswith("unresolved") and not paragraph.startswith("The interval"):
                body_sections.append(f"          <p>{escape_html(paragraph)}</p>")
            else:
                body_sections.append(f"          <p>{escape_html(paragraph)}</p>")
        if section.note:
            body_sections.append(
                f"""          <div class="journal-note">
            <p class="card-kicker">Note</p>
            <p>{escape_html(section.note)}</p>
          </div>"""
            )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape_html(draft.lede)}">
  <meta name="theme-color" content="#0b1020">
  <meta name="robots" content="index,follow">
  <meta property="og:title" content="{escape_html(draft.title)}">
  <meta property="og:description" content="{escape_html(draft.lede)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical}">
  <meta property="article:published_time" content="{draft.published.isoformat()}">
  <meta name="twitter:card" content="summary">
  <meta name="mncs:journal-number" content="{draft.number:03d}">
  <meta name="mncs:covered-start" content="{draft.covered.start_date.isoformat()}">
  <meta name="mncs:covered-end" content="{draft.covered.end_date.isoformat()}">
  <meta name="mncs:maintainer" content="{MAINTAINER_IDENTITY}">
  <meta name="mncs:non-normative" content="true">
  <meta name="author" content="Atlas Journal Maintainer">
  <title>{escape_html(draft.title)} — MNCS Atlas</title>
  <link rel="canonical" href="{canonical}">
  <link rel="stylesheet" href="../assets/styles.css">
  <link rel="stylesheet" href="../assets/journal.css">{provenance_json}
  <script defer src="../assets/app.js"></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>

  <header class="site-header">
    <div class="shell nav-wrap">
      <a class="brand" href="../" aria-label="MNCS Atlas home">
        <span class="brand-mark" aria-hidden="true">M</span>
        <span><strong>MNCS</strong> Atlas</span>
      </a>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
      <nav id="site-nav" class="site-nav" aria-label="Primary navigation">
        <a href="../">Atlas</a>
        <a href="index.html">Journal</a>
        <a href="../#architecture">Architecture</a>
        <a href="../#projects">Projects</a>
        <a href="https://github.com/epi13/mncs-atlas">GitHub</a>
      </nav>
    </div>
  </header>

  <main id="main">
    <article class="section journal-article">
      <div class="shell">
        <header class="journal-article-header">
          <p class="eyebrow">Development Journal · {draft.number:03d}</p>
          <div class="journal-meta">
            <span>{escape_html(published_pretty)}</span>
            <span>Covered {escape_html(covered)}</span>
            <span>Atlas Journal Maintainer</span>
            <span>Non-normative</span>
          </div>
          <h1>{escape_html(draft.title)}</h1>
          <p class="lede-small">{escape_html(draft.lede)}</p>
        </header>

        <div class="journal-article-body">
{chr(10).join(body_sections)}

          <div class="journal-back">
            <a class="text-link" href="index.html">← Back to the Development Journal</a>
          </div>
        </div>
      </div>
    </article>
  </main>

  <footer class="site-footer">
    <div class="shell footer-grid">
      <div>
        <strong>MNCS Development Journal</strong>
        <p>Dated field notes from the development of a machine-native research project family.</p>
        <p class="footer-links">
          <a href="../">Atlas</a>
          <a href="index.html">Journal</a>
          <a href="https://github.com/epi13/mncs-atlas">GitHub</a>
        </p>
      </div>
      <div>
        <p>Journal entries are non-normative and may describe ideas that later change.</p>
        <p>Apache-2.0 · <span id="year">{draft.published.year}</span></p>
      </div>
    </div>
  </footer>
</body>
</html>
"""
    return RenderedEntry(
        draft=draft,
        html=html,
        canonical_url=canonical,
        relative_path=f"site/journal/{filename}",
    )


def render_index(entries: list[tuple[str, str, str, date, int]], latest_href: str) -> str:
    cards = []
    for filename, title, summary, published, number in entries:
        cards.append(
            f"""          <a class="project-card" href="{escape_html(filename)}">
            <span class="project-type">{escape_html(format_pretty_date(published))} · Journal {number:03d}</span>
            <h3>{escape_html(title)}</h3>
            <p>{escape_html(summary)}</p>
            <span class="repo-link">Read entry ↗</span>
          </a>"""
        )
    card_html = "\n".join(cards) if cards else "          <p>No journal entries have been published yet.</p>"
    latest_label = "Read the latest entry" if entries else "Read the first entry"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="The MNCS Development Journal records the reasoning, experiments, failures, and architectural changes behind the Machine-Native Complexity Standard project family.">
  <meta name="theme-color" content="#0b1020">
  <meta name="robots" content="index,follow">
  <meta property="og:title" content="MNCS Development Journal — Atlas">
  <meta property="og:description" content="Dated notes from the development of the MNCS project family: decisions, experiments, failures, and changes in understanding.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{CANONICAL_PAGES_URL}journal/">
  <meta name="twitter:card" content="summary">
  <title>MNCS Development Journal — Atlas</title>
  <link rel="canonical" href="{CANONICAL_PAGES_URL}journal/">
  <link rel="stylesheet" href="../assets/styles.css">
  <link rel="stylesheet" href="../assets/journal.css">
  <script defer src="../assets/app.js"></script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>

  <header class="site-header">
    <div class="shell nav-wrap">
      <a class="brand" href="../" aria-label="MNCS Atlas home">
        <span class="brand-mark" aria-hidden="true">M</span>
        <span><strong>MNCS</strong> Atlas</span>
      </a>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav">Menu</button>
      <nav id="site-nav" class="site-nav" aria-label="Primary navigation">
        <a href="../">Atlas</a>
        <a href="index.html">Journal</a>
        <a href="../#architecture">Architecture</a>
        <a href="../#projects">Projects</a>
        <a href="https://github.com/epi13/mncs-atlas">GitHub</a>
      </nav>
    </div>
  </header>

  <main id="main">
    <section class="hero journal-hero">
      <div class="shell">
        <p class="eyebrow">MNCS Development Journal</p>
        <h1>Recording the work <span>while the reasoning is still fresh.</span></h1>
        <p class="lede">Atlas describes the MNCS project family as it currently stands. This journal records how it gets there: architectural decisions, experiments, failures, open questions, and changes in understanding as the system develops.</p>
        <div class="hero-actions">
          <a class="button primary" href="{escape_html(latest_href)}">{escape_html(latest_label)}</a>
          <a class="button ghost" href="../">Back to Atlas</a>
        </div>
      </div>
    </section>

    <section class="section section-soft">
      <div class="shell">
        <div class="section-heading compact">
          <p class="eyebrow">Entries</p>
          <h2>Dated snapshots of an experimental system in motion.</h2>
          <p>Entries describe the thinking at a particular point in time. Later experiments or specifications may supersede them.</p>
        </div>

        <div class="journal-list">
{card_html}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <div class="section-heading compact">
          <p class="eyebrow">What belongs here</p>
          <h2>The journal sits between Git history and formal documentation.</h2>
          <p>It preserves context that is important to the project but inappropriate to treat as specification authority.</p>
        </div>

        <div class="runtime-notes">
          <article>
            <p class="card-kicker">Decisions</p>
            <h3>Why an architecture changed</h3>
            <p>The tradeoffs, constraints, and observations behind a direction before the final result gets compressed into an RFC or implementation.</p>
          </article>
          <article>
            <p class="card-kicker">Experiments</p>
            <h3>What actually happened</h3>
            <p>Promising results, failures, surprising behavior, and the conclusions that changed the next experiment or design.</p>
          </article>
          <article>
            <p class="card-kicker">Open questions</p>
            <h3>Ideas before they harden</h3>
            <p>Machine-native concepts worth preserving even when they are incomplete, provisional, or likely to be revised.</p>
          </article>
        </div>

        <div class="callout">
          <div>
            <p class="card-kicker">Authority boundary</p>
            <h3>The journal is historical context, not governing truth.</h3>
            <p>MNCS and MNCDS specifications, accepted project contracts, and the current documentation of an owning repository remain authoritative. A journal entry is a dated record of reasoning, not a conformance rule.</p>
          </div>
          <div class="callout-actions">
            <a class="button primary" href="../#projects">Explore the project family</a>
          </div>
        </div>
      </div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="shell footer-grid">
      <div>
        <strong>MNCS Development Journal</strong>
        <p>Dated field notes from the development of a machine-native research project family.</p>
        <p class="footer-links">
          <a href="../">Atlas</a>
          <a href="index.html">Journal</a>
          <a href="https://github.com/epi13/mncs-atlas">GitHub</a>
        </p>
      </div>
      <div>
        <p>Journal entries are non-normative and may describe ideas that later change.</p>
        <p>Apache-2.0 · <span id="year">2026</span></p>
      </div>
    </div>
  </footer>
</body>
</html>
"""


def render_sitemap(home: str, entries: list[tuple[str, date]]) -> str:
    urls = [
        f"""  <url>
    <loc>{home}</loc>
  </url>""",
        f"""  <url>
    <loc>{home}journal/</loc>
    <lastmod>{max((item[1] for item in entries), default=date.today()).isoformat()}</lastmod>
  </url>""",
    ]
    for filename, published in entries:
        urls.append(
            f"""  <url>
    <loc>{home}journal/{filename}</loc>
    <lastmod>{published.isoformat()}</lastmod>
  </url>"""
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def _split_lede(lede: str) -> list[str]:
    return [lede] if lede else []


def _public_provenance(run: JournalRun, draft: DraftEntry) -> dict:
    payload = run.to_dict()
    payload.pop("items", None)
    if payload.get("previous") and isinstance(payload["previous"], dict):
        payload["previous"].pop("path", None)
    for cluster in payload.get("clusters") or []:
        if isinstance(cluster, dict):
            cluster.pop("summary", None)
    for source in payload.get("sources") or []:
        if isinstance(source, dict) and source.get("gap"):
            source["gap"] = _compact_gap(source["gap"])
            source["detail"] = source.get("detail") and _compact_gap(str(source["detail"]))
    payload["entry"] = {
        "number": draft.number,
        "filename": draft.filename,
        "covered": draft.covered.to_dict(),
    }
    return payload


def _compact_gap(text: str) -> str:
    if "HTTP 403" in text:
        return "GitHub returned HTTP 403 for some family repositories (commonly secondary rate-limit). Remaining retrieved evidence was used; missing repositories were not invented."
    return text[:400]


def _inert_json(run: JournalRun, draft: DraftEntry) -> str:
    payload = _public_provenance(run, draft)
    encoded = json.dumps(payload, indent=2, ensure_ascii=False)
    encoded = encoded.replace("</", "<\\/")
    if re.search(r"<script|javascript:", encoded, re.I):
        encoded = json.dumps({"error": "provenance contained unsafe content and was withheld"}, indent=2)
    return encoded
