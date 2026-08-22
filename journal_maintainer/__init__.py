"""Atlas Journal Maintainer.

A bounded, non-normative Atlas capability that synthesizes the MNCS Development
Journal from inspectable project evidence. It does not own MNCS/MNCDS authority,
Commons persistence, Fabric execution, Forge evaluation, or Harness policy.
"""

from .models import (
    AutoMergeEligibility,
    Confidence,
    CoveredInterval,
    DraftEntry,
    EvidenceItem,
    JournalRun,
    PublicationEligibility,
    RunOutcome,
    SourceClass,
    SourceStatus,
)

__all__ = [
    "AutoMergeEligibility",
    "Confidence",
    "CoveredInterval",
    "DraftEntry",
    "EvidenceItem",
    "JournalRun",
    "PublicationEligibility",
    "RunOutcome",
    "SourceClass",
    "SourceStatus",
]

__version__ = "0.1.0"
