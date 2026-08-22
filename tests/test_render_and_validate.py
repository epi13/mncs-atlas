from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from journal_maintainer.journal_html import load_journal_entries, parse_journal_entry
from journal_maintainer.models import CoveredInterval, DraftEntry, DraftSection, JournalRun, RunOutcome
from journal_maintainer.paths import classify_changed_paths
from journal_maintainer.render import render_entry, render_index, render_sitemap
from journal_maintainer.validate import validate_draft, validate_journal
from tests.helpers import ROOT, make_atlas_tree


class RenderAndValidateTests(unittest.TestCase):
    def test_parses_existing_opening_entry(self) -> None:
        path = ROOT / "site" / "journal" / "2026-08-20-starting-the-development-journal.html"
        parsed = parse_journal_entry(path)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.number, 1)
        self.assertEqual(parsed.published.isoformat(), "2026-08-20")
        self.assertFalse(parsed.machine_maintained)
        self.assertIn("starting-the-development-journal", parsed.canonical_url)

    def test_duplicate_numbers_and_filenames_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            journal = root / "site" / "journal"
            original = journal / "2026-08-20-starting-the-development-journal.html"
            duplicate = journal / "2026-08-21-starting-the-development-journal.html"
            duplicate.write_bytes(original.read_bytes())
            errors = validate_journal(journal)
            self.assertTrue(any("duplicate journal numbers" in error for error in errors))

    def test_rendered_article_has_required_metadata(self) -> None:
        covered = CoveredInterval(
            start=datetime(2026, 8, 21, tzinfo=timezone.utc),
            end=datetime(2026, 8, 21, 23, 59, tzinfo=timezone.utc),
        )
        draft = DraftEntry(
            number=2,
            title="Family record spine, and the journal maintainer",
            slug="family-record-spine-and-the-journal-maintainer",
            lede="The project started turning developmental history into a machine-native journal.",
            sections=[
                DraftSection("What moved", ["The Journal Maintainer contract landed, still non-normative."]),
                DraftSection("What this entry is not", ["It is not a specification."]),
            ],
            disclosure="This entry was synthesized by the Atlas Journal Maintainer from inspectable MNCS project evidence. It is a dated developmental record, not a specification.",
            covered=covered,
            published=date(2026, 8, 21),
        )
        run = JournalRun("jm-test", datetime(2026, 8, 21, tzinfo=timezone.utc), RunOutcome.NORMAL, covered=covered)
        rendered = render_entry(draft, run)
        self.assertIn('name="mncs:journal-number" content="002"', rendered.html)
        self.assertIn("machine-maintained", rendered.html.lower())
        self.assertIn("Non-normative", rendered.html)
        self.assertIn("skip-link", rendered.html)
        self.assertIn("viewport", rendered.html)
        self.assertIn("journal-maintainer-provenance", rendered.html)
        self.assertEqual(validate_draft(draft, set()), [])

    def test_index_and_sitemap_include_new_entry(self) -> None:
        html = render_index(
            [
                ("2026-08-21-notes.html", "Notes", "A later entry.", date(2026, 8, 21), 2),
                ("2026-08-20-starting-the-development-journal.html", "Starting", "Opening.", date(2026, 8, 20), 1),
            ],
            "2026-08-21-notes.html",
        )
        self.assertIn("2026-08-21-notes.html", html)
        self.assertIn("Read the latest entry", html)
        sitemap = render_sitemap("https://epi13.github.io/mncs-atlas/", [("2026-08-21-notes.html", date(2026, 8, 21))])
        self.assertIn("journal/2026-08-21-notes.html", sitemap)

    def test_invalid_filename_is_caught(self) -> None:
        with TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            journal.mkdir()
            (journal / "notes.html").write_text("<html><h1>bad</h1></html>", encoding="utf-8")
            (journal / "index.html").write_text("<html></html>", encoding="utf-8")
            errors = validate_journal(journal)
            self.assertTrue(any("invalid journal filename" in error for error in errors))

    def test_unexpected_changed_path_detected_independently(self) -> None:
        authorized, unexpected = classify_changed_paths(Path("."), ["site/journal/x.html", "README.md"])
        self.assertEqual(unexpected, ["README.md"])
        self.assertEqual(authorized, ["site/journal/x.html"])


if __name__ == "__main__":
    unittest.main()
