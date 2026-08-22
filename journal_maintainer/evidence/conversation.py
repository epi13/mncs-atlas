"""Optional conversation-derived hints.

Hints may identify likely topics. They are never the sole source for a
concrete technical claim when inspectable project evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import (
    Confidence,
    EvidenceItem,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceSourceResult,
    SourceClass,
    SourceStatus,
    utcnow,
)
from ..sanitize import evidence_as_data, scrub_text


def gather_hints(path: Path | None) -> EvidenceSourceResult:
    if path is None:
        return EvidenceSourceResult(
            source_class=SourceClass.CONVERSATION_HINT,
            status=SourceStatus.SKIPPED,
            consulted=False,
            detail="No conversation-hint file was supplied.",
        )
    if not path.is_file():
        return EvidenceSourceResult(
            source_class=SourceClass.CONVERSATION_HINT,
            status=SourceStatus.UNAVAILABLE,
            consulted=True,
            gap="Configured hints file was missing.",
            detail=str(path),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return EvidenceSourceResult(
            source_class=SourceClass.CONVERSATION_HINT,
            status=SourceStatus.MALFORMED,
            consulted=True,
            gap="Conversation hints were malformed.",
            detail=str(error),
        )
    records = payload if isinstance(payload, list) else payload.get("hints") or []
    if not isinstance(records, list):
        return EvidenceSourceResult(
            source_class=SourceClass.CONVERSATION_HINT,
            status=SourceStatus.MALFORMED,
            consulted=True,
            gap="Hints root was not a list or object with hints.",
        )
    items: list[EvidenceItem] = []
    retrieved = utcnow()
    for index, record in enumerate(records):
        if isinstance(record, str):
            title = evidence_as_data(record, limit=180)
            summary = ""
        elif isinstance(record, dict):
            title = evidence_as_data(record.get("title") or record.get("topic") or f"hint-{index}", limit=180)
            summary = evidence_as_data(record.get("summary") or record.get("text") or "", limit=400)
        else:
            continue
        items.append(
            EvidenceItem(
                item_id=f"hint:{index}:{scrub_text(title, limit=40)}",
                source_class=SourceClass.CONVERSATION_HINT,
                kind=EvidenceKind.HINT,
                title=title,
                summary=summary,
                provenance=EvidenceProvenance(
                    source_class=SourceClass.CONVERSATION_HINT,
                    locator=str(path),
                    retrieved_at=retrieved,
                    record_id=str(index),
                ),
                signal=1.5,
                confidence=Confidence.LOW,
                unresolved=True,
            )
        )
    return EvidenceSourceResult(
        source_class=SourceClass.CONVERSATION_HINT,
        status=SourceStatus.AVAILABLE if items else SourceStatus.EMPTY,
        consulted=True,
        items=items,
        detail="Conversation hints were treated as untrusted topic suggestions, not technical fact.",
    )
