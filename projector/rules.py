"""Pure Atlas projection rules: classification without I/O.

These functions own the only semantic decisions the projector makes, and
each one is total: unrecognized or missing input yields an explicit
``unknown`` state with a reason instead of a fabricated fact.  Authority,
maturity, lifecycle/topology, and implementation status are kept as
separate concepts on purpose; callers must not collapse them.
"""

from __future__ import annotations

from typing import Any

LIFECYCLES = (
    "active",
    "incubating",
    "experimental",
    "orientation",
    "deprecated",
    "retired",
    "historical",
)

# Lifecycle vocabulary the projector accepts from any source.  Anything else
# is reported, never silently remapped.
KNOWN_LIFECYCLES = frozenset(LIFECYCLES) | {"unknown"}

# Native-migration states.  Only ``declared`` evidence may produce a state
# other than ``unknown``; file extensions or directory layout never do.
IMPLEMENTATION_STATES = frozenset(
    {
        "native-canonical",
        "host-canonical",
        "native-shadow",
        "bridge-adapter",
        "experimental",
        "migration-incomplete",
        "unknown",
    }
)


def normalize_lifecycle(value: Any) -> dict[str, str]:
    """Return ``{"lifecycle", "reason"}`` for a declared lifecycle value."""
    if isinstance(value, str) and value in KNOWN_LIFECYCLES:
        return {"lifecycle": value, "reason": "declared"}
    if isinstance(value, str) and value:
        return {"lifecycle": "unknown", "reason": f"unrecognized lifecycle: {value}"}
    return {"lifecycle": "unknown", "reason": "no lifecycle declared"}


def authority_note(authority_class: Any) -> dict[str, str]:
    """Split authority class from maturity: never imply one from the other."""
    if isinstance(authority_class, str) and authority_class:
        return {"authority_class": authority_class, "reason": "declared"}
    return {"authority_class": "unknown", "reason": "no authority class declared"}


def maturity_note(maturity: Any) -> dict[str, str]:
    """Maturity is descriptive only; it grants nothing."""
    if isinstance(maturity, str) and maturity:
        return {"maturity": maturity, "reason": "declared"}
    return {"maturity": "unknown", "reason": "no maturity declared"}


def classify_implementation(evidence: Any) -> dict[str, str]:
    """Classify implementation state from declared evidence only.

    ``evidence`` is a mapping of declaration name -> truthy detail, or a
    pre-classified state string from an owning record.  Absence of evidence
    is ``unknown``, never a passing or failing state.
    """
    if isinstance(evidence, str) and evidence in IMPLEMENTATION_STATES:
        if evidence == "unknown":
            return {"state": "unknown", "reason": "owning record reports unknown"}
        return {"state": evidence, "reason": "declared by owning record"}
    if isinstance(evidence, str) and evidence:
        return {"state": "unknown", "reason": f"unrecognized state: {evidence}"}
    if isinstance(evidence, dict) and evidence:
        kinds = sorted(str(key) for key, detail in evidence.items() if detail)
        if kinds:
            return {"state": "unknown", "reason": "undeclared mapping: " + ",".join(kinds)}
    return {"state": "unknown", "reason": "no implementation declaration"}


def verification_state(record: Any) -> dict[str, str]:
    """Map a verification record to PASS / FAIL / UNKNOWN.

    Missing evidence is never PASS.  Records that declare checks without
    carrying results are UNKNOWN with an explicit reason.
    """
    if isinstance(record, dict):
        verdict = record.get("verdict", record.get("status"))
        if verdict in ("PASS", "FAIL"):
            return {"state": verdict, "reason": "declared by owning verifier"}
        if verdict == "UNKNOWN":
            return {"state": "UNKNOWN", "reason": str(record.get("reason", "declared unknown"))}
        if "checks" in record or "surface" in record:
            return {"state": "UNKNOWN", "reason": "declaration without result feed"}
    return {"state": "UNKNOWN", "reason": "no verification evidence"}


def freshness_state(source_statuses: list[str]) -> dict[str, str]:
    """Summarize projection freshness from per-source availability."""
    if not source_statuses:
        return {"status": "unknown", "reason": "no sources examined"}
    if all(status == "present" for status in source_statuses):
        return {"status": "current", "reason": "all declared sources readable"}
    if all(status in ("missing", "invalid") for status in source_statuses):
        return {"status": "unknown", "reason": "no declared source readable"}
    return {"status": "stale", "reason": "some declared sources unreadable"}


def stable_key(value: Any) -> str:
    """Best-effort stable identity fragment for sorting mixed records."""
    if isinstance(value, dict):
        for field in ("id", "identity", "contract_identity", "capability"):
            candidate = value.get(field)
            if isinstance(candidate, str) and candidate:
                return candidate
        return ""
    return value if isinstance(value, str) else ""
