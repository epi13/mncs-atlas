"""MNCS Control journal-context adapter (bounded local operator context).

Control exposes ``journal_context_collect`` over MCP and persists an immutable
bundle with schema ``mncs-control.journal-context.v1``. The operator/editor
exports that bundle to a file and hands it to this maintainer via
``--journal-context-file`` / ``MNCS_JOURNAL_CONTEXT_FILE``.

Boundaries preserved here:

- Atlas never opens Control private state, Fabric sockets, Forge state, or the
  Commons store; it reads only the exported public bundle contract.
- Every item is untrusted inert data. Summaries are re-scrubbed locally so
  instruction-like text cannot act as instructions even if Control redaction
  missed a pattern.
- Missing or malformed bundles are recorded explicitly; nothing is invented.
- Control-provided evidence never overrides owning-repository retrieval
  completeness. It enriches the record (local-only Git work, durable
  experiment state, execution/evaluation references) without claiming that
  remote history was retrievable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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
from ..sanitize import evidence_as_data

_BUNDLE_ID = re.compile(r"^jctx-[0-9a-f]{32}$")
_MAX_ITEMS = 400

# When a bundle exceeds the item bound, keep the highest-journal-value
# classes rather than whichever rows happened to come back first.
_SOURCE_PRIORITY = (
    "experiments",
    "local_repositories",
    "working_trees",
    "commons",
    "fabric",
    "forge",
    "local_notes",
    "control_activity",
)

# Control-side source classes mapped onto Atlas evidence classes. Everything
# stays inside the exported bundle contract; no Control internals are imported.
_KIND_BY_CONTROL_SOURCE = {
    "fabric": EvidenceKind.EXECUTION_REFERENCE,
    "forge": EvidenceKind.EVALUATION_REFERENCE,
}
_SIGNAL_BASE = {
    "local_repositories": 3.0,
    "working_trees": 2.5,
    "experiments": 4.0,
    "commons": 3.5,
    "fabric": 3.0,
    "forge": 3.0,
    "control_activity": 1.5,
    "local_notes": 2.0,
}


def gather_control_context(
    bundle_path: Path | None,
    interval: CoveredInterval,
    *,
    projects: list[FamilyProject] | None = None,
) -> EvidenceSourceResult:
    if bundle_path is None:
        return EvidenceSourceResult(
            source_class=SourceClass.OPERATOR_CONTEXT,
            status=SourceStatus.UNAVAILABLE,
            consulted=False,
            gap="No MNCS Control journal-context bundle was provided.",
            detail=(
                "Local operator context (local-only Git work, uncommitted state, "
                "durable experiments, Fabric/Forge references, redacted Control "
                "activity, local notes) was not consulted. Export a "
                "mncs-control.journal-context.v1 bundle and pass "
                "--journal-context-file to include it."
            ),
        )
    if not bundle_path.is_file():
        return EvidenceSourceResult(
            source_class=SourceClass.OPERATOR_CONTEXT,
            status=SourceStatus.UNAVAILABLE,
            consulted=True,
            gap="Configured MNCS Control journal-context bundle was missing.",
            detail=str(bundle_path),
        )
    try:
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return EvidenceSourceResult(
            source_class=SourceClass.OPERATOR_CONTEXT,
            status=SourceStatus.MALFORMED,
            consulted=True,
            gap="MNCS Control journal-context bundle was malformed.",
            detail=str(error),
        )
    error = _bundle_problem(payload)
    if error is not None:
        return EvidenceSourceResult(
            source_class=SourceClass.OPERATOR_CONTEXT,
            status=SourceStatus.MALFORMED,
            consulted=True,
            gap=error,
            detail=str(bundle_path),
        )
    assert isinstance(payload, dict)
    bundle_id = str(payload.get("bundle_id"))
    raw_items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
    if len(raw_items) > _MAX_ITEMS:
        priority = {name: index for index, name in enumerate(_SOURCE_PRIORITY)}
        raw_items = sorted(
            raw_items,
            key=lambda item: (
                priority.get(str(item.get("source_class") or ""), len(priority)),
                str(item.get("occurred_at") or ""),
            ),
        )
        truncated_for_bound = len(payload.get("items")) - _MAX_ITEMS
    else:
        truncated_for_bound = 0
    repo_by_name = _repo_by_name(projects or [])
    items: list[EvidenceItem] = []
    skipped_out_of_interval = 0
    retrieved_at = utcnow()
    for raw in raw_items[:_MAX_ITEMS]:
        occurred = parse_iso_datetime(str(raw.get("occurred_at") or "") or None)
        if occurred is not None and (occurred < interval.start or occurred > interval.end):
            skipped_out_of_interval += 1
            continue
        mapped = _map_item(raw, occurred=occurred, retrieved_at=retrieved_at, repo_lookup=repo_by_name)
        if mapped is not None:
            items.append(mapped)
    status = SourceStatus.AVAILABLE if items else SourceStatus.EMPTY
    detail = (
        f"Read MNCS Control journal-context bundle {bundle_id} as untrusted inert data"
        f" ({len(raw_items)} bundle items, {len(items)} in interval,"
        f" {skipped_out_of_interval} outside interval"
        + (f", {truncated_for_bound} low-priority items beyond the adapter bound" if truncated_for_bound else "")
        + ")."
    )
    return EvidenceSourceResult(
        source_class=SourceClass.OPERATOR_CONTEXT,
        status=status,
        consulted=True,
        items=items,
        detail=detail,
        gap=None if items else "Control journal-context bundle contained no items in the covered interval.",
    )


def _bundle_problem(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "Journal-context bundle root was not an object."
    schema = str(payload.get("schema") or "")
    if not schema.startswith("mncs-control.journal-context.v"):
        return "Journal-context bundle schema was not mncs-control.journal-context.v1."
    bundle_id = str(payload.get("bundle_id") or "")
    if not _BUNDLE_ID.match(bundle_id):
        return "Journal-context bundle_id is missing or malformed."
    if not isinstance(payload.get("items"), list):
        return "Journal-context bundle has no items list."
    return None


def _repo_by_name(projects: list[FamilyProject]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for project in projects:
        if project.owner and project.repo:
            mapping[project.repo.lower()] = f"{project.owner}/{project.repo}"
            mapping[str(project.project_id).lower()] = f"{project.owner}/{project.repo}"
    return mapping


def _map_item(
    raw: dict[str, Any],
    *,
    occurred,
    retrieved_at,
    repo_lookup: dict[str, str],
) -> EvidenceItem | None:
    control_source = str(raw.get("source_class") or "").strip()
    if not control_source:
        return None
    evidence_id = str(raw.get("evidence_id") or "").strip()
    if not evidence_id:
        return None
    project = str(raw.get("project")) if isinstance(raw.get("project"), str) else None
    title = evidence_as_data(_title_from_summary(str(raw.get("summary") or "")), limit=140)
    summary = evidence_as_data(str(raw.get("summary") or ""), limit=700)
    negative = bool(raw.get("negative"))
    unresolved = bool(raw.get("unresolved"))
    local_only = bool(raw.get("local_only"))
    confidence_value = str(raw.get("confidence") or "MEDIUM").upper()

    if control_source == "experiments":
        source_class = SourceClass.EXPERIMENT
        kind = EvidenceKind.FAILURE if negative else EvidenceKind.EXPERIMENT_RECORD
    elif control_source == "commons":
        source_class = SourceClass.COMMONS
        kind = EvidenceKind.COMMONS_RECORD
    else:
        source_class = SourceClass.OPERATOR_CONTEXT
        kind = _KIND_BY_CONTROL_SOURCE.get(control_source, EvidenceKind.LOCAL_GIT_EVIDENCE)

    signal = _SIGNAL_BASE.get(control_source, 2.0)
    if local_only:
        # Local-only work is invisible to GitHub retrieval; preserving it is
        # precisely the point of this surface.
        signal += 2.0
    if negative:
        signal += 1.0
    if unresolved:
        signal += 0.5

    if confidence_value == "HIGH":
        confidence = Confidence.MEDIUM
    elif confidence_value == "UNKNOWN":
        confidence = Confidence.UNKNOWN
    else:
        confidence = Confidence.LOW

    repository = repo_lookup.get(project.lower()) if project else None
    development_state = str(raw.get("development_state") or "recorded")
    locator = str(raw.get("locator") or evidence_id)[:512]
    return EvidenceItem(
        item_id=evidence_id,
        source_class=source_class,
        kind=kind,
        title=title or evidence_id,
        summary=summary,
        provenance=EvidenceProvenance(
            source_class=SourceClass.OPERATOR_CONTEXT,
            locator=f"mncs-control:{locator}",
            retrieved_at=retrieved_at,
            repository=repository,
            record_id=str(raw.get("content_hash") or evidence_id)[:80],
            content_type="mncs-control-journal-context",
        ),
        occurred_at=occurred,
        repository=repository,
        project_id=project,
        labels=[development_state, *(["local-only"] if local_only else [])],
        signal=signal,
        confidence=confidence,
        negative=negative,
        unresolved=unresolved,
        raw={
            "control_bundle_item": True,
            "control_source_class": control_source,
            "authority": str(raw.get("authority") or ""),
            "redacted": bool(raw.get("redacted", True)),
            "instructionsAreUntrusted": True,
        },
    )


def _title_from_summary(summary: str) -> str:
    """Derive a short neutral label; never treat summary text as instructions."""

    for separator in ("\n", "; ", ". "):
        if separator in summary:
            candidate = summary.split(separator, 1)[0].strip()
            if len(candidate) >= 12:
                return candidate
    return summary.strip()
