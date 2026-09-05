"""Structured bypass detection.

Atlas observes; it does not enforce. Given a stream of observed operation
events, :func:`scan` returns structured findings for patterns that bypass
the conformant path: direct protected mutation, self-validation, provenance
stripping, fabricated evidence, undeclared cross-repo mutation, undeclared
network use, unauthorized worker dispatch, CI/conformance disabling, and
promotion outside the lifecycle.

Each finding carries the conformant route when one exists. Many bypasses
are development pressure, not malice: the finding says how to comply.
"""

from __future__ import annotations

from .vocabulary import LIFECYCLE_GATE

# Paths whose modification is governance-shaped wherever they appear.
PROTECTED_PATH_PREFIXES = (
    "validators/",
    "validator/",
    "schemas/",
    "policy/",
    "policies/",
    ".github/workflows/",
    "mncs-actions/",
    "rights/",
    "provenance/",
)

LIFECYCLE_PROMOTION_ORDER = ("proposal", "validation", "confirmation", "promotion", "release")


def _is_protected(path: str) -> bool:
    lowered = path.lower()
    return lowered.startswith(PROTECTED_PATH_PREFIXES)


def scan(events: list[dict]) -> list[dict]:
    """Scan observed operation events; return structured bypass findings."""
    findings: list[dict] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        kind = event.get("kind", "")
        scanner = _SCANNERS.get(kind)
        if scanner is None:
            continue
        finding = scanner(event, index)
        if finding is not None:
            findings.append(finding)
    return findings


def _base(code: str, severity: str, event: dict, index: int, detail: str,
          authority: str, conformant_route: tuple[str, ...]) -> dict:
    return {
        "schema_version": "mncs.atlas-bypass-finding/1",
        "code": code,
        "severity": severity,
        "actor": event.get("actor", "unknown"),
        "event_index": index,
        "detail": detail,
        "authority": authority,
        "conformant_route": list(conformant_route),
    }


def _scan_mutation(event: dict, index: int) -> dict | None:
    paths = [str(p) for p in event.get("paths", []) if isinstance(p, str)]
    protected = [p for p in paths if _is_protected(p)]
    if event.get("action_id"):
        # Declared action touching protected paths: conformant shape, but a
        # self-validating one is still a bypass (checked below).
        if protected and event.get("change_id") and event.get("change_id") == event.get(
            "validating_change_id"
        ):
            return _base(
                "SELF_VALIDATION", "high", event, index,
                f"change {event.get('change_id')} validates itself while "
                f"touching protected paths: {', '.join(protected)}.",
                "forge",
                ("independent forge evaluation", "independent confirmation", "promotion"),
            )
        return None
    if protected:
        return _base(
            "DIRECT_PROTECTED_MUTATION", "high", event, index,
            f"protected paths mutated without a declared MNCS action: "
            f"{', '.join(protected)}.",
            "mncs-actions",
            ("declare intent as MNCS action", "change.validate", "provide evidence"),
        )
    repos = {str(r) for r in event.get("repos", []) if isinstance(r, str)}
    if len(repos) > 1:
        return _base(
            "UNDECLARED_CROSS_REPO_MUTATION", "medium", event, index,
            f"mutation spans repositories without a declared action: "
            f"{', '.join(sorted(repos))}.",
            "mncs-actions",
            ("declare a cross-repository action", "per-repo authority review"),
        )
    return None


def _scan_evidence(event: dict, index: int) -> dict | None:
    if event.get("provenance_stripped"):
        return _base(
            "PROVENANCE_STRIPPING", "high", event, index,
            "artifact or change presented without the provenance it was "
            "produced with.",
            "rights-provenance",
            ("record transformation lineage", "re-attach provenance", "re-validate"),
        )
    digest = event.get("digest", "")
    if digest and not (isinstance(digest, str) and len(digest) == 64
                       and all(c in "0123456789abcdef" for c in digest.lower())):
        return _base(
            "FABRICATED_EVIDENCE", "high", event, index,
            f"evidence digest is malformed: {digest!r}.",
            "rights-provenance",
            ("reproduce the artifact", "re-record evidence with valid digests"),
        )
    return None


def _scan_execution(event: dict, index: int) -> dict | None:
    if event.get("network_used") and not event.get("network_declared"):
        return _base(
            "UNDECLARED_NETWORK_USE", "medium", event, index,
            "network use observed without a prior declaration.",
            "fabric",
            ("declare network use", "worker.dispatch"),
        )
    if event.get("worker_dispatched") and not event.get("execution_target"):
        return _base(
            "UNAUTHORIZED_WORKER_DISPATCH", "medium", event, index,
            "work dispatched without a declared Fabric execution target.",
            "fabric",
            ("declare execution target", "fabric placement", "worker.dispatch"),
        )
    return None


def _scan_governance(event: dict, index: int) -> dict | None:
    if event.get("ci_disabled") or event.get("conformance_disabled"):
        return _base(
            "CI_CONFORMANCE_DISABLING", "high", event, index,
            "conformance or CI enforcement was disabled or bypassed.",
            "mncs-actions",
            ("re-enable the check", "record a governed exception with expiry"),
        )
    to = event.get("lifecycle_to", "")
    if event.get("promoted") and to not in ("confirmation", "promotion", "release"):
        return _base(
            "PROMOTION_OUTSIDE_LIFECYCLE", "high", event, index,
            f"promotion attempted from lifecycle state {to or 'unknown'}; "
            "a proposal is never a promotion.",
            "mncds",
            ("advance through validation", "independent confirmation", "promotion"),
        )
    return None


_SCANNERS = {
    "mutation": _scan_mutation,
    "evidence": _scan_evidence,
    "execution": _scan_execution,
    "governance": _scan_governance,
}
