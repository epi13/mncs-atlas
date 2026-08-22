from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from journal_maintainer.config import load_config
from journal_maintainer.editorial import cluster_topics, meaningful_development, synthesize
from journal_maintainer.evidence.experiments import gather_experiments
from journal_maintainer.evidence.gather import _item_from_dict, gather_evidence
from journal_maintainer.models import CoveredInterval, SourceClass
from tests.helpers import evidence_item, make_atlas_tree, write_evidence


def _interval() -> CoveredInterval:
    return CoveredInterval(
        start=datetime(2026, 8, 21, tzinfo=timezone.utc),
        end=datetime(2026, 8, 21, 23, 59, tzinfo=timezone.utc),
    )


class EditorialTests(unittest.TestCase):
    def test_normal_weekly_story_is_not_a_changelog(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            evidence = write_evidence(
                Path(tmp) / "evidence.json",
                [
                    {
                        "source_class": "owning-repository",
                        "status": "available",
                        "consulted": True,
                        "items": [
                            evidence_item(
                                item_id="pr-8",
                                title="Define bounded Atlas Journal Maintainer workflow",
                                summary="Atlas now owns a recurring journal maintainer contract without becoming an authority layer.",
                                files=["docs/JOURNAL_MAINTAINER.md"],
                            ),
                            evidence_item(
                                item_id="pr-9",
                                title="Document the Family Record Spine and Concept Reconstruction Experiment flow",
                                summary="Producer-owned records stay in their native semantics; Commons indexes rather than owns truth.",
                                files=["docs/family-record-spine.md"],
                            ),
                            evidence_item(
                                item_id="deps",
                                title="chore(deps): bump urllib3",
                                summary="Routine dependency bump.",
                                signal=0.2,
                                noise=True,
                                files=["requirements.txt"],
                            ),
                        ],
                    },
                    {
                        "source_class": "commons",
                        "status": "unavailable",
                        "consulted": False,
                        "gap": "Commons not configured",
                        "items": [],
                    },
                    {
                        "source_class": "experiment",
                        "status": "unavailable",
                        "consulted": False,
                        "gap": "no snapshot",
                        "items": [],
                    },
                ],
            )
            config = load_config(root, evidence_file=evidence)
            sources, items, _repos = gather_evidence(config, _interval())
            clusters, draft = synthesize(
                items=items,
                sources=sources,
                covered=_interval(),
                previous=None,
                existing_entries=[],
                published=_interval().end_date,
            )
            self.assertTrue(meaningful_development(clusters, items))
            self.assertNotIn("37 commits", draft.lede.lower())
            self.assertIn("machine-maintained", draft.disclosure.lower())
            used = " ".join(item.title for cluster in clusters if not cluster.omitted for item in cluster.items)
            self.assertNotIn("bump urllib3", used)
            self.assertTrue(any("Journal" in cluster.title or "spine" in cluster.title.lower() for cluster in clusters if not cluster.omitted))

    def test_no_meaningful_activity_is_a_no_op(self) -> None:
        with TemporaryDirectory() as tmp:
            root = make_atlas_tree(Path(tmp))
            evidence = write_evidence(
                Path(tmp) / "quiet.json",
                [
                    {
                        "source_class": "owning-repository",
                        "status": "available",
                        "consulted": True,
                        "items": [
                            evidence_item(
                                item_id="fmt",
                                title="style: prettier",
                                summary="formatting only",
                                signal=0.1,
                                noise=True,
                                files=["src/foo.py"],
                                kind="commit",
                            )
                        ],
                    }
                ],
            )
            config = load_config(root, evidence_file=evidence)
            sources, items, _ = gather_evidence(config, _interval())
            clusters, _draft = synthesize(
                items=items,
                sources=sources,
                covered=_interval(),
                previous=None,
                existing_entries=[],
                published=_interval().end_date,
            )
            self.assertFalse(meaningful_development(clusters, items))

    def test_negative_results_are_preserved(self) -> None:
        item = _item_from_dict(
            evidence_item(
                item_id="fail",
                title="Experiment failed to reconstruct the tri-state lattice",
                summary="The language candidate could not express FAIL dominating UNKNOWN.",
                negative=True,
                kind="failure",
                repository="epi13/mncs-language",
                signal=9,
                files=["spec/result-lattice.md"],
            ),
            SourceClass.EXPERIMENT,
        )
        clusters = cluster_topics([item], None)
        self.assertTrue(any(cluster.negative and not cluster.omitted for cluster in clusters))

    def test_malformed_experiment_snapshot_is_a_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "experiments.json"
            bad.write_text("{not-json", encoding="utf-8")
            result = gather_experiments(bad, _interval())
            self.assertEqual(result.status.value, "malformed")
            self.assertIsNotNone(result.gap)

    def test_missing_commons_is_unavailable_not_invented(self) -> None:
        from journal_maintainer.evidence.commons import gather_commons

        result = gather_commons(base_url=None, interval=_interval())
        self.assertEqual(result.status.value, "unavailable")
        self.assertFalse(result.consulted)
        self.assertEqual(result.items, [])


if __name__ == "__main__":
    unittest.main()
