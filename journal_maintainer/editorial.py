"""Separate evidence collection from editorial synthesis.

The journal is not a changelog. The synthesizer selects a small set of
developments that changed implementation, architecture, experimental
understanding, confidence, research direction, or project boundaries.
Routine noise is omitted. Uncertainty and negative results are preserved.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .journal_html import next_journal_number
from .models import (
    Confidence,
    CoveredInterval,
    DraftEntry,
    DraftSection,
    EvidenceItem,
    EvidenceKind,
    EvidenceSourceResult,
    PreviousPublication,
    SourceClass,
    SourceStatus,
    TopicCluster,
)
from .sanitize import slugify, scrub_text

THEME_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("orientation-and-journal", "Orientation and the Development Journal", ("journal", "atlas", "orientation", "maintainer")),
    ("family-record-spine", "Family record spine and concept reconstruction", ("spine", "reconstruction", "cre", "record spine")),
    ("authority-and-evidence", "Authority, evidence, and UNKNOWN", ("authority", "conformance", "unknown", "evidence", "fail >")),
    ("language-and-compiler", "Language and compiler", ("language", "compiler", "ssa", "wasm", "hir", "syntax")),
    ("execution-fabric", "Execution and Fabric", ("fabric", "worker", "execution", "transport", "admission")),
    ("commons-memory", "Commons and institutional memory", ("commons", "institutional", "coordination", "handoff")),
    ("operator-stack", "Operator stack: Control, Harness, and Forge", ("control", "harness", "forge", "operator", "sandbox")),
    ("learning", "Learning systems", ("ravel", "mnel", "learning", "investigator")),
    ("rights-provenance", "Rights and provenance", ("rights", "provenance", "authorship", "license")),
    ("studies-validators", "Studies and independent validation", ("reference", "validator", "study")),
)

DISCLOSURE = (
    "This entry is machine-maintained: it was synthesized by the Atlas Journal "
    "Maintainer from inspectable MNCS project evidence. It is a dated developmental "
    "record, not a specification, acceptance decision, or substitute for "
    "owning-repository documentation."
)

NOISE_KINDS = {EvidenceKind.COMMIT}


def synthesize(
    *,
    items: list[EvidenceItem],
    sources: list[EvidenceSourceResult],
    covered: CoveredInterval,
    previous: PreviousPublication | None,
    existing_entries: list[PreviousPublication],
    published: date,
    synthesizer: str = "heuristic",
    draft_file: Path | None = None,
) -> tuple[list[TopicCluster], DraftEntry]:
    if draft_file is not None:
        return _from_draft_file(
            draft_file,
            items=items,
            sources=sources,
            covered=covered,
            existing_entries=existing_entries,
            published=published,
        )

    clusters = cluster_topics(items, previous)
    selected = [cluster for cluster in clusters if not cluster.omitted]
    selected.sort(key=lambda cluster: (-(sum(item.signal for item in cluster.items)), cluster.topic_id))
    selected = selected[:7]

    gaps = [
        source.gap
        for source in sources
        if source.gap and source.status in {SourceStatus.UNAVAILABLE, SourceStatus.MALFORMED}
    ]
    omitted = [cluster.title for cluster in clusters if cluster.omitted]
    unresolved = _collect_unresolved(selected, items, previous)
    ambiguity = _material_ambiguity(sources, selected, items)

    number = next_journal_number(existing_entries)
    title, lede = _title_and_lede(selected, covered, previous)
    sections = [_section_for(cluster) for cluster in selected]
    if unresolved:
        sections.append(
            DraftSection(
                heading="Unresolved questions",
                paragraphs=[
                    "The interval did not settle every thread it opened. The following remain better treated as open than as conclusions:",
                    *[f"{question}" for question in unresolved[:6]],
                ],
            )
        )
    negative = [cluster for cluster in selected if cluster.negative]
    if negative and not any("fail" in section.heading.lower() or "wrong" in section.heading.lower() for section in sections):
        sections.append(
            DraftSection(
                heading="Failures and negative results worth keeping",
                paragraphs=[
                    "Software histories prefer the artifacts that survived. This interval still has work that failed, stalled, or stayed UNKNOWN, and those outcomes are part of the developmental record rather than defects in the journal.",
                    *[cluster.summary for cluster in negative[:4]],
                ],
            )
        )
    sections.append(
        DraftSection(
            heading="What this entry is not",
            paragraphs=[
                "Nothing here overrides MNCS, MNCDS, an accepted project contract, or an owning repository's current documentation. Git activity is not project truth. Commons publication is not acceptance. Fabric execution is not conformance. Forge results are not normative. Where evidence was thin, the maintainer omitted the claim instead of manufacturing confidence.",
            ],
            note="Non-normative developmental record.",
        )
    )

    used_ids = [item.item_id for cluster in selected for item in cluster.items]
    draft = DraftEntry(
        number=number,
        title=title,
        slug=slugify(title),
        lede=lede,
        sections=sections,
        disclosure=DISCLOSURE,
        covered=covered,
        published=published,
        unresolved=unresolved,
        omitted_topics=omitted,
        evidence_gaps=[gap for gap in gaps if gap],
        ambiguity=ambiguity[0],
        ambiguity_reason=ambiguity[1],
        synthesizer=synthesizer,
        used_item_ids=used_ids,
    )
    return clusters, draft


def cluster_topics(items: list[EvidenceItem], previous: PreviousPublication | None) -> list[TopicCluster]:
    usable = [
        item
        for item in items
        if item.source_class not in {SourceClass.CONVERSATION_HINT, SourceClass.PREVIOUS_JOURNAL}
        and not item.noise
        and not (item.kind == EvidenceKind.COMMIT and item.signal < 6)
        and not item.title.lower().startswith("merge pull request")
    ]
    buckets: dict[str, list[EvidenceItem]] = defaultdict(list)
    for item in usable:
        buckets[_theme_for(item)].append(item)

    previous_title = (previous.title if previous else "").lower()
    clusters: list[TopicCluster] = []
    for theme_id, heading, _keys in THEME_RULES:
        grouped = buckets.get(theme_id, [])
        if not grouped:
            continue
        grouped.sort(key=lambda item: (-item.signal, item.title))
        primary = grouped[:8]
        if len(primary) == 1 and primary[0].kind in {EvidenceKind.ISSUE, EvidenceKind.COMMIT} and primary[0].signal < 4:
            continue
        confidence = _cluster_confidence(primary)
        summary = _cluster_summary(heading, primary)
        omitted = False
        omit_reason = None
        # Avoid restating the opening journal manifesto every week.
        if theme_id == "orientation-and-journal" and previous and not previous.machine_maintained:
            if all(item.kind == EvidenceKind.JOURNAL_ENTRY for item in primary) and max(item.signal for item in primary) < 7:
                omitted = True
                omit_reason = "Previous entry already established the journal's purpose."
        if heading.lower() in previous_title and all(item.kind == EvidenceKind.JOURNAL_ENTRY for item in primary):
            omitted = True
            omit_reason = "Topic was already the subject of the previous journal entry."
        clusters.append(
            TopicCluster(
                topic_id=theme_id,
                title=heading,
                theme=theme_id,
                summary=summary,
                items=primary,
                confidence=confidence,
                negative=any(item.negative for item in primary),
                unresolved_questions=[item.title for item in primary if item.unresolved][:4],
                omitted=omitted,
                omit_reason=omit_reason,
            )
        )
    leftover = buckets.get("other") or []
    leftover = [item for item in leftover if item.signal >= 5][:6]
    if leftover:
        clusters.append(
            TopicCluster(
                topic_id="other-material",
                title="Other material developments",
                theme="other",
                summary=_cluster_summary("Other material developments", leftover),
                items=leftover,
                confidence=_cluster_confidence(leftover),
                negative=any(item.negative for item in leftover),
            )
        )
    # Drop buckets that are only noise-level after scoring.
    for cluster in clusters:
        if sum(item.signal for item in cluster.items) < 4 and not cluster.negative:
            cluster.omitted = True
            cluster.omit_reason = cluster.omit_reason or "Below editorial threshold; treated as routine activity."
    return clusters


def meaningful_development(clusters: list[TopicCluster], items: list[EvidenceItem]) -> bool:
    selected = [cluster for cluster in clusters if not cluster.omitted]
    if selected:
        return True
    strong = [item for item in items if not item.noise and item.signal >= 6 and item.source_class != SourceClass.PREVIOUS_JOURNAL]
    return len(strong) >= 2


def _theme_for(item: EvidenceItem) -> str:
    repo = (item.repository or "").lower()
    project = (item.project_id or "").lower()
    if "mncs-language" in repo or project == "mncs-language":
        return "language-and-compiler"
    if "mncs-fabric" in repo:
        return "execution-fabric"
    if "commons" in repo:
        return "commons-memory"
    if "forge" in repo:
        return "operator-stack"
    if "harness" in repo or "control-mcp" in repo:
        return "operator-stack"
    if "ravel" in repo or "experimental-learning" in repo:
        return "learning"
    if "rights" in repo:
        return "rights-provenance"
    if "mncs-atlas" in repo or project == "atlas":
        text = f"{item.title} {item.summary} {' '.join(item.files)}".lower()
        if any(key in text for key in ("spine", "reconstruction", "cre")):
            return "family-record-spine"
        return "orientation-and-journal"
    text = f"{item.title} {item.summary} {' '.join(item.files)}".lower()
    for theme_id, _heading, keys in THEME_RULES:
        if any(key in text or key in project for key in keys):
            return theme_id
    return "other"


def _cluster_confidence(items: list[EvidenceItem]) -> Confidence:
    if any(item.confidence == Confidence.UNKNOWN for item in items) and all(item.signal < 6 for item in items):
        return Confidence.UNKNOWN
    if any(item.kind in {EvidenceKind.MERGED_PR, EvidenceKind.RFC, EvidenceKind.ARCHITECTURE} for item in items):
        return Confidence.HIGH
    if items:
        return Confidence.MEDIUM
    return Confidence.UNKNOWN


def _cluster_summary(heading: str, items: list[EvidenceItem]) -> str:
    merged = [item for item in items if item.kind in {EvidenceKind.MERGED_PR, EvidenceKind.RFC, EvidenceKind.ARCHITECTURE, EvidenceKind.DOCUMENTATION}]
    open_items = [item for item in items if item.unresolved]
    negatives = [item for item in items if item.negative]
    lead = merged[0] if merged else items[0]
    parts = [
        f"{heading} moved during this interval, principally through {lead.title}."
    ]
    if lead.summary:
        parts.append(lead.summary.rstrip(".") + ".")
    extras = [item.title for item in merged[1:3] if item.title != lead.title]
    if extras:
        parts.append("Related work included " + "; ".join(extras) + ".")
    if negatives:
        parts.append(
            "The record includes negative or unresolved outcomes rather than a cleaned success narrative: "
            + negatives[0].title
            + "."
        )
    if open_items and not negatives:
        parts.append("Some of this work remains open rather than merged or decided.")
    repos = sorted({item.repository.split("/")[-1] for item in items if item.repository})
    if len(repos) > 1:
        parts.append("The thread crossed " + ", ".join(repos[:4]) + ".")
    return " ".join(parts)


def _section_for(cluster: TopicCluster) -> DraftSection:
    paragraphs = [cluster.summary]
    supporting = []
    seen_titles: set[str] = set()
    for item in cluster.items[:6]:
        if item.kind == EvidenceKind.JOURNAL_ENTRY:
            continue
        title_key = item.title.lower().strip()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        repo = item.repository.split("/")[-1] if item.repository else None
        supporting.append(f"{repo}: {item.title}" if repo else item.title)
    if supporting:
        paragraphs.append("Inspectable sources for this thread include " + "; ".join(supporting[:4]) + ".")
    if cluster.unresolved_questions:
        paragraphs.append(
            "Open or unfinished pieces of this thread remain: " + "; ".join(cluster.unresolved_questions) + "."
        )
    if cluster.confidence in {Confidence.LOW, Confidence.UNKNOWN}:
        paragraphs.append(
            "Confidence here is limited. The maintainer is describing the evidence trail, not asserting that the interpretation is settled."
        )
    return DraftSection(heading=cluster.title, paragraphs=paragraphs)


def _as_sentence(text: str) -> str:
    text = text.strip()
    if not text.endswith("."):
        text += "."
    return text


def _title_and_lede(
    clusters: list[TopicCluster],
    covered: CoveredInterval,
    previous: PreviousPublication | None,
) -> tuple[str, str]:
    if not clusters:
        return (
            "Quiet interval in MNCS development",
            "The covered interval did not produce a development story strong enough to justify a journal entry.",
        )
    primary = clusters[0]
    if len(clusters) == 1:
        title = primary.title
    else:
        title = _compact_title(clusters)
    span = f"{_pretty_date(covered.start_date)}–{_pretty_date(covered.end_date)}"
    if covered.start_date == covered.end_date:
        span = _pretty_date(covered.start_date)
    lede = (
        f"Since the previous Development Journal publication, MNCS work in {span} concentrated on "
        f"{_lower_first(primary.title)}. This entry follows that trail without turning it into a changelog or a specification."
    )
    if previous and not previous.machine_maintained:
        lede = (
            "The opening journal entry marked why this record exists. This first machine-maintained "
            f"entry covers what actually moved afterward: {_lower_first(primary.title).rstrip('.')}, "
            "together with the adjacent work that changed confidence or project boundaries."
        )
    return title, lede


def _compact_title(clusters: list[TopicCluster]) -> str:
    names = [cluster.title.split(":")[0].split(" and ")[0] for cluster in clusters[:3]]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]}, and {names[1].lower()}"
    return f"{names[0]}, {names[1].lower()}, and {names[2].lower()}"


def _pretty_date(value: date) -> str:
    return format_pretty_date(value)


def _lower_first(value: str) -> str:
    if not value:
        return value
    return value[0].lower() + value[1:]


def _collect_unresolved(
    clusters: list[TopicCluster],
    items: list[EvidenceItem],
    previous: PreviousPublication | None,
) -> list[str]:
    questions: list[str] = []
    for cluster in clusters:
        questions.extend(cluster.unresolved_questions)
    for item in items:
        if item.source_class == SourceClass.PREVIOUS_JOURNAL:
            questions.extend(list(item.raw.get("unresolved") or [])[:3])
    # Keep unique, short, non-repetitive questions.
    unique: list[str] = []
    seen: set[str] = set()
    for question in questions:
        key = question.lower().strip()
        if key in seen or len(question) < 12:
            continue
        seen.add(key)
        unique.append(question if question.endswith("?") else question.rstrip(".") + ".")
    return unique[:8]


def _material_ambiguity(
    sources: list[EvidenceSourceResult],
    clusters: list[TopicCluster],
    items: list[EvidenceItem],
) -> tuple[bool, str | None]:
    github = next((source for source in sources if source.source_class == SourceClass.OWNING_REPOSITORY), None)
    if github and github.status == SourceStatus.UNAVAILABLE:
        return True, "Owning-repository evidence was unavailable, so the interval cannot be synthesized confidently."
    competing = [cluster for cluster in clusters if cluster.confidence == Confidence.UNKNOWN and not cluster.omitted]
    if len(competing) >= 2 and sum(len(cluster.items) for cluster in clusters if not cluster.omitted) < 3:
        return True, "Multiple material topics remain at UNKNOWN confidence with little supporting evidence."
    conflicts = [
        item
        for item in items
        if item.negative and item.kind == EvidenceKind.MERGED_PR and item.signal >= 6
    ]
    # Negative merged work is not itself ambiguity; conflicting interpretations of the same object would be.
    del conflicts
    return False, None


def _from_draft_file(
    path: Path,
    *,
    items: list[EvidenceItem],
    sources: list[EvidenceSourceResult],
    covered: CoveredInterval,
    existing_entries: list[PreviousPublication],
    published: date,
) -> tuple[list[TopicCluster], DraftEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sections = [
        DraftSection(heading=str(section["heading"]), paragraphs=[str(p) for p in section.get("paragraphs") or []])
        for section in payload.get("sections") or []
    ]
    number = int(payload.get("number") or next_journal_number(existing_entries))
    title = scrub_text(payload.get("title") or "MNCS development notes", limit=160)
    draft = DraftEntry(
        number=number,
        title=title,
        slug=slugify(payload.get("slug") or title),
        lede=scrub_text(payload.get("lede") or "", limit=500),
        sections=sections,
        disclosure=str(payload.get("disclosure") or DISCLOSURE),
        covered=covered,
        published=published,
        unresolved=list(payload.get("unresolved") or []),
        omitted_topics=list(payload.get("omitted_topics") or []),
        evidence_gaps=[source.gap for source in sources if source.gap],
        ambiguity=bool(payload.get("ambiguity")),
        ambiguity_reason=payload.get("ambiguity_reason"),
        synthesizer="editor-draft",
        used_item_ids=[item.item_id for item in items[:20]],
    )
    return [], draft


def format_pretty_date(value: date) -> str:
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    return f"{months[value.month - 1]} {value.day}, {value.year}"
