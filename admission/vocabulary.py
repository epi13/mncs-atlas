"""Canonical participant capability vocabulary for MNCS Atlas admission.

This module is orientation data, not authority. Each capability names the
subsystem that owns the decision (``owner``) and the Atlas component id that
documents it (``component``). Atlas routes and composes; it never re-decides
what an owner has not decided.

Sensitivity classes (increasing protection):

- ``open``: safe to grant to any admitted participant (read orientation).
- ``scoped``: granted only inside an explicit session scope.
- ``protected``: additionally requires recorded evidence and, where stated,
  independent confirmation.
- ``governance``: additionally requires separation of duties: the session
  that proposes the effect cannot satisfy its own approval evidence.

``default_posture`` describes what an unknown participant gets without
evidence: ``grantable`` capabilities may be granted by admission state alone,
``conditional`` capabilities always need evidence, and ``denied`` is never
granted by Atlas-side state (only a live owning authority could allow it,
routed explicitly).
"""

from __future__ import annotations

from dataclasses import dataclass, field

VOCABULARY_VERSION = "0.4.0"

SENSITIVITIES = ("open", "scoped", "protected", "governance")
POSTURES = ("grantable", "conditional", "denied")

# Subsystem keys. Each must correspond to an Atlas component id or to the
# pseudo-owner "owning-repo" (the repository that owns the scoped resource).
OWNERS = (
    "atlas",
    "fabric",
    "rights-provenance",
    "mncs-actions",
    "mncds",
    "forge",
    "commons",
    "mncs",
    "owning-repo",
)


@dataclass(frozen=True)
class Capability:
    """One participant-facing capability with its authority ownership."""

    id: str
    description: str
    owner: str
    component: str
    sensitivity: str
    scope_kind: str
    default_posture: str
    grant_at_state: str | None = None
    evidence: tuple[str, ...] = ()
    conformant_path: tuple[str, ...] = ()


def _cap(
    id: str,
    description: str,
    owner: str,
    component: str,
    sensitivity: str,
    scope_kind: str,
    default_posture: str,
    grant_at_state: str | None = None,
    evidence: tuple[str, ...] = (),
    conformant_path: tuple[str, ...] = (),
) -> Capability:
    assert owner in OWNERS, f"unknown owner: {owner}"
    assert sensitivity in SENSITIVITIES, f"unknown sensitivity: {sensitivity}"
    assert default_posture in POSTURES, f"unknown posture: {default_posture}"
    return Capability(
        id=id,
        description=description,
        owner=owner,
        component=component,
        sensitivity=sensitivity,
        scope_kind=scope_kind,
        default_posture=default_posture,
        grant_at_state=grant_at_state,
        evidence=evidence,
        conformant_path=conformant_path,
    )


CAPABILITIES: dict[str, Capability] = {}


def _register(cap: Capability) -> Capability:
    assert cap.id not in CAPABILITIES, f"duplicate capability: {cap.id}"
    CAPABILITIES[cap.id] = cap
    return cap


# Orientation: safe for any identified participant.
_register(_cap(
    "orientation.read", "Read Atlas orientation state and component map.",
    "atlas", "atlas", "open", "ecosystem", "grantable",
    grant_at_state="KNOWN",
))
_register(_cap(
    "ecosystem.inspect", "Inspect ecosystem components, relationships, and entry points.",
    "atlas", "atlas", "open", "ecosystem", "grantable",
    grant_at_state="KNOWN",
))

# Scoped participation: granted by admission state inside an explicit scope.
_register(_cap(
    "repo.read", "Read repository content inside the session scope.",
    "owning-repo", "atlas", "scoped", "repo", "grantable",
    grant_at_state="ADMITTED",
))
_register(_cap(
    "change.propose", "Propose a change (proposal state only, never promotion).",
    "mncds", "mncds", "scoped", "repo", "grantable",
    grant_at_state="ADMITTED",
    conformant_path=("change.propose", "validate", "provide evidence", "promotion"),
))
_register(_cap(
    "repo.edit", "Edit working-tree content inside the session scope.",
    "owning-repo", "atlas", "scoped", "repo", "grantable",
    grant_at_state="SCOPED",
    evidence=("session.scope",),
    conformant_path=("change.propose", "validate", "provide evidence", "promotion"),
))
_register(_cap(
    "tests.execute", "Execute tests on Fabric workers inside the session scope.",
    "fabric", "fabric", "scoped", "execution-target", "grantable",
    grant_at_state="SCOPED",
    evidence=("session.scope", "execution.target"),
    conformant_path=("declare execution target", "worker.dispatch", "tests.execute"),
))
_register(_cap(
    "artifact.create", "Create artifacts inside the session scope with provenance.",
    "fabric", "fabric", "scoped", "repo", "grantable",
    grant_at_state="SCOPED",
    evidence=("session.scope", "provenance.recorded"),
))
_register(_cap(
    "network.fetch", "Fetch declared remote resources.",
    "fabric", "fabric", "scoped", "execution-target", "conditional",
    evidence=("session.scope", "network.declared"),
    conformant_path=("declare network use", "worker.dispatch"),
))
_register(_cap(
    "worker.dispatch", "Dispatch bounded work to Fabric execution targets.",
    "fabric", "fabric", "scoped", "execution-target", "conditional",
    evidence=("session.scope", "execution.target"),
    conformant_path=("declare execution target", "fabric placement", "worker.dispatch"),
))
_register(_cap(
    "evidence.attest", "Attach attestations to Commons evidence traces.",
    "commons", "commons", "scoped", "repo", "grantable",
    grant_at_state="SCOPED",
    evidence=("session.scope", "participant.identity"),
))
_register(_cap(
    "change.validate", "Run action validation over a proposed change.",
    "mncs-actions", "mncs-actions", "scoped", "change-set", "grantable",
    grant_at_state="SCOPED",
    evidence=("action.declared",),
    conformant_path=("declare intent as MNCS action", "change.validate"),
))

