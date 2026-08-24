"""GitHub family-repository evidence."""

from __future__ import annotations

from datetime import datetime

from ..github_client import GitHubClient
from ..http import HttpError
from ..models import (
    Confidence,
    CoveredInterval,
    EvidenceItem,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceSourceResult,
    FamilyProject,
    SourceClass,
    SourceStatus,
    parse_iso_datetime,
    utcnow,
)
from ..sanitize import evidence_as_data, is_noise_title, safe_url, scrub_text
from .base import classify_files, confidence_from_score, looks_negative, score_item, summarize_body


def gather_github(
    client: GitHubClient | None,
    projects: list[FamilyProject],
    interval: CoveredInterval,
) -> EvidenceSourceResult:
    if client is None:
        return EvidenceSourceResult(
            source_class=SourceClass.OWNING_REPOSITORY,
            status=SourceStatus.UNAVAILABLE,
            consulted=False,
            gap="GitHub client was not configured.",
            detail="No GitHub token/client was supplied. Repository evidence was not inspected.",
        )
    items: list[EvidenceItem] = []
    errors: list[str] = []
    repository_statuses: dict[str, SourceStatus] = {}
    retrieved = utcnow()
    for project in projects:
        if not project.owner or not project.repo:
            continue
        repo_full = f"{project.owner}/{project.repo}"
        pulls: list[dict] = []
        issues: list[dict] = []
        commits: list[dict] = []
        releases: list[dict] = []
        endpoint_errors: list[str] = []
        try:
            pulls = client.list_pulls(project.owner, project.repo, state="all", per_page=50)
        except HttpError as error:
            message = f"{repo_full} pulls: {error}"; errors.append(message); endpoint_errors.append(message)
        try:
            issues = client.list_issues(project.owner, project.repo, state="all", per_page=20)
        except HttpError as error:
            message = f"{repo_full} issues: {error}"; errors.append(message); endpoint_errors.append(message)
        try:
            commits = client.list_commits(project.owner, project.repo, since=interval.start, until=interval.end)
        except HttpError as error:
            message = f"{repo_full} commits: {error}"; errors.append(message); endpoint_errors.append(message)
        try:
            releases = client.list_releases(project.owner, project.repo)
        except HttpError as error:
            message = f"{repo_full} releases: {error}"; errors.append(message); endpoint_errors.append(message)
        records_present = bool(pulls or issues or commits or releases)
        if len(endpoint_errors) == 4:
            repository_statuses[repo_full] = SourceStatus.UNAVAILABLE
        elif endpoint_errors:
            repository_statuses[repo_full] = SourceStatus.PARTIAL
        elif records_present:
            repository_statuses[repo_full] = SourceStatus.AVAILABLE
        else:
            repository_statuses[repo_full] = SourceStatus.EMPTY
        if not pulls and not commits and not issues and not releases:
            continue
        merged = []
        open_prs = []
        for raw in pulls:
            merged_at = parse_iso_datetime(raw.get("merged_at"))
            updated = parse_iso_datetime(raw.get("updated_at"))
            if merged_at and interval.start <= merged_at <= interval.end:
                merged.append(raw)
            elif raw.get("state") == "open" and updated and interval.start <= updated <= interval.end:
                open_prs.append(raw)
        issues = [
            raw
            for raw in issues
            if (occurred := parse_iso_datetime(raw.get("updated_at") or raw.get("closed_at")))
            and interval.start <= occurred <= interval.end
        ]

        for raw in merged:
            item = _from_issue(
                raw,
                project=project,
                kind=EvidenceKind.MERGED_PR,
                retrieved=retrieved,
                files=_maybe_files(client, project, raw),
            )
            if item:
                items.append(item)
        for raw in open_prs:
            if raw.get("pull_request", {}).get("merged_at"):
                continue
            item = _from_issue(
                raw,
                project=project,
                kind=EvidenceKind.OPEN_PR,
                retrieved=retrieved,
                files=_maybe_files(client, project, raw),
            )
            if item:
                items.append(item)
        for raw in issues:
            if raw.get("pull_request"):
                continue
            item = _from_issue(raw, project=project, kind=EvidenceKind.ISSUE, retrieved=retrieved)
            if item and (item.signal >= 3 or item.unresolved or item.negative):
                items.append(item)
        for raw in commits:
            item = _from_commit(raw, project=project, retrieved=retrieved)
            if item and not item.noise and not item.title.lower().startswith("merge pull request"):
                items.append(item)
        for raw in releases:
            published = parse_iso_datetime(raw.get("published_at") or raw.get("created_at"))
            if published is None or published < interval.start or published > interval.end:
                continue
            title = scrub_text(raw.get("name") or raw.get("tag_name") or "release", limit=180)
            items.append(
                EvidenceItem(
                    item_id=f"release:{repo_full}:{raw.get('id')}",
                    source_class=SourceClass.OWNING_REPOSITORY,
                    kind=EvidenceKind.RELEASE,
                    title=title,
                    summary=summarize_body(raw.get("body")),
                    provenance=EvidenceProvenance(
                        source_class=SourceClass.OWNING_REPOSITORY,
                        locator=str(raw.get("html_url") or repo_full),
                        retrieved_at=retrieved,
                        repository=repo_full,
                        record_id=str(raw.get("tag_name") or raw.get("id")),
                    ),
                    occurred_at=published,
                    repository=repo_full,
                    project_id=project.project_id,
                    url=safe_url(raw.get("html_url")),
                    signal=4.0,
                    confidence=Confidence.HIGH,
                )
            )

    repo_count = len(repository_statuses)
    unavailable_count = sum(status == SourceStatus.UNAVAILABLE for status in repository_statuses.values())
    if repo_count and unavailable_count == repo_count:
        return EvidenceSourceResult(
            source_class=SourceClass.OWNING_REPOSITORY,
            status=SourceStatus.UNAVAILABLE,
            consulted=True,
            gap="GitHub family evidence could not be retrieved.",
            detail="; ".join(errors[:8]),
            repository_statuses=repository_statuses,
        )
    if errors:
        status = SourceStatus.PARTIAL
    else:
        status = SourceStatus.AVAILABLE if items else SourceStatus.EMPTY
    gap = None
    if errors:
        names = sorted({error.split()[0] for error in errors if error})
        if any("403" in error for error in errors):
            gap = "GitHub HTTP 403 for some repositories: " + ", ".join(names[:8])
        else:
            gap = "Some repositories could not be inspected: " + "; ".join(errors[:4])
    return EvidenceSourceResult(
        source_class=SourceClass.OWNING_REPOSITORY,
        status=status,
        consulted=True,
        items=_dedupe(items),
        gap=gap,
        detail=f"Inspected {len(projects)} Atlas-mapped repositories." if not gap else gap,
        repository_statuses=repository_statuses,
    )


