"""Journal Maintainer orchestration.

One implementation, multiple invocation surfaces (CLI, GitHub Actions,
MNCS Control). Editorial policy stays in Atlas.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .checkpoint import branch_for_interval, determine_checkpoint
from .config import MaintainerConfig, load_family_projects
from .editorial import meaningful_development, synthesize
from .evidence.gather import gather_evidence
from .gitops import (
    GitError,
    commit_authorized_paths,
    evaluate_auto_merge,
    open_or_update_pull_request,
    push_branch,
    run_git,
    try_enable_auto_merge,
)
from .github_client import GitHubClient
from .http import HttpError
from .journal_html import load_journal_entries
from .models import (
    AutoMergeEligibility,
    FailureState,
    JournalRun,
    PathCheckResult,
    PublicationEligibility,
    RunOutcome,
    SourceClass,
    SourceStatus,
    utcnow,
)
from .provenance import pull_request_body
from .publication import check_changed_paths, publish_to_site
from .render import render_entry
from .validate import validate_draft, validate_site


def execute_run(
    config: MaintainerConfig,
    *,
    now: datetime | None = None,
    dry_run: bool = True,
    publish: bool = False,
    output_dir: Path | None = None,
    github_client: GitHubClient | None = None,
    draft_file: Path | None = None,
    retry: bool = False,
) -> JournalRun:
    started = utcnow()
    moment = now or started
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    run = JournalRun(
        run_id=f"jm-{moment.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        started_at=started,
        outcome=RunOutcome.NORMAL,
    )
    checkpoint = determine_checkpoint(
        config.journal_dir,
        now=moment,
        retry_branch="retry" if retry else None,
    )
    run.previous = checkpoint.previous
    run.covered = checkpoint.covered
    run.notes.extend(checkpoint.notes or [])
    run.retry_of = checkpoint.existing_for_interval.publication_id if checkpoint.retry else None

    if checkpoint.outcome_hint == RunOutcome.ALREADY_PUBLISHED or checkpoint.covered is None:
        run.outcome = RunOutcome.ALREADY_PUBLISHED
        run.notes.append("No uncovered interval remains; succeeding as a no-op.")
        run.finished_at = utcnow()
        return run

    client = github_client or GitHubClient(config.github_token, api=config.github_api, user_agent=config.user_agent)
    sources, items, repositories = gather_evidence(config, checkpoint.covered, github_client=client)
    run.sources = sources
    run.items = items
    run.inspected_repositories = repositories or [
        f"{project.owner}/{project.repo}"
        for project in load_family_projects(config)
        if project.owner and project.repo
    ]
    run.evidence_gaps = [source.gap for source in sources if source.gap]

    github = run.source_status(SourceClass.OWNING_REPOSITORY)
    if github and github.status == SourceStatus.UNAVAILABLE:
        run.outcome = RunOutcome.FAILED
        run.failure = FailureState(
            code="EVIDENCE_UNAVAILABLE",
            message="Owning-repository evidence was unavailable; refusing to invent a journal narrative.",
        )
        run.finished_at = utcnow()
        return run

    existing = load_journal_entries(config.journal_dir)
    clusters, draft = synthesize(
        items=items,
        sources=sources,
        covered=checkpoint.covered,
        previous=checkpoint.previous,
        existing_entries=existing,
        published=checkpoint.covered.end_date,
        synthesizer=config.synthesizer,
        draft_file=draft_file,
    )
    run.clusters = clusters
    run.draft = draft
    run.omitted_uncertain = list(draft.omitted_topics)
    if draft.ambiguity:
        run.outcome = RunOutcome.AMBIGUOUS
        run.auto_merge = AutoMergeEligibility(False, [draft.ambiguity_reason or "ambiguous evidence"])
        run.publication = PublicationEligibility(False, ["material evidence ambiguity requires human review"])
        run.notes.append(draft.ambiguity_reason or "Ambiguous run; leaving unpublished.")
        run.finished_at = utcnow()
        return run

    if not meaningful_development(clusters, items) and config.synthesizer != "editor-draft" and draft_file is None:
        run.outcome = RunOutcome.NO_OP
        run.notes.append("No meaningful MNCS development justified a journal entry; succeeding without publication.")
        run.finished_at = utcnow()
        return run

    rendered = render_entry(draft, run)
    run.rendered = rendered
    draft_errors = validate_draft(draft, {entry.filename for entry in existing})
    if draft_errors:
        run.outcome = RunOutcome.FAILED
        run.failure = FailureState(code="INVALID_JOURNAL_OUTPUT", message="; ".join(draft_errors))
        run.finished_at = utcnow()
        return run

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / rendered.draft.filename).write_text(rendered.html, encoding="utf-8")
        (output_dir / "run.json").write_text(json.dumps(run.to_dict(), indent=2) + "\n", encoding="utf-8")

    if dry_run and not publish:
        run.outcome = checkpoint.outcome_hint
        run.publication = PublicationEligibility(False, ["dry-run; no repository mutation"])
        run.auto_merge = AutoMergeEligibility(False, ["dry-run"])
        run.validation = ["dry-run skipped live site mutation"]
        run.finished_at = utcnow()
        return run

    run.branch = branch_for_interval(checkpoint.covered)
    run.outcome = checkpoint.outcome_hint
    run.validation = [
        "python scripts/sync_pages_root.py --check",
        "python scripts/check_site.py",
        "journal_maintainer.validate.validate_journal",
    ]

    if not publish:
        publish_to_site(config, rendered)
        path_check = check_changed_paths(config.root)
        run.path_check = path_check
        if not path_check.allowed:
            run.outcome = RunOutcome.FAILED
            run.failure = FailureState(
                code="UNEXPECTED_PATHS",
                message="Refusing publication because unexpected paths changed: " + ", ".join(path_check.unexpected),
            )
            run.publication = PublicationEligibility(False, run.failure.message.splitlines())
            run.auto_merge = AutoMergeEligibility(False, ["unexpected changed paths"])
            run.finished_at = utcnow()
            return run

        site_errors = validate_site(config.root)
        if site_errors:
            run.outcome = RunOutcome.FAILED
            run.failure = FailureState(code="VALIDATION_FAILURE", message="; ".join(site_errors[:12]))
            run.publication = PublicationEligibility(False, site_errors[:12])
            run.auto_merge = AutoMergeEligibility(False, ["validation failed"])
            run.finished_at = utcnow()
            return run

        run.publication = PublicationEligibility(True, ["journal files written and validated"])
        run.auto_merge = evaluate_auto_merge(
            originated_from_maintainer=True,
            path_check=path_check,
            validation_ok=True,
            ambiguity=False,
            mergeable_state=None,
            reviews_request_changes=False,
            repo_allows_auto_merge=None,
            human_hold=False,
        )
        run.notes.append("Local publication prepared; PR creation skipped.")
        run.finished_at = utcnow()
        return run

    path_check = PathCheckResult(True, [], [], [])

    try:
        from dataclasses import replace
        import tempfile

        worktree = Path(tempfile.mkdtemp(prefix="atlas-journal-"))
        run_git(config.root, "fetch", "origin", config.base_branch, check=False)
        start_ref = f"origin/{config.base_branch}"
        if run_git(config.root, "rev-parse", "--verify", start_ref, check=False).returncode != 0:
            start_ref = config.base_branch
        existing_remote = run_git(config.root, "rev-parse", "--verify", f"origin/{run.branch}", check=False)
        if existing_remote.returncode == 0:
            start_ref = f"origin/{run.branch}"
        run_git(config.root, "worktree", "add", "-B", run.branch, str(worktree), start_ref)
        try:
            wt_config = replace(config, root=worktree)
            publish_to_site(wt_config, rendered)
            wt_paths = check_changed_paths(worktree)
            run.path_check = wt_paths
            if not wt_paths.allowed:
                raise GitError("worktree contained unexpected paths: " + ", ".join(wt_paths.unexpected))
            site_errors = validate_site(worktree)
            if site_errors:
                raise GitError("; ".join(site_errors[:12]))
            commit_authorized_paths(
                worktree,
                wt_paths.changed,
                f"journal: {draft.filename} ({checkpoint.covered.key})",
            )
            push_branch(worktree, run.branch)
        finally:
            run_git(config.root, "worktree", "remove", "--force", str(worktree), check=False)

        pull = open_or_update_pull_request(
            client,
            config,
            branch=run.branch,
            title=f"journal: {draft.title}",
            body=pull_request_body(run),
        )
        run.pull_request_url = pull.get("html_url")
        settings = {}
        try:
            settings = client.repo_settings(config.owner, config.atlas_repo)
        except HttpError:
            settings = {}
        allows = settings.get("allow_auto_merge")
        mergeable = pull.get("mergeable_state")
        run.auto_merge = evaluate_auto_merge(
            originated_from_maintainer=True,
            path_check=run.path_check or path_check,
            validation_ok=True,
            ambiguity=False,
            mergeable_state=str(mergeable) if mergeable else None,
            reviews_request_changes=False,
            repo_allows_auto_merge=bool(allows) if allows is not None else None,
            human_hold=False,
        )
        if run.auto_merge.eligible:
            enabled, detail = try_enable_auto_merge(client, pull)
            run.notes.append(detail)
            if not enabled:
                run.auto_merge = AutoMergeEligibility(
                    False,
                    run.auto_merge.reasons + [detail],
                    repository_permits_auto_merge=run.auto_merge.repository_permits_auto_merge,
                )
        elif allows is False:
            run.notes.append(
                "Repository auto-merge is disabled. Enable Settings → General → Pull Requests → Allow auto-merge."
            )
    except (GitError, HttpError, OSError) as error:
        run.outcome = RunOutcome.FAILED
        run.failure = FailureState(code="PUBLISH_FAILED", message=str(error))
    run.finished_at = utcnow()
    return run
