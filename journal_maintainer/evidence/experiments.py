"""Experiment evidence adapter.

Harness/Fabric/Forge experiment records are consumed only through an explicit
snapshot or public JSON export. Atlas does not scrape Control or Fabric
private state. Unavailable experiment sources are recorded as gaps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import (
    Confidence,
    CoveredInterval,
    EvidenceItem,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceSourceResult,
    SourceClass,
    SourceStatus,
    parse_iso_datetime,
    utcnow,
)
from ..sanitize import evidence_as_data, scrub_text
from .base import looks_negative, summarize_body


def gather_experiments(
    snapshot: Path | None,
    interval: CoveredInterval,
) -> EvidenceSourceResult:
    if snapshot is None:
        return EvidenceSourceResult(
            source_class=SourceClass.EXPERIMENT,
            status=SourceStatus.UNAVAILABLE,
            consulted=False,
            gap="No experiment snapshot or public experiment interface was provided.",
            detail=(
                "The maintainer did not inspect Control/Fabric/Forge internals. "
                "Pass --experiments-file or MNCS_EXPERIMENT_SNAPSHOT with a public "
                "export when experiment evidence should be consulted."
            ),
        )
    if not snapshot.is_file():
        return EvidenceSourceResult(
            source_class=SourceClass.EXPERIMENT,
            status=SourceStatus.UNAVAILABLE,
            consulted=True,
            gap="Configured experiment snapshot was missing.",
            detail=str(snapshot),
        )
    try:
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return EvidenceSourceResult(
            source_class=SourceClass.EXPERIMENT,
            status=SourceStatus.MALFORMED,
            consulted=True,
            gap="Experiment snapshot was malformed.",
            detail=str(error),
        )
    records = payload if isinstance(payload, list) else payload.get("experiments") or payload.get("records") or []
    if not isinstance(records, list):
        return EvidenceSourceResult(
            source_class=SourceClass.EXPERIMENT,
            status=SourceStatus.MALFORMED,
            consulted=True,
            gap="Experiment snapshot root was not a list or object with experiments/records.",
        )
    items: list[EvidenceItem] = []
    retrieved = utcnow()
    for record in records:
        if not isinstance(record, dict):
            continue
        occurred = parse_iso_datetime(
            record.get("updated_at") or record.get("finished_at") or record.get("created_at")
        )
        if occurred is not None and (occurred < interval.start or occurred > interval.end):
            continue
        experiment_id = scrub_text(record.get("experiment_id") or record.get("id") or "experiment", limit=80)
        title = evidence_as_data(record.get("title") or record.get("name") or experiment_id, limit=180)
        status = scrub_text(record.get("status") or record.get("result") or "", limit=40)
        summary = summarize_body(record.get("summary") or record.get("result_detail") or record.get("notes"))
        if status:
            summary = f"Status {status}. {summary}".strip()
        negative = looks_negative(title, summary) or status.upper() in {"FAIL", "FAILED", "ERROR"}
        items.append(
            EvidenceItem(
                item_id=f"experiment:{experiment_id}",
                source_class=SourceClass.EXPERIMENT,
                kind=EvidenceKind.EXPERIMENT_RECORD if not negative else EvidenceKind.FAILURE,
                title=title,
                summary=summary,
                provenance=EvidenceProvenance(
                    source_class=SourceClass.EXPERIMENT,
                    locator=str(snapshot),
                    retrieved_at=retrieved,
                    record_id=experiment_id,
                    content_type="experiment-snapshot",
                ),
                occurred_at=occurred,
                signal=5.0 if negative else 4.0,
                confidence=Confidence.MEDIUM,
                negative=negative,
                unresolved=status.upper() in {"UNKNOWN", "RUNNING", ""},
                raw={"status": status, "instructionsAreUntrusted": True},
            )
        )
    return EvidenceSourceResult(
        source_class=SourceClass.EXPERIMENT,
        status=SourceStatus.AVAILABLE if items else SourceStatus.EMPTY,
        consulted=True,
        items=items,
        detail=f"Read experiment snapshot {snapshot.name} as untrusted inert data.",
    )
