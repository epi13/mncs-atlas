"""Structured denials: a refused operation teaches the conformant route.

Every denial names what was requested, why it was refused, which subsystem
owns the decision, what is missing, and which conformant path exists.
A denial without a conformant path is recorded explicitly as such; Atlas
never invents a path the owning subsystem has not declared.
"""

from __future__ import annotations


def build_denial(
    requested: str,
    reason: str,
    authority: str,
    missing: list[str] | tuple[str, ...] = (),
    conformant_path: list[str] | tuple[str, ...] = (),
    evidence_required: list[str] | tuple[str, ...] = (),
    scope: str = "",
) -> dict:
    return {
        "schema_version": "mncs.atlas-denial/1",
        "outcome": "ACTION_DENIED",
        "requested": requested,
        "reason": reason,
        "authority": authority,
        "missing": list(missing),
        "evidence_required": list(evidence_required),
        "conformant_path": list(conformant_path),
        "scope": scope,
    }


def denial_from_decision(decision: dict, requested: str = "") -> dict | None:
    """Project a router ``denied`` decision into the ACTION_DENIED shape."""
    if decision.get("status") != "denied":
        return None
    return build_denial(
        requested=requested or decision.get("capability", ""),
        reason=decision.get("reason", ""),
        authority=decision.get("authority", ""),
        missing=decision.get("missing", ()),
        conformant_path=decision.get("conformant_path", ()),
        evidence_required=decision.get("evidence_required", ()),
        scope=decision.get("scope", ""),
    )
