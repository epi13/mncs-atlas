"""Assemble evidence from all adapters in contract order."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import MaintainerConfig, load_family_projects
from ..github_client import GitHubClient
from ..models import CoveredInterval, EvidenceItem, EvidenceSourceResult, SourceClass, SourceStatus, utcnow
from .commons import gather_commons
from .control_context import gather_control_context
from .conversation import gather_hints
from .experiments import gather_experiments
from .github import gather_github
from .journal import gather_previous_journal


def gather_evidence(
    config: MaintainerConfig,
    interval: CoveredInterval,
    *,
    github_client: GitHubClient | None = None,
) -> tuple[list[EvidenceSourceResult], list[EvidenceItem], list[str]]:
    if config.evidence_file:
        return _from_fixture(config.evidence_file, interval)

    projects = load_family_projects(config)
    client = github_client
    if client is None and (config.github_token or config.github_api):
        client = GitHubClient(config.github_token, api=config.github_api, user_agent=config.user_agent)

    sources = [
        gather_github(client, projects, interval),
        # Control journal context enriches the record with bounded local
        # operator evidence. It never substitutes for owning-repository
        # retrieval completeness.
        gather_control_context(config.journal_context_file, interval, projects=projects),
        gather_experiments(config.experiments_file, interval),
        gather_commons(
            base_url=config.commons_url,
            interval=interval,
            allow_http=config.commons_allow_http,
        ),
        gather_previous_journal(config.journal_dir),
        gather_hints(config.hints_file),
    ]
    items: list[EvidenceItem] = []
    repositories: list[str] = []
    for source in sources:
        items.extend(source.items)
        if source.source_class == SourceClass.OWNING_REPOSITORY:
            repositories.extend(sorted({item.repository for item in source.items if item.repository}))
    return sources, items, repositories


def _from_fixture(path: Path, interval: CoveredInterval) -> tuple[list[EvidenceSourceResult], list[EvidenceItem], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources") or []
    sources: list[EvidenceSourceResult] = []
    items: list[EvidenceItem] = []
    # A recorded EvidenceBundle (as written to output-dir/evidence-bundle.json)
    # carries its items at the top level rather than inside each source. This
    # makes the exact editor handoff replayable: the same bundle file can be
    # fed back through --evidence-file with --draft-file so bundle identity,
    # interval, and evidence IDs stay stable between collection and draft
    # validation.
    bundle_mode = bool(raw_sources) and all(
        isinstance(raw, dict) and not raw.get("items") for raw in raw_sources
    ) and isinstance(payload.get("items"), list)
    grouped: dict[str, list[EvidenceItem]] = {}
    if bundle_mode:
        for raw in payload.get("items") or []:
            if not isinstance(raw, dict):
                continue
            source_class = SourceClass(raw.get("source_class"))
            grouped.setdefault(_bundle_group_key(raw), []).append(_item_from_dict(raw, source_class))
    for raw in raw_sources:
        source_class = SourceClass(raw.get("source_class"))
        status = SourceStatus(raw.get("status") or "available")
        if bundle_mode:
            source_items = grouped.get(str(source_class.value), [])
            repository_statuses = {
                name: SourceStatus(value)
                for name, value in (raw.get("repository_statuses") or {}).items()
            }
        else:
            source_items = [_item_from_dict(item, source_class) for item in raw.get("items") or []]
            repository_statuses = {}
        sources.append(
            EvidenceSourceResult(
                source_class=source_class,
                status=status,
                consulted=bool(raw.get("consulted", True)),
                items=source_items,
                gap=raw.get("gap"),
                detail=raw.get("detail"),
                repository_statuses=repository_statuses,
            )
        )
        items.extend(source_items)
    repositories = sorted({item.repository for item in items if item.repository})
    return sources, items, repositories


def _bundle_group_key(raw: dict) -> str:
    """Group a recorded bundle item under the source that collected it.

    Control journal-context items can be mapped onto EXPERIMENT/COMMONS item
    classes while their provenance stays with the operator-context source;
    provenance is therefore the faithful grouping key.
    """

    provenance = raw.get("provenance")
    if isinstance(provenance, dict) and provenance.get("source_class"):
        return str(provenance["source_class"])
    return str(raw.get("source_class"))


def _item_from_dict(raw: dict, source_class: SourceClass) -> EvidenceItem:
    from ..models import Confidence, EvidenceKind, EvidenceProvenance, parse_iso_datetime

    provenance_raw = raw.get("provenance") or {}
    return EvidenceItem(
        item_id=str(raw.get("item_id") or raw.get("title")),
        source_class=SourceClass(raw.get("source_class") or source_class.value),
        kind=EvidenceKind(raw.get("kind") or "unknown"),
        title=str(raw.get("title") or "untitled"),
        summary=str(raw.get("summary") or ""),
        provenance=EvidenceProvenance(
            source_class=SourceClass(provenance_raw.get("source_class") or raw.get("source_class") or source_class.value),
            locator=str(provenance_raw.get("locator") or "fixture"),
            retrieved_at=parse_iso_datetime(provenance_raw.get("retrieved_at")) or utcnow(),
            repository=provenance_raw.get("repository") or raw.get("repository"),
            record_id=provenance_raw.get("record_id"),
            content_type=provenance_raw.get("content_type") or "text",
            untrusted=bool(provenance_raw.get("untrusted", True)),
        ),
        occurred_at=parse_iso_datetime(raw.get("occurred_at")),
        repository=raw.get("repository"),
        project_id=raw.get("project_id"),
        url=raw.get("url"),
        labels=list(raw.get("labels") or []),
        files=list(raw.get("files") or []),
        signal=float(raw.get("signal") or 0),
        noise=bool(raw.get("noise")),
        confidence=Confidence(raw.get("confidence") or "medium"),
        negative=bool(raw.get("negative")),
        unresolved=bool(raw.get("unresolved")),
    )
