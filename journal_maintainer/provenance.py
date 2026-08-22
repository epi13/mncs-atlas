"""Inspectable, non-normative run provenance for journal PRs."""

from __future__ import annotations

from .models import JournalRun, SourceClass, SourceStatus


def pull_request_body(run: JournalRun) -> str:
    covered = run.covered
    interval = "unknown"
    if covered is not None:
        interval = f"{covered.start_date.isoformat()} → {covered.end_date.isoformat()} ({covered.days} day(s))"
    sources = []
    for source in run.sources:
        mark = source.status.value
        sources.append(f"- `{source.source_class.value}`: {mark}" + (f" — {source.gap}" if source.gap else ""))
    commons = run.source_status(SourceClass.COMMONS)
    experiments = run.source_status(SourceClass.EXPERIMENT)
    auto = "no"
    if run.auto_merge and run.auto_merge.eligible:
        auto = "yes"
    elif run.auto_merge:
        auto = "no — " + "; ".join(run.auto_merge.reasons)
    gaps = "\n".join(f"- {gap}" for gap in run.evidence_gaps) or "- none recorded"
    omitted = "\n".join(f"- {item}" for item in run.omitted_uncertain) or "- none recorded"
    validation = "\n".join(f"- `{item}`" for item in run.validation) or "- none recorded"
    repos = ", ".join(run.inspected_repositories) or "none"
    return f"""## Atlas Journal Maintainer run

This pull request was produced by the bounded **Atlas Journal Maintainer**.
The journal entry is **non-normative**. It does not override MNCS, MNCDS,
owning-repository contracts, experiment evidence, or Commons records.

- **Run ID:** `{run.run_id}`
- **Outcome:** `{run.outcome.value}`
- **Covered interval:** {interval}
- **Previous publication:** {run.previous.publication_id if run.previous else "none (first run)"}
- **Inspected repositories:** {repos}
- **Commons consulted:** {_consulted(commons)}
- **Experiment evidence consulted:** {_consulted(experiments)}
- **Automatic merge eligible:** {auto}

### Evidence source classes

{chr(10).join(sources) or "- none"}

### Validation

{validation}

### Known evidence gaps

{gaps}

### Uncertain topics omitted

{omitted}

### Authority reminder

Git activity is not project truth. Commons publication is not acceptance.
Fabric execution is not conformance. Forge results are not normative.
Model interpretation is not factual history. Journal prose is not a specification.
"""


def _consulted(source) -> str:
    if source is None:
        return "no"
    if not source.consulted:
        return f"no ({source.status.value})"
    if source.status == SourceStatus.UNAVAILABLE:
        return f"attempted, unavailable ({source.gap or 'no detail'})"
    if source.status == SourceStatus.EMPTY:
        return "yes, no records in interval"
    if source.status == SourceStatus.MALFORMED:
        return "yes, malformed snapshot"
    return f"yes ({source.status.value})"
