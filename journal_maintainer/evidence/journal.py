"""Previous journal entries as continuity evidence."""

from __future__ import annotations

from pathlib import Path

from ..journal_html import extract_visible_text, load_journal_entries
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
from ..sanitize import scrub_text


def gather_previous_journal(journal_dir: Path, *, limit: int = 6) -> EvidenceSourceResult:
    entries = load_journal_entries(journal_dir)
    if not entries:
        return EvidenceSourceResult(
            source_class=SourceClass.PREVIOUS_JOURNAL,
            status=SourceStatus.EMPTY,
            consulted=True,
            detail="No previous journal entries were present.",
        )
    items: list[EvidenceItem] = []
    retrieved = utcnow()
    for entry in entries[-limit:]:
        path = Path(entry.path)
        html = path.read_text(encoding="utf-8")
        text = extract_visible_text(html)
        questions = _unresolved_from_text(text)
        items.append(
            EvidenceItem(
                item_id=f"journal:{entry.filename}",
                source_class=SourceClass.PREVIOUS_JOURNAL,
                kind=EvidenceKind.JOURNAL_ENTRY,
                title=entry.title,
                summary=scrub_text(text, limit=500),
                provenance=EvidenceProvenance(
                    source_class=SourceClass.PREVIOUS_JOURNAL,
                    locator=entry.canonical_url,
                    retrieved_at=retrieved,
                    record_id=entry.publication_id,
                    content_type="journal-html",
                ),
                occurred_at=None,
                url=entry.canonical_url,
                signal=6.0,
                confidence=Confidence.HIGH,
                unresolved=bool(questions),
                raw={"unresolved": questions, "number": entry.number, "machine": entry.machine_maintained},
            )
        )
    return EvidenceSourceResult(
        source_class=SourceClass.PREVIOUS_JOURNAL,
        status=SourceStatus.AVAILABLE,
        consulted=True,
        items=items,
        detail=f"Read {len(items)} previous journal entries for continuity.",
    )


def _unresolved_from_text(text: str) -> list[str]:
    questions: list[str] = []
    for sentence in text.replace("?", "?|").split("|"):
        sentence = sentence.strip()
        if sentence.endswith("?") and 12 < len(sentence) < 240:
            questions.append(sentence)
    return questions[:8]
