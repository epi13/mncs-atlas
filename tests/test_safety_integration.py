from __future__ import annotations

import json
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from journal_maintainer.editorial import synthesize
from journal_maintainer.evidence.github import gather_github
from journal_maintainer.github_client import GitHubClient
from journal_maintainer.gitops import evaluate_auto_merge, evaluate_github_promotion
from journal_maintainer.http import HttpError
from journal_maintainer.models import CoveredInterval, FamilyProject, PathCheckResult
from journal_maintainer.paths import check_diff


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _repo(root: Path) -> tuple[Path, str]:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "tests")
    (root / "site/journal").mkdir(parents=True)
    (root / "site/journal/2026-08-20-old-entry.html").write_text("old", encoding="utf-8")
    (root / "site/journal/index.html").write_text("old index", encoding="utf-8")
    (root / "site/sitemap.xml").write_text("old sitemap", encoding="utf-8")
    (root / "journal").mkdir()
    (root / "journal/2026-08-20-old-entry.html").write_text("old", encoding="utf-8")
    (root / "journal/index.html").write_text("old index", encoding="utf-8")
    (root / "sitemap.xml").write_text("old sitemap", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root, _git(root, "rev-parse", "HEAD")


class SafetyIntegrationTests(unittest.TestCase):
    def test_clean_checkout_detects_committed_unauthorized_pr_diff(self) -> None:
        with TemporaryDirectory() as tmp:
            root, base = _repo(Path(tmp) / "repo")
            (root / "README.md").write_text("unauthorized", encoding="utf-8")
            _git(root, "add", "README.md")
            _git(root, "commit", "-qm", "forged")
            result = check_diff(root, base=base, head="HEAD")
            self.assertFalse(result.allowed)
            self.assertIn("README.md", result.unexpected)

    def test_old_entry_modification_and_deletion_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root, base = _repo(Path(tmp) / "repo")
            (root / "site/journal/2026-08-20-old-entry.html").write_text("rewritten", encoding="utf-8")
            (root / "journal/2026-08-20-old-entry.html").unlink()
            _git(root, "add", "-A")
            _git(root, "commit", "-qm", "historical correction")
            result = check_diff(root, base=base)
            self.assertFalse(result.append_only)
            self.assertTrue(any("historical journal article" in error for error in result.history_errors))

    def test_one_new_entry_index_sitemap_and_mirror_is_accepted(self) -> None:
        with TemporaryDirectory() as tmp:
            root, base = _repo(Path(tmp) / "repo")
            article = "2026-08-21-new-entry.html"
            (root / f"site/journal/{article}").write_text("new", encoding="utf-8")
            (root / f"journal/{article}").write_text("new", encoding="utf-8")
            for relative in ("site/journal/index.html", "journal/index.html", "site/sitemap.xml", "sitemap.xml"):
                (root / relative).write_text("updated", encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-qm", "routine journal")
            result = check_diff(root, base=base)
            self.assertTrue(result.allowed, result.history_errors)

    def test_unknown_mergeability_and_changed_head_block_promotion(self) -> None:
        path = PathCheckResult(True, [], [], [])
        result = evaluate_auto_merge(
            originated_from_maintainer=True,
            path_check=path,
            validation_ok=True,
            ambiguity=False,
            mergeable_state=None,
            reviews_request_changes=False,
            repo_allows_auto_merge=True,
            human_hold=False,
            required_checks_ok=None,
            head_sha="new",
            evaluated_head_sha="old",
        )
        self.assertFalse(result.eligible)
        self.assertTrue(any("UNKNOWN" in reason for reason in result.reasons))
        self.assertTrue(any("head SHA" in reason for reason in result.reasons))

    def test_editor_draft_requires_real_editor_and_bundle(self) -> None:
        interval = CoveredInterval(datetime(2026, 8, 21, tzinfo=timezone.utc), datetime(2026, 8, 21, 23, 59, tzinfo=timezone.utc))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps({"title": "fake", "sections": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                synthesize(items=[], sources=[], covered=interval, previous=None, existing_entries=[], published=interval.end_date, synthesizer="editor-draft", draft_file=path, evidence_bundle_id="eb-test")

    def test_total_github_outage_is_unavailable_but_partial_is_explicit(self) -> None:
        interval = CoveredInterval(datetime(2026, 8, 21, tzinfo=timezone.utc), datetime(2026, 8, 21, 23, 59, tzinfo=timezone.utc))
        project = FamilyProject("p", "p", "https://github.com/o/r", "o", "r", "role")

        class Outage:
            def __getattr__(self, _name):
                def fail(*_args, **_kwargs):
                    raise HttpError("HTTP_ERROR", "HTTP 503", status=503)
                return fail

        total = gather_github(Outage(), [project], interval)
        self.assertEqual(total.status.value, "unavailable")
        self.assertEqual(total.repository_statuses["o/r"].value, "unavailable")

        class Partial(Outage):
            def list_pulls(self, *_args, **_kwargs): return []
            def list_issues(self, *_args, **_kwargs): return []
            def list_commits(self, *_args, **_kwargs): return []
            def list_releases(self, *_args, **_kwargs): raise HttpError("HTTP_ERROR", "HTTP 503", status=503)

        partial = gather_github(Partial(), [project], interval)
        self.assertEqual(partial.status.value, "partial")
        self.assertEqual(partial.repository_statuses["o/r"].value, "partial")

    def test_requested_changes_and_hold_block_current_head(self) -> None:
        class Client:
            def pull_status(self, *_args, **_kwargs):
                return {"number": 1, "base": {"ref": "main"}, "head": {"sha": "abc", "ref": "journal/maintainer/x", "repo": {"full_name": "o/r"}}, "user": {"login": "maintainer[bot]", "type": "Bot"}, "labels": [{"name": "journal-maintainer"}, {"name": "human-hold"}], "mergeable_state": "clean"}
            def pull_reviews(self, *_args, **_kwargs): return [{"state": "CHANGES_REQUESTED"}]
            def check_runs(self, *_args, **_kwargs): return [{"status": "completed", "conclusion": "success"}]
            def combined_status(self, *_args, **_kwargs): return {"state": "success", "statuses": [{"context": "Atlas CI / site-integrity"}]}
            def branch_protection(self, *_args, **_kwargs): return {"required_status_checks": {"contexts": ["Atlas CI / site-integrity"]}}
            def repo_settings(self, *_args, **_kwargs): return {"allow_auto_merge": True}

        class Config:
            owner = "o"; atlas_repo = "r"

        result = evaluate_github_promotion(Client(), Config(), {"number": 1}, path_check=PathCheckResult(True, [], [], []), validation_ok=True, ambiguity=False)
        self.assertFalse(result.eligible)
        self.assertTrue(any("requested changes" in reason for reason in result.reasons))
        self.assertTrue(any("human hold" in reason for reason in result.reasons))

    def test_missing_or_pending_required_checks_block_promotion(self) -> None:
        class Client:
            def pull_status(self, *_args, **_kwargs):
                return {"number": 1, "base": {"ref": "main"}, "head": {"sha": "abc", "ref": "journal/maintainer/x", "repo": {"full_name": "o/r"}}, "user": {"login": "maintainer[bot]", "type": "Bot"}, "labels": [{"name": "journal-maintainer"}], "mergeable_state": "clean"}
            def pull_reviews(self, *_args, **_kwargs): return []
            def check_runs(self, *_args, **_kwargs): return [{"name": "Atlas CI / site-integrity", "status": "in_progress", "conclusion": None}]
            def combined_status(self, *_args, **_kwargs): return {"state": "pending", "statuses": []}
            def branch_protection(self, *_args, **_kwargs): return {"required_status_checks": {"contexts": ["Atlas CI / site-integrity"]}}
            def repo_settings(self, *_args, **_kwargs): return {"allow_auto_merge": True}

        class Config:
            owner = "o"; atlas_repo = "r"; base_branch = "main"

        result = evaluate_github_promotion(Client(), Config(), {"number": 1}, path_check=PathCheckResult(True, [], [], []), validation_ok=True, ambiguity=False)
        self.assertFalse(result.eligible)
        self.assertTrue(any("required Atlas checks" in reason for reason in result.reasons))

    def test_maintainer_label_and_branch_do_not_forge_app_provenance(self) -> None:
        from journal_maintainer.gitops import verify_maintainer_provenance
        pull = {"head": {"sha": "abc", "ref": "journal/maintainer/forged", "repo": {"full_name": "o/r"}}, "user": {"login": "human"}}
        self.assertFalse(verify_maintainer_provenance(pull, owner="o", repo="r", branch="journal/maintainer/forged"))

    def test_github_pagination_covers_delayed_active_repository(self) -> None:
        seen_pages: list[str] = []
        def fetcher(url, **_kwargs):
            page = parse_qs(urlparse(url).query).get("page", ["1"])[0]
            seen_pages.append(page)
            return ([{"sha": str(index)} for index in range(100)] if page == "1" else [{"sha": "last"}])
        client = GitHubClient("token", fetcher=fetcher)
        interval = CoveredInterval(datetime(2026, 8, 1, tzinfo=timezone.utc), datetime(2026, 8, 21, 23, 59, tzinfo=timezone.utc))
        records = client.list_commits("o", "r", since=interval.start, until=interval.end)
        self.assertEqual(len(records), 101)
        self.assertEqual(seen_pages, ["1", "2"])


if __name__ == "__main__":
    unittest.main()