# Evidence-gated: state alone never grants these.
_register(_cap(
    "change.sign", "Sign a change with a rights attestation.",
    "rights-provenance", "rights-provenance", "protected", "change-set", "conditional",
    evidence=("provenance.complete", "participant.identity"),
    conformant_path=("change.propose", "validate", "record provenance", "change.sign"),
))
_register(_cap(
    "change.merge", "Merge a change into a protected branch.",
    "rights-provenance", "rights-provenance", "protected", "repo", "conditional",
    evidence=(
        "actions.conformant",
        "provenance.complete",
        "tests.passed",
        "independent_confirmations>=2",
    ),
    conformant_path=("change.propose", "validate", "provide evidence", "promotion"),
))
_register(_cap(
    "release.publish", "Publish a release artifact.",
    "mncs", "mncs", "protected", "repo", "conditional",
    evidence=(
        "actions.conformant",
        "provenance.complete",
        "independent_confirmations>=2",
    ),
    conformant_path=("promotion decision", "release.publish"),
))

# Governance: separation of duties is structural, not advisory.
_register(_cap(
    "validator.modify", "Modify a validator or conformance check.",
    "mncs", "mncs", "governance", "validator", "conditional",
    evidence=(
        "actions.conformant",
        "provenance.complete",
        "independent_confirmations>=2",
        "forge.evaluation",
    ),
    conformant_path=("change.propose", "forge evaluation", "independent confirmation", "promotion"),
))
_register(_cap(
    "policy.modify", "Modify policy, rights, or governance configuration.",
    "forge", "forge", "governance", "policy", "conditional",
    evidence=(
        "provenance.complete",
        "independent_confirmations>=2",
        "forge.evaluation",
    ),
    conformant_path=("change.propose", "forge evaluation", "independent confirmation", "promotion"),
))
_register(_cap(
    "capability.grant", "Grant or expand another participant's capability.",
    "rights-provenance", "rights-provenance", "governance", "capability", "denied",
    evidence=("independent_confirmations>=2",),
    conformant_path=("request capability", "owning-authority review", "scoped grant"),
))

# Ordered progression states. CONFORMANT_FOR_CAPABILITY is per-capability
# evidence satisfaction, never a global flag.
ADMISSION_STATES = (
    "OUTSIDE",
    "KNOWN",
    "ADMITTED",
    "SCOPED",
    "CONFORMANT_FOR_CAPABILITY",
)

# Sensitivity ladder: index increases with protection. Effects at a higher
# rung always need strictly stronger evidence than lower rungs.
SENSITIVITY_LADDER = ("open", "scoped", "protected", "governance")

# Rights-provenance authority scopes backing participant capabilities.
# Source: mncs-rights-provenance AUTHORITY_SCOPES (may_*); Atlas maps its
# participant vocabulary onto those scopes without redefining them.
RIGHTS_SCOPE_FOR_CAPABILITY = {
    "change.propose": "may_propose",
    "evidence.attest": "may_provide_evidence",
    "change.validate": "may_evaluate",
    "change.sign": "may_attest",
    "change.merge": "may_promote",
    "repo.edit": "may_modify_repository",
    "validator.modify": "may_approve_change_class",
    "policy.modify": "may_approve_change_class",
    "capability.grant": "may_approve",
    "release.publish": "may_promote",
}

# MNCDS lifecycle states that gate promotion-shaped capabilities.
# A proposal is never a promotion: merge/publish require confirmation or later.
LIFECYCLE_STATES = ("proposal", "validation", "confirmation", "promotion", "release")
LIFECYCLE_GATE = {
    "change.propose": "proposal",
    "change.validate": "validation",
    "change.sign": "validation",
    "change.merge": "confirmation",
    "release.publish": "promotion",
}

# Verdict lattice shared with the family: FAIL > UNKNOWN > PASS, INVALID for
# malformed queries. Atlas reuses it; it does not invent its own.
VERDICTS = ("PASS", "FAIL", "UNKNOWN", "INVALID")

# Capability query outcomes from the broker's point of view.
STATUSES = ("granted", "conditional", "denied")


def get_capability(capability_id: str) -> Capability:
    try:
        return CAPABILITIES[capability_id]
    except KeyError:
        raise UnknownCapabilityError(capability_id) from None


class UnknownCapabilityError(KeyError):
    """Raised when a capability id is outside the Atlas vocabulary."""

    def __init__(self, capability_id: str) -> None:
        super().__init__(f"unknown capability: {capability_id!r}")
        self.capability_id = capability_id


def capability_ids() -> tuple[str, ...]:
    return tuple(CAPABILITIES)


def describe_capability(capability_id: str) -> dict:
    cap = get_capability(capability_id)
    return {
        "id": cap.id,
        "description": cap.description,
        "owner": cap.owner,
        "component": cap.component,
        "sensitivity": cap.sensitivity,
        "scope_kind": cap.scope_kind,
        "default_posture": cap.default_posture,
        "grant_at_state": cap.grant_at_state,
        "evidence": list(cap.evidence),
        "conformant_path": list(cap.conformant_path),
    }