def _maybe_files(client: GitHubClient, project: FamilyProject, raw: dict) -> list[str]:
    number = raw.get("number")
    if not isinstance(number, int) or not project.owner or not project.repo:
        return []
    # Only fetch files for likely-high-signal PRs to keep runs bounded.
    title = str(raw.get("title") or "")
    if is_noise_title(title):
        return []
    try:
        details = client.pull_file_details(project.owner, project.repo, number)[:80]
        raw["_file_details"] = [
            {"filename": detail.get("filename"), "patch": scrub_text(detail.get("patch"), limit=1200)}
            for detail in details if isinstance(detail, dict)
        ]
        return [scrub_text(detail.get("filename"), limit=200) for detail in details if detail.get("filename")]
    except HttpError:
        return []


def _from_issue(
    raw: dict,
    *,
    project: FamilyProject,
    kind: EvidenceKind,
    retrieved: datetime,
    files: list[str] | None = None,
) -> EvidenceItem | None:
    number = raw.get("number")
    title = evidence_as_data(raw.get("title"), limit=180)
    if not title or not number:
        return None
    files = files or []
    labels = [
        scrub_text(label.get("name") if isinstance(label, dict) else label, limit=40)
        for label in (raw.get("labels") or [])
    ]
    # Triage summaries stay short. Raw patches live in the evidence bundle;
    # only a tightly bounded hint of documentation changes reaches prose.
    summary = summarize_body(raw.get("body"), limit=280)
    file_details = raw.get("_file_details") or []
    doc_excerpts = [
        f"{detail.get('filename')}: {scrub_text(detail.get('patch'), limit=240)}"
        for detail in file_details
        if isinstance(detail, dict) and detail.get("patch") and str(detail.get("filename", "")).lower().endswith((".md", ".rst", ".txt"))
    ]
    if doc_excerpts:
        summary = (summary + " Doc changes (untrusted evidence): " + " | ".join(doc_excerpts[:2]))[:900]
    path_kind = classify_files(files)
    if path_kind is not None and kind in {EvidenceKind.MERGED_PR, EvidenceKind.OPEN_PR}:
        kind = path_kind
    score, noise = score_item(title, summary, files, labels)
    repo_full = f"{project.owner}/{project.repo}"
    nested = raw.get("pull_request") if isinstance(raw.get("pull_request"), dict) else {}
    occurred = (
        parse_iso_datetime(raw.get("merged_at"))
        or parse_iso_datetime(nested.get("merged_at"))
        or parse_iso_datetime(raw.get("closed_at"))
        or parse_iso_datetime(raw.get("updated_at"))
    )
    return EvidenceItem(
        item_id=f"{kind.value}:{repo_full}:{number}",
        source_class=SourceClass.OWNING_REPOSITORY,
        kind=kind,
        title=title,
        summary=summary,
        provenance=EvidenceProvenance(
            source_class=SourceClass.OWNING_REPOSITORY,
            locator=str(raw.get("html_url") or ""),
            retrieved_at=retrieved,
            repository=repo_full,
            record_id=str(number),
        ),
        occurred_at=occurred,
        repository=repo_full,
        project_id=project.project_id,
        url=safe_url(raw.get("html_url")),
        labels=labels,
        files=files,
        signal=score,
        noise=noise,
        confidence=confidence_from_score(score, source_complete=True),
        negative=looks_negative(title, summary),
        unresolved=kind == EvidenceKind.OPEN_PR or raw.get("state") == "open",
        raw={"number": number, "state": raw.get("state")},
    )


