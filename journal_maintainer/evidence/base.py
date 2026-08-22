"""Shared evidence scoring and classification."""

from __future__ import annotations

import re

from ..models import Confidence, EvidenceKind
from ..sanitize import is_noise_title, scrub_text

SIGNAL_TERMS = {
    "architecture": 4.0,
    "authority": 4.0,
    "rfc": 4.5,
    "specification": 4.0,
    "spec": 3.0,
    "contract": 3.5,
    "evidence": 3.0,
    "conformance": 3.5,
    "unknown": 2.5,
    "fail": 2.5,
    "fabric": 3.0,
    "commons": 3.0,
    "forge": 3.0,
    "harness": 2.5,
    "control": 2.0,
    "language": 3.5,
    "compiler": 3.5,
    "ssa": 3.0,
    "runtime": 2.5,
    "journal": 3.0,
    "provenance": 3.0,
    "rights": 2.5,
    "experiment": 3.5,
    "failure": 3.0,
    "abandoned": 3.5,
    "boundary": 3.0,
    "lifecycle": 2.5,
    "operator": 2.0,
    "spine": 3.5,
    "reconstruction": 3.0,
    "mncds": 3.0,
    "mncs": 1.5,
}

PATH_SIGNAL = {
    "docs/architecture": 5.0,
    "docs/": 2.5,
    "rfc": 5.0,
    "spec/": 4.5,
    "schema": 3.0,
    "journal": 3.5,
    "agnts": 0.0,
    "agents.md": 2.0,
    "readme": 2.0,
}

KIND_BY_PATH = (
    (re.compile(r"rfc", re.I), EvidenceKind.RFC),
    (re.compile(r"(^|/)spec(/|$)|specification", re.I), EvidenceKind.RFC),
    (re.compile(r"architecture", re.I), EvidenceKind.ARCHITECTURE),
    (re.compile(r"docs/", re.I), EvidenceKind.DOCUMENTATION),
)


def classify_files(files: list[str]) -> EvidenceKind | None:
    joined = " ".join(files)
    for pattern, kind in KIND_BY_PATH:
        if pattern.search(joined):
            return kind
    return None


def score_item(title: str, summary: str, files: list[str], labels: list[str]) -> tuple[float, bool]:
    text = " ".join([title, summary, " ".join(files), " ".join(labels)]).lower()
    if is_noise_title(title):
        return 0.1, True
    score = 1.0
    for term, weight in SIGNAL_TERMS.items():
        if term in text:
            score += weight
    for fragment, weight in PATH_SIGNAL.items():
        if fragment in text:
            score += weight
    if any(token in text for token in ("wip", "draft", "unknown", "fail", "abandon", "revert")):
        score += 1.5
    return score, score < 2.0 and is_noise_title(title)


def confidence_from_score(score: float, *, source_complete: bool) -> Confidence:
    if not source_complete and score < 6:
        return Confidence.UNKNOWN
    if score >= 8:
        return Confidence.HIGH
    if score >= 4:
        return Confidence.MEDIUM
    if score >= 2:
        return Confidence.LOW
    return Confidence.UNKNOWN


def looks_negative(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(
        token in text
        for token in (
            "fail",
            "failed",
            "abandon",
            "revert",
            "unknown",
            "dead end",
            "does not",
            "cannot",
            "blocked",
            "rejected",
        )
    )


def summarize_body(body: object, *, limit: int = 420) -> str:
    text = scrub_text(body, limit=limit * 2)
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("#"):
            continue
        if stripped.lower() in {"summary", "## summary"}:
            continue
        if re.match(r"^[-*]\s.+:\s*$", stripped):
            continue
        if re.match(r"^[-*]\s", stripped) and not lines:
            continue
        lines.append(stripped.lstrip("-* "))
        if len(" ".join(lines)) >= limit:
            break
    first = " ".join(lines)
    return scrub_text(first, limit=limit)
