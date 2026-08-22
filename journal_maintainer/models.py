"""Core Journal Maintainer types.

These objects are inspectable run state, not project authority. A journal run
may record UNKNOWN, omit uncertain material, or refuse publication. It must not
promote Git activity, Commons records, Fabric execution, Forge results, or
model interpretation into governing truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


CANONICAL_PAGES_URL = "https://epi13.github.io/mncs-atlas/"
JOURNAL_CANONICAL_PREFIX = f"{CANONICAL_PAGES_URL}journal/"
MAINTAINER_IDENTITY = "atlas-journal-maintainer"
MAINTAINER_LABEL = "journal-maintainer"
NON_NORMATIVE_LABEL = "Non-normative"


class SourceClass(str, Enum):
    OWNING_REPOSITORY = "owning-repository"
    EXPERIMENT = "experiment"
    COMMONS = "commons"
    PREVIOUS_JOURNAL = "previous-journal"
    CONVERSATION_HINT = "conversation-hint"


class SourceStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    EMPTY = "empty"
    MALFORMED = "malformed"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class RunOutcome(str, Enum):
    FIRST_RUN = "first-run"
    NORMAL = "normal"
    DELAYED = "delayed"
    RETRY = "retry"
    NO_OP = "no-op"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    ALREADY_PUBLISHED = "already-published"


class EvidenceKind(str, Enum):
    MERGED_PR = "merged-pr"
    OPEN_PR = "open-pr"
    COMMIT = "commit"
    ISSUE = "issue"
    RELEASE = "release"
    DOCUMENTATION = "documentation"
    RFC = "rfc"
    ARCHITECTURE = "architecture"
    EXPERIMENT_RECORD = "experiment-record"
    COMMONS_RECORD = "commons-record"
    JOURNAL_ENTRY = "journal-entry"
    HINT = "hint"
    FAILURE = "failure"
    UNKNOWN = "unknown"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CoveredInterval:
    """Development interval the run is responsible for covering."""

    start: datetime
    end: datetime
    previous_publication_id: str | None = None
    derived_from: str = "previous-successful-publication"

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("covered interval end precedes start")

    @property
    def start_date(self) -> date:
        return self.start.astimezone(timezone.utc).date()

    @property
    def end_date(self) -> date:
        return self.end.astimezone(timezone.utc).date()

    @property
    def key(self) -> str:
        return f"{self.start_date.isoformat()}_{self.end_date.isoformat()}"

    @property
    def days(self) -> int:
        return max(1, (self.end_date - self.start_date).days + 1)

    @property
    def delayed(self) -> bool:
        return self.days > 9

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": isoformat_utc(self.start),
            "end": isoformat_utc(self.end),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "key": self.key,
            "days": self.days,
            "delayed": self.delayed,
            "previous_publication_id": self.previous_publication_id,
            "derived_from": self.derived_from,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CoveredInterval":
        start = parse_iso_datetime(data.get("start") or data.get("start_date"))
        end = parse_iso_datetime(data.get("end") or data.get("end_date"))
        if start is None or end is None:
            raise ValueError("covered interval requires start and end")
        return cls(
            start=start,
            end=end,
            previous_publication_id=data.get("previous_publication_id"),
            derived_from=str(data.get("derived_from") or "previous-successful-publication"),
        )


@dataclass(frozen=True)
class PreviousPublication:
    number: int
    slug: str
    filename: str
    title: str
    published: date
    covered: CoveredInterval | None
    machine_maintained: bool
    canonical_url: str
    path: str

    @property
    def publication_id(self) -> str:
        return f"{self.number:03d}:{self.slug}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "slug": self.slug,
            "filename": self.filename,
            "title": self.title,
            "published": self.published.isoformat(),
            "covered": None if self.covered is None else self.covered.to_dict(),
            "machine_maintained": self.machine_maintained,
            "canonical_url": self.canonical_url,
            "path": self.path,
            "publication_id": self.publication_id,
        }


@dataclass
class EvidenceProvenance:
    source_class: SourceClass
    locator: str
    retrieved_at: datetime
    repository: str | None = None
    record_id: str | None = None
    content_type: str = "text"
    untrusted: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class.value,
            "locator": self.locator,
            "retrieved_at": isoformat_utc(self.retrieved_at),
            "repository": self.repository,
            "record_id": self.record_id,
            "content_type": self.content_type,
            "untrusted": self.untrusted,
        }


@dataclass
class EvidenceItem:
    """One inspectable development fact. Evidence is data, not executable authority."""

    item_id: str
    source_class: SourceClass
    kind: EvidenceKind
    title: str
    summary: str
    provenance: EvidenceProvenance
    occurred_at: datetime | None = None
    repository: str | None = None
    project_id: str | None = None
    url: str | None = None
    labels: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    signal: float = 0.0
    noise: bool = False
    confidence: Confidence = Confidence.MEDIUM
    negative: bool = False
    unresolved: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source_class": self.source_class.value,
            "kind": self.kind.value,
            "title": self.title,
            "summary": self.summary,
            "provenance": self.provenance.to_dict(),
            "occurred_at": isoformat_utc(self.occurred_at),
            "repository": self.repository,
            "project_id": self.project_id,
            "url": self.url,
            "labels": list(self.labels),
            "files": list(self.files),
            "signal": self.signal,
            "noise": self.noise,
            "confidence": self.confidence.value,
            "negative": self.negative,
            "unresolved": self.unresolved,
        }


@dataclass
class EvidenceSourceResult:
    source_class: SourceClass
    status: SourceStatus
    consulted: bool
    items: list[EvidenceItem] = field(default_factory=list)
    gap: str | None = None
    detail: str | None = None
    # Completeness is tracked per owning source/repository so one endpoint
    # failure cannot be mistaken for a complete empty result.
    repository_statuses: dict[str, SourceStatus] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_class": self.source_class.value,
            "status": self.status.value,
            "consulted": self.consulted,
            "item_count": len(self.items),
            "gap": self.gap,
            "detail": self.detail,
            "repository_statuses": {name: status.value for name, status in sorted(self.repository_statuses.items())},
        }


@dataclass(frozen=True)
class EvidenceBundle:
    """Bounded, inspectable handoff from Atlas collection to a capable editor."""

    bundle_id: str
    interval: CoveredInterval
    previous_publication: PreviousPublication | None
    sources: tuple[EvidenceSourceResult, ...]
    items: tuple[EvidenceItem, ...]
    unavailable_sources: tuple[str, ...] = ()
    temporal_coverage: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "interval": self.interval.to_dict(),
            "previous_publication": self.previous_publication.to_dict() if self.previous_publication else None,
            "sources": [source.to_dict() for source in self.sources],
            "items": [item.to_dict() for item in self.items],
            "unavailable_sources": list(self.unavailable_sources),
            "temporal_coverage": dict(self.temporal_coverage),
            "created_at": isoformat_utc(self.created_at),
        }


@dataclass
class TopicCluster:
    topic_id: str
    title: str
    theme: str
    summary: str
    items: list[EvidenceItem]
    confidence: Confidence
    negative: bool = False
    unresolved_questions: list[str] = field(default_factory=list)
    omitted: bool = False
    omit_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "title": self.title,
            "theme": self.theme,
            "summary": self.summary,
            "item_ids": [item.item_id for item in self.items],
            "confidence": self.confidence.value,
            "negative": self.negative,
            "unresolved_questions": list(self.unresolved_questions),
            "omitted": self.omitted,
            "omit_reason": self.omit_reason,
        }


@dataclass
class DraftSection:
    heading: str
    paragraphs: list[str]
    note: str | None = None
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DraftEntry:
    number: int
    title: str
    slug: str
    lede: str
    sections: list[DraftSection]
    disclosure: str
    covered: CoveredInterval
    published: date
    machine_maintained: bool = True
    unresolved: list[str] = field(default_factory=list)
    omitted_topics: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    ambiguity: bool = False
    ambiguity_reason: str | None = None
    synthesizer: str = "heuristic"
    used_item_ids: list[str] = field(default_factory=list)
    editor_identity: str | None = None
    editor_type: str | None = None
    editor_run_id: str | None = None
    evidence_bundle_id: str | None = None

    @property
    def filename(self) -> str:
        return f"{self.published.isoformat()}-{self.slug}.html"

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "slug": self.slug,
            "lede": self.lede,
            "sections": [section.to_dict() for section in self.sections],
            "disclosure": self.disclosure,
            "covered": self.covered.to_dict(),
            "published": self.published.isoformat(),
            "machine_maintained": self.machine_maintained,
            "unresolved": list(self.unresolved),
            "omitted_topics": list(self.omitted_topics),
            "evidence_gaps": list(self.evidence_gaps),
            "ambiguity": self.ambiguity,
            "ambiguity_reason": self.ambiguity_reason,
            "synthesizer": self.synthesizer,
            "used_item_ids": list(self.used_item_ids),
            "editor_identity": self.editor_identity,
            "editor_type": self.editor_type,
            "editor_run_id": self.editor_run_id,
            "evidence_bundle_id": self.evidence_bundle_id,
            "filename": self.filename,
        }


@dataclass
class RenderedEntry:
    draft: DraftEntry
    html: str
    canonical_url: str
    relative_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.draft.filename,
            "canonical_url": self.canonical_url,
            "relative_path": self.relative_path,
            "html_bytes": len(self.html.encode("utf-8")),
        }


@dataclass
class PublicationEligibility:
    eligible: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"eligible": self.eligible, "reasons": list(self.reasons)}


@dataclass
class AutoMergeEligibility:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    repository_permits_auto_merge: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "repository_permits_auto_merge": self.repository_permits_auto_merge,
        }


@dataclass
class PathCheckResult:
    allowed: bool
    changed: list[str]
    unexpected: list[str]
    authorized: list[str]
    base: str | None = None
    head: str | None = None
    append_only: bool = True
    history_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "changed": list(self.changed),
            "unexpected": list(self.unexpected),
            "authorized": list(self.authorized),
            "base": self.base,
            "head": self.head,
            "append_only": self.append_only,
            "history_errors": list(self.history_errors),
        }


@dataclass
class FailureState:
    code: str
    message: str
    closed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "closed": self.closed}


@dataclass
class JournalRun:
    """Complete inspectable state for one maintainer invocation."""

    run_id: str
    started_at: datetime
    outcome: RunOutcome
    covered: CoveredInterval | None = None
    previous: PreviousPublication | None = None
    sources: list[EvidenceSourceResult] = field(default_factory=list)
    items: list[EvidenceItem] = field(default_factory=list)
    clusters: list[TopicCluster] = field(default_factory=list)
    draft: DraftEntry | None = None
    rendered: RenderedEntry | None = None
    publication: PublicationEligibility | None = None
    auto_merge: AutoMergeEligibility | None = None
    path_check: PathCheckResult | None = None
    validation: list[str] = field(default_factory=list)
    inspected_repositories: list[str] = field(default_factory=list)
    evidence_gaps: list[str] = field(default_factory=list)
    omitted_uncertain: list[str] = field(default_factory=list)
    branch: str | None = None
    pull_request_url: str | None = None
    failure: FailureState | None = None
    retry_of: str | None = None
    notes: list[str] = field(default_factory=list)
    finished_at: datetime | None = None
    evidence_bundle_id: str | None = None
    synthesizer_path: str | None = None
    editor_identity: str | None = None
    editor_type: str | None = None
    head_sha: str | None = None
    promotion_state: str = "not-evaluated"

    def source_status(self, source_class: SourceClass) -> EvidenceSourceResult | None:
        for source in self.sources:
            if source.source_class == source_class:
                return source
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "maintainer": MAINTAINER_IDENTITY,
            "non_normative": True,
            "authority": "atlas-editorial-automation-only",
            "started_at": isoformat_utc(self.started_at),
            "finished_at": isoformat_utc(self.finished_at),
            "outcome": self.outcome.value,
            "covered": None if self.covered is None else self.covered.to_dict(),
            "previous": None if self.previous is None else self.previous.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "item_count": len(self.items),
            "clusters": [cluster.to_dict() for cluster in self.clusters],
            "draft": None if self.draft is None else self.draft.to_dict(),
            "rendered": None if self.rendered is None else self.rendered.to_dict(),
            "publication": None if self.publication is None else self.publication.to_dict(),
            "auto_merge": None if self.auto_merge is None else self.auto_merge.to_dict(),
            "path_check": None if self.path_check is None else self.path_check.to_dict(),
            "validation": list(self.validation),
            "inspected_repositories": list(self.inspected_repositories),
            "evidence_gaps": list(self.evidence_gaps),
            "omitted_uncertain": list(self.omitted_uncertain),
            "branch": self.branch,
            "pull_request_url": self.pull_request_url,
            "failure": None if self.failure is None else self.failure.to_dict(),
            "retry_of": self.retry_of,
            "notes": list(self.notes),
            "evidence_bundle_id": self.evidence_bundle_id,
            "synthesizer_path": self.synthesizer_path,
            "editor_identity": self.editor_identity,
            "editor_type": self.editor_type,
            "head_sha": self.head_sha,
            "promotion_state": self.promotion_state,
        }


@dataclass
class FamilyProject:
    project_id: str
    name: str
    repository: str | None
    owner: str | None
    repo: str | None
    role: str
    maturity: str | None = None
    authority_class: str | None = None
    operator: bool = False
