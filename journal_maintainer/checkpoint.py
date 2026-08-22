"""Durable covered-period checkpoints derived from published journal history.

The previous successful journal publication is the checkpoint. No opaque
database is introduced. Retries of the same covered interval must not create
a second article.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .journal_html import (
    interval_already_published,
    load_journal_entries,
    previous_successful_publication,
    uncovered_start,
)
from .models import CoveredInterval, PreviousPublication, RunOutcome


@dataclass
class Checkpoint:
    previous: PreviousPublication | None
    covered: CoveredInterval | None
    outcome_hint: RunOutcome
    existing_for_interval: PreviousPublication | None = None
    retry: bool = False
    notes: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "previous": None if self.previous is None else self.previous.to_dict(),
            "covered": None if self.covered is None else self.covered.to_dict(),
            "outcome_hint": self.outcome_hint.value,
            "existing_for_interval": None
            if self.existing_for_interval is None
            else self.existing_for_interval.to_dict(),
            "retry": self.retry,
            "notes": list(self.notes or []),
        }


def determine_checkpoint(
    journal_dir: Path,
    *,
    now: datetime | None = None,
    retry_branch: str | None = None,
) -> Checkpoint:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    entries = load_journal_entries(journal_dir)
    previous = previous_successful_publication(entries)
    notes: list[str] = []
    if previous is None:
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        covered = CoveredInterval(start=start, end=moment, previous_publication_id=None, derived_from="first-run")
        return Checkpoint(
            previous=None,
            covered=covered,
            outcome_hint=RunOutcome.FIRST_RUN,
            notes=["No previous journal publication; treating the run as a first-run interval."],
        )

    start = uncovered_start(previous)
    if start > moment:
        notes.append("Uncovered interval would start after now; treating as already covered.")
        return Checkpoint(
            previous=previous,
            covered=None,
            outcome_hint=RunOutcome.ALREADY_PUBLISHED,
            notes=notes,
        )

    covered = CoveredInterval(
        start=start,
        end=moment,
        previous_publication_id=previous.publication_id,
        derived_from="previous-successful-publication",
    )
    existing = interval_already_published(entries, covered.key)
    if existing is not None:
        notes.append(f"Covered interval {covered.key} already published as {existing.filename}.")
        return Checkpoint(
            previous=previous,
            covered=covered,
            outcome_hint=RunOutcome.ALREADY_PUBLISHED,
            existing_for_interval=existing,
            notes=notes,
        )

    retry = bool(retry_branch)
    if covered.delayed:
        hint = RunOutcome.DELAYED
        notes.append(f"Interval spans {covered.days} days; this is a delayed run rather than a fixed seven-day window.")
    elif retry:
        hint = RunOutcome.RETRY
        notes.append("Retry requested for the current uncovered interval.")
    elif previous.number <= 1 and not previous.machine_maintained:
        hint = RunOutcome.FIRST_RUN
        notes.append("Previous publication is the opening human journal marker.")
    else:
        hint = RunOutcome.NORMAL
    return Checkpoint(previous=previous, covered=covered, outcome_hint=hint, retry=retry, notes=notes)


def branch_for_interval(covered: CoveredInterval) -> str:
    return f"journal/maintainer/{covered.key.replace('_', '-')}"
