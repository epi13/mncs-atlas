from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from journal_maintainer.checkpoint import branch_for_interval, determine_checkpoint
from journal_maintainer.models import RunOutcome
from tests.helpers import make_atlas_tree


class CheckpointTests(unittest.TestCase):
    def test_opening_journal_is_the_first_checkpoint(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            now = datetime(2026, 8, 21, 18, 0, tzinfo=timezone.utc)
            checkpoint = determine_checkpoint(root / "site" / "journal", now=now)
            self.assertIsNotNone(checkpoint.previous)
            self.assertEqual(checkpoint.previous.number, 1)
            self.assertEqual(checkpoint.covered.start_date.isoformat(), "2026-08-21")
            self.assertEqual(checkpoint.covered.end_date.isoformat(), "2026-08-21")
            self.assertEqual(checkpoint.outcome_hint, RunOutcome.FIRST_RUN)
            self.assertEqual(branch_for_interval(checkpoint.covered), "journal/maintainer/2026-08-21-2026-08-21")

    def test_first_run_without_entries(self) -> None:
        with TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            journal.mkdir()
            checkpoint = determine_checkpoint(journal, now=datetime(2026, 8, 21, tzinfo=timezone.utc))
            self.assertIsNone(checkpoint.previous)
            self.assertEqual(checkpoint.outcome_hint, RunOutcome.FIRST_RUN)

    def test_delayed_run_uses_previous_publication_not_seven_days(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            now = datetime(2026, 9, 10, tzinfo=timezone.utc)
            checkpoint = determine_checkpoint(root / "site" / "journal", now=now)
            self.assertTrue(checkpoint.covered.delayed)
            self.assertEqual(checkpoint.outcome_hint, RunOutcome.DELAYED)
            self.assertEqual(checkpoint.covered.days, 21)

    def test_duplicate_covered_period_is_already_published(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            journal = root / "site" / "journal"
            html = (journal / "2026-08-20-starting-the-development-journal.html").read_text(encoding="utf-8")
            html = html.replace(
                '<meta property="og:type" content="article">',
                '<meta property="og:type" content="article">\n  <meta name="mncs:journal-number" content="001">\n  <meta name="mncs:covered-start" content="2026-08-21">\n  <meta name="mncs:covered-end" content="2026-08-21">\n  <meta name="mncs:maintainer" content="atlas-journal-maintainer">',
            )
            (journal / "2026-08-21-family-record-spine.html").write_text(html.replace("001", "002").replace("Starting the MNCS Development Journal", "Later entry"), encoding="utf-8")
            now = datetime(2026, 8, 21, 20, 0, tzinfo=timezone.utc)
            checkpoint = determine_checkpoint(journal, now=now)
            self.assertEqual(checkpoint.outcome_hint, RunOutcome.ALREADY_PUBLISHED)

    def test_retry_flag_marks_retry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            now = datetime(2026, 8, 22, tzinfo=timezone.utc)
            checkpoint = determine_checkpoint(root / "site" / "journal", now=now, retry_branch="retry")
            self.assertTrue(checkpoint.retry)
            self.assertEqual(checkpoint.outcome_hint, RunOutcome.RETRY)


if __name__ == "__main__":
    unittest.main()