def _from_commit(raw: dict, *, project: FamilyProject, retrieved: datetime) -> EvidenceItem | None:
    commit = raw.get("commit") if isinstance(raw.get("commit"), dict) else {}
    message = evidence_as_data(commit.get("message"), limit=240)
    if not message:
        return None
    title = message.split("\n", 1)[0]
    sha = str(raw.get("sha") or "")[:12]
    repo_full = f"{project.owner}/{project.repo}"
    score, noise = score_item(title, message, [], [])
    occurred = parse_iso_datetime((commit.get("committer") or {}).get("date") if isinstance(commit.get("committer"), dict) else None)
    return EvidenceItem(
        item_id=f"commit:{repo_full}:{sha}",
        source_class=SourceClass.OWNING_REPOSITORY,
        kind=EvidenceKind.COMMIT,
        title=title,
        summary=summarize_body(message),
        provenance=EvidenceProvenance(
            source_class=SourceClass.OWNING_REPOSITORY,
            locator=str(raw.get("html_url") or sha),
            retrieved_at=retrieved,
            repository=repo_full,
            record_id=sha,
        ),
        occurred_at=occurred,
        repository=repo_full,
        project_id=project.project_id,
        url=safe_url(raw.get("html_url")),
        signal=score,
        noise=noise or is_noise_title(title),
        confidence=confidence_from_score(score, source_complete=True),
        negative=looks_negative(title, message),
    )


def _dedupe(items: list[EvidenceItem]) -> list[EvidenceItem]:
    seen: set[str] = set()
    unique: list[EvidenceItem] = []
    for item in sorted(items, key=lambda candidate: (-candidate.signal, candidate.item_id)):
        if item.item_id in seen:
            continue
        seen.add(item.item_id)
        unique.append(item)
    return unique
