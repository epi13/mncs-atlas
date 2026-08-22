"""Assemble evidence from all adapters in contract order."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import MaintainerConfig, load_family_projects
from ..github_client import GitHubClient
from ..models import CoveredInterval, EvidenceItem, EvidenceSourceResult, SourceClass, SourceStatus, utcnow
from .commons import gather_commons
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
    for raw in raw_sources:
        source_class = SourceClass(raw.get("source_class"))
        status = SourceStatus(raw.get("status") or "available")
        source_items = [_item_from_dict(item, source_class) for item in raw.get("items") or []]
        sources.append(
            EvidenceSourceResult(
                source_class=source_class,
                status=status,
                consulted=bool(raw.get("consulted", True)),
                items=source_items,
                gap=raw.get("gap"),
                detail=raw.get("detail"),
            )
        )
        items.extend(source_items)
    repositories = sorted({item.repository for item in items if item.repository})
    return sources, items, repositories


def _item_from_dict(raw: dict, source_class: SourceClass) -> EvidenceItem:
    from ..models import EvidenceKind, EvidenceProvenance, parse_iso_datetime

    provenance_raw = raw.get("provenance") or {}
    return EvidenceItem(
        item_id=str(raw.get("item_id") or raw.get("title")),
        source_class=source_class,
        kind=EvidenceKind(raw.get("kind") or "unknown"),
        title=str(raw.get("title") or "untitled"),
        summary=str(raw.get("summary") or ""),
        provenance=EvidenceProvenance(
            source_class=source_class,
            locator=str(provenance_raw.get("locator") or "fixture"),
            retrieved_at=parse_iso_datetime(provenance_raw.get("retrieved_at")) or utcnow(),
            repository=provenance_raw.get("repository") or raw.get("repository"),
            record_id=provenance_raw.get("record_id"),
        ),
        occurred_at=parse_iso_datetime(raw.get("occurred_at")),
        repository=raw.get("repository"),
        project_id=raw.get("project_id"),
        url=raw.get("url"),
        labels=list(raw.get("labels") or []),
        files=list(raw.get("files") or []),
        signal=float(raw.get("signal") or 0),
        noise=bool(raw.get("noise")),
        negative=bool(raw.get("negative")),
        unresolved=bool(raw.get("unresolved")),
    )
