from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from journal_maintainer.config import load_config
from journal_maintainer.models import RunOutcome, SourceClass, SourceStatus
from journal_maintainer.render import render_entry
from journal_maintainer.run import execute_run
from journal_maintainer.validate import validate_draft, validate_journal
from tests.helpers import evidence_item, make_atlas_tree, write_evidence


NOW = datetime(2026, 8, 21, 19, 0, tzinfo=timezone.utc)


class RunTests(unittest.TestCase):
    def _run(self, root: Path, sources: list[dict], **kwargs):
        evidence = write_evidence(root / "evidence.json", sources)
        config = load_config(root, evidence_file=evidence)
        output = kwargs.pop("output_dir", root / "out")
        return execute_run(config, now=NOW, dry_run=True, output_dir=output, **kwargs)

    def test_normal_run_renders_machine_entry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            run = self._run(
                root,
                [
                    {
                        "source_class": "owning-repository",
                        "status": "available",
                        "consulted": True,
                        "items": [
                            evidence_item(
                                item_id="pr-8",
                                title="Define bounded Atlas Journal Maintainer workflow",
                                summary="Contract for a recurring machine-maintained journal without new authority.",
                                files=["docs/JOURNAL_MAINTAINER.md"],
                            ),
                            evidence_item(
                                item_id="pr-9",
                                title="Document the Family Record Spine",
                                summary="Producer-owned records connected by identity rather than a universal schema.",
                                files=["docs/family-record-spine.md"],
                            ),
                        ],
                    },
                    {"source_class": "commons", "status": "unavailable", "consulted": False, "gap": "unconfigured", "items": []},
                    {"source_class": "experiment", "status": "unavailable", "consulted": False, "gap": "unconfigured", "items": []},
                ],
            )
            self.assertNotEqual(run.outcome, RunOutcome.NO_OP)
            self.assertNotEqual(run.outcome, RunOutcome.FAILED)
            self.assertIsNotNone(run.draft)
            self.assertIsNotNone(run.rendered)
            self.assertIn("Atlas Journal Maintainer", run.rendered.html)
            self.assertIn("Non-normative", run.rendered.html)
            self.assertIn("mncs:covered-start", run.rendered.html)
            self.assertIn("machine-maintained", run.rendered.html.lower())
            self.assertTrue((root / "out" / run.draft.filename).is_file())
            self.assertEqual(run.draft.number, 2)
            errors = validate_draft(run.draft, set())
            self.assertEqual(errors, [])

    def test_quiet_week_is_no_op(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            run = self._run(
                root,
                [
                    {
                        "source_class": "owning-repository",
                        "status": "available",
                        "consulted": True,
                        "items": [
                            evidence_item(
                                item_id="typo",
                                title="docs: typo",
                                summary="fixed a typo",
                                signal=0.2,
                                noise=True,
                                kind="commit",
                            )
                        ],
                    }
                ],
            )
            self.assertEqual(run.outcome, RunOutcome.NO_OP)
            self.assertIsNone(run.pull_request_url)

    def test_unavailable_github_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            run = self._run(
                root,
                [
                    {
                        "source_class": "owning-repository",
                        "status": "unavailable",
                        "consulted": True,
                        "gap": "GitHub 401",
                        "items": [],
                    }
                ],
            )
            self.assertEqual(run.outcome, RunOutcome.FAILED)
            self.assertEqual(run.failure.code, "EVIDENCE_UNAVAILABLE")

    def test_already_published_interval_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            journal = root / "site" / "journal"
            source = (journal / "2026-08-20-starting-the-development-journal.html").read_text(encoding="utf-8")
            injected = source.replace(
                "<title>",
                '<meta name="mncs:journal-number" content="002">\n  <meta name="mncs:covered-start" content="2026-08-21">\n  <meta name="mncs:covered-end" content="2026-08-21">\n  <meta name="mncs:maintainer" content="atlas-journal-maintainer">\n  <title>',
            ).replace("Starting the MNCS Development Journal", "Covered interval already published")
            injected = injected.replace("Development Journal · 001", "Development Journal · 002")
            (journal / "2026-08-21-covered-interval-already-published.html").write_text(injected, encoding="utf-8")
            run = self._run(root, [{"source_class": "owning-repository", "status": "available", "items": []}])
            self.assertEqual(run.outcome, RunOutcome.ALREADY_PUBLISHED)

    def test_prepare_updates_index_and_mirror(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            evidence = write_evidence(
                root / "evidence.json",
                [
                    {
                        "source_class": "owning-repository",
                        "status": "available",
                        "consulted": True,
                        "items": [
                            evidence_item(
                                item_id="pr-8",
                                title="Define bounded Atlas Journal Maintainer workflow",
                                summary="Contract for a recurring machine-maintained journal.",
                                files=["docs/JOURNAL_MAINTAINER.md"],
                            ),
                            evidence_item(
                                item_id="pr-9",
                                title="Family Record Spine",
                                summary="Producer-owned records and CREs.",
                                files=["docs/family-record-spine.md"],
                            ),
                        ],
                    }
                ],
            )
            config = load_config(root, evidence_file=evidence)
            run = execute_run(config, now=NOW, dry_run=False, publish=False)
            self.assertIsNone(run.failure)
            self.assertIsNotNone(run.draft)
            entry = root / "site" / "journal" / run.draft.filename
            self.assertTrue(entry.is_file())
            index = (root / "site" / "journal" / "index.html").read_text(encoding="utf-8")
            self.assertIn(run.draft.filename, index)
            mirror = root / "journal" / run.draft.filename
            self.assertTrue(mirror.is_file())
            self.assertEqual(entry.read_bytes(), mirror.read_bytes())
            errors = validate_journal(root / "site" / "journal")
            self.assertEqual(errors, [])
            if run.path_check is not None:
                self.assertTrue(run.path_check.allowed)

    def test_github_unavailable_source_status_is_recorded(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            run = self._run(
                root,
                [
                    {
                        "source_class": "owning-repository",
                        "status": "unavailable",
                        "consulted": True,
                        "gap": "timeout",
                        "items": [],
                    }
                ],
            )
            source = run.source_status(SourceClass.OWNING_REPOSITORY)
            self.assertEqual(source.status, SourceStatus.UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
