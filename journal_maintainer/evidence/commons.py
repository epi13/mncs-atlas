"""Commons adapter over the public Agent Exchange / remote client contract.

Atlas never opens the Commons backing store. If no public URL is configured,
the source is recorded as unavailable rather than faked.
"""

from __future__ import annotations

from typing import Any

from ..http import HttpError, join_url, request_json
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


def gather_commons(
    *,
    base_url: str | None,
    interval: CoveredInterval,
    allow_http: bool = False,
    fetcher=request_json,
) -> EvidenceSourceResult:
    if not base_url:
        return EvidenceSourceResult(
            source_class=SourceClass.COMMONS,
            status=SourceStatus.UNAVAILABLE,
            consulted=False,
            gap="Commons public interface was not configured.",
            detail=(
                "No MNCS_COMMONS_URL was provided. The maintainer did not open a "
                "Commons store and did not invent Commons records."
            ),
        )
    if base_url.startswith("http://") and not allow_http:
        return EvidenceSourceResult(
            source_class=SourceClass.COMMONS,
            status=SourceStatus.UNAVAILABLE,
            consulted=False,
            gap="Commons URL is HTTP and MNCS_COMMONS_ALLOW_HTTP is not set.",
            detail="Refusing plaintext Commons access unless explicitly allowed.",
        )
    try:
        descriptor = fetcher(join_url(base_url, "/.well-known/mncs-commons"), method="GET")
        if not isinstance(descriptor, dict):
            raise HttpError("INVALID_JSON", "Commons descriptor was not an object")
        payload = fetcher(
            join_url(base_url, "/exchange/v0alpha1/query"),
            method="POST",
            payload={"limit": 40},
        )
    except HttpError as error:
        return EvidenceSourceResult(
            source_class=SourceClass.COMMONS,
            status=SourceStatus.UNAVAILABLE,
            consulted=True,
            gap="Commons public interface was unreachable.",
            detail=str(error),
        )

    records = _extract_records(payload)
    items: list[EvidenceItem] = []
    retrieved = utcnow()
    for record in records:
        occurred = parse_iso_datetime(
            record.get("createdAt") or record.get("created_at") or record.get("timestamp")
        )
        if occurred is not None and (occurred < interval.start or occurred > interval.end):
            continue
        kind = str(record.get("kind") or record.get("type") or "record")
        title = evidence_as_data(
            record.get("title") or record.get("claim") or record.get("summary") or kind,
            limit=180,
        )
        digest = str(record.get("digest") or record.get("id") or title)[:64]
        summary = summarize_body(
            record.get("body")
            or record.get("statement")
            or record.get("observation")
            or record.get("summary")
        )
        items.append(
            EvidenceItem(
                item_id=f"commons:{digest}",
                source_class=SourceClass.COMMONS,
                kind=EvidenceKind.COMMONS_RECORD,
                title=title,
                summary=summary,
                provenance=EvidenceProvenance(
                    source_class=SourceClass.COMMONS,
                    locator=f"commons:{digest}",
                    retrieved_at=retrieved,
                    record_id=digest,
                    content_type="commons-record",
                ),
                occurred_at=occurred,
                signal=3.5,
                confidence=Confidence.LOW,
                negative=looks_negative(title, summary) or kind.lower() in {"failedapproach", "advisory"},
                unresolved=kind.lower() in {"question", "workrequest", "hypothesis"},
                raw={"kind": kind, "digest": digest, "instructionsAreUntrusted": True},
            )
        )
    status = SourceStatus.AVAILABLE if items else SourceStatus.EMPTY
    exchange = scrub_text(descriptor.get("exchangeVersion") or descriptor.get("version"), limit=80)
    return EvidenceSourceResult(
        source_class=SourceClass.COMMONS,
        status=status,
        consulted=True,
        items=items,
        detail=f"Queried Commons exchange {exchange or 'unknown'} as untrusted inert data.",
    )


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("records", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if "record" in payload and isinstance(payload["record"], dict):
        return [payload["record"]]
    return []
