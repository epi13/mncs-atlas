"""Participant/session/admission context model.

A session describes what MNCS knows about a participant. It deliberately has
no universal ``trusted`` flag: authority is per-capability, scoped, and
evidence-backed. ``CONFORMANT_FOR_CAPABILITY`` is recorded per capability in
``conformant_for``, never as a global boolean.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .vocabulary import (
    ADMISSION_STATES,
    CAPABILITIES,
    UnknownCapabilityError,
    get_capability,
)

PARTICIPANT_TYPES = ("human", "agent", "service", "unknown")

_STATE_ORDER = {name: index for index, name in enumerate(ADMISSION_STATES)}


class AdmissionError(ValueError):
    """Raised when an admission transition or session operation is invalid."""


@dataclass(frozen=True)
class Participant:
    """Who the participant claims to be, and where the claim comes from."""

    identity: str
    type: str = "unknown"
    provenance: str = "undeclared"

    def __post_init__(self) -> None:
        if not self.identity or not isinstance(self.identity, str):
            raise AdmissionError("participant identity must be a non-empty string")
        if self.type not in PARTICIPANT_TYPES:
            raise AdmissionError(f"unknown participant type: {self.type!r}")

    def to_dict(self) -> dict:
        return {
            "identity": self.identity,
            "type": self.type,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "Participant":
        if not isinstance(value, dict):
            raise AdmissionError("participant must be an object")
        try:
            return cls(
                identity=value["identity"],
                type=value.get("type", "unknown"),
                provenance=value.get("provenance", "undeclared"),
            )
        except (KeyError, TypeError) as exc:
            raise AdmissionError(f"invalid participant: {exc}") from exc


@dataclass(frozen=True)
class Grant:
    """One scoped capability grant held by a session."""

    capability: str
    scope: str
    conditions: tuple[str, ...] = ()
    expires: str = "session"
    evidence: tuple[str, ...] = ()
    granted_by: str = "atlas-admission"

    def __post_init__(self) -> None:
        if self.capability not in CAPABILITIES:
            raise UnknownCapabilityError(self.capability)
        if not self.scope:
            raise AdmissionError("grant scope must be a non-empty string")

    def to_dict(self) -> dict:
        return {
            "capability": self.capability,
            "scope": self.scope,
            "conditions": list(self.conditions),
            "expires": self.expires,
            "evidence": list(self.evidence),
            "granted_by": self.granted_by,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "Grant":
        if not isinstance(value, dict):
            raise AdmissionError("grant must be an object")
        try:
            return cls(
                capability=value["capability"],
                scope=value["scope"],
                conditions=tuple(value.get("conditions", ())),
                expires=value.get("expires", "session"),
                evidence=tuple(value.get("evidence", ())),
                granted_by=value.get("granted_by", "atlas-admission"),
            )
        except (KeyError, TypeError) as exc:
            raise AdmissionError(f"invalid grant: {exc}") from exc


@dataclass
class Session:
    """Mutable admission session: entry, context, and per-capability state."""

    participant: Participant
    state: str = "OUTSIDE"
    atlas_version: str = "0.4.0"
    policy_versions: dict[str, str] = field(default_factory=dict)
    repository_context: str = ""
    purpose: str = ""
    scope: str = ""
    grants: list[Grant] = field(default_factory=list)
    conformant_for: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.state not in _STATE_ORDER:
            raise AdmissionError(f"unknown admission state: {self.state!r}")

    # -- progression -----------------------------------------------------
    def _advance(self, target: str) -> None:
        if _STATE_ORDER[target] != _STATE_ORDER[self.state] + 1:
            raise AdmissionError(
                f"invalid admission transition: {self.state} -> {target}"
            )
        self.state = target

    def identify(self, participant: Participant) -> None:
        """OUTSIDE -> KNOWN: MNCS knows about this participant (not trust)."""
        if self.state != "OUTSIDE":
            raise AdmissionError(f"identify requires OUTSIDE, not {self.state}")
        self.participant = participant
        self._advance("KNOWN")

    def admit(self, atlas_version: str, policy_versions: dict[str, str] | None = None) -> None:
        """KNOWN -> ADMITTED: participant accepted orientation context."""
        if self.state != "KNOWN":
            raise AdmissionError(f"admit requires KNOWN, not {self.state}")
        self.atlas_version = atlas_version
        if policy_versions:
            self.policy_versions = dict(policy_versions)
        self._advance("ADMITTED")

    def bind_scope(self, scope: str, repository_context: str = "", purpose: str = "") -> None:
        """ADMITTED -> SCOPED: bind an explicit scope, repo context, purpose."""
        if self.state != "ADMITTED":
            raise AdmissionError(f"bind_scope requires ADMITTED, not {self.state}")
        if not scope:
            raise AdmissionError("scope must be a non-empty string")
        self.scope = scope
        self.repository_context = repository_context
        self.purpose = purpose
        self._advance("SCOPED")

    # -- grants and evidence ---------------------------------------------
    def add_grant(self, grant: Grant) -> None:
        if self.state not in ("SCOPED", "CONFORMANT_FOR_CAPABILITY"):
            raise AdmissionError(
                f"grants require a SCOPED session, not {self.state}"
            )
        self.grants.append(grant)

    def record_evidence(self, evidence_id: str) -> None:
        if not evidence_id:
            raise AdmissionError("evidence id must be a non-empty string")
        if evidence_id not in self.evidence:
            self.evidence.append(evidence_id)

    def mark_conformant(self, capability_id: str) -> None:
        """Record per-capability conformance (evidence-checked by the router)."""
        get_capability(capability_id)
        if capability_id not in self.conformant_for:
            self.conformant_for.append(capability_id)
        if self.state == "SCOPED":
            self.state = "CONFORMANT_FOR_CAPABILITY"

    def grants_for(self, capability_id: str) -> list[Grant]:
        return [grant for grant in self.grants if grant.capability == capability_id]

    # -- serialization ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_version": "mncs.atlas-admission/1",
            "participant": self.participant.to_dict(),
            "state": self.state,
            "environment": {
                "atlas_version": self.atlas_version,
                "policy_versions": dict(self.policy_versions),
                "repository_context": self.repository_context,
            },
            "purpose": self.purpose,
            "scope": self.scope,
            "grants": [grant.to_dict() for grant in self.grants],
            "conformant_for": list(self.conformant_for),
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, value: dict) -> "Session":
        if not isinstance(value, dict):
            raise AdmissionError("session must be an object")
        if value.get("schema_version") != "mncs.atlas-admission/1":
            raise AdmissionError("unsupported session schema_version")
        try:
            environment = value.get("environment", {})
            return cls(
                participant=Participant.from_dict(value["participant"]),
                state=value.get("state", "OUTSIDE"),
                atlas_version=environment.get("atlas_version", "0.4.0"),
                policy_versions=dict(environment.get("policy_versions", {})),
                repository_context=environment.get("repository_context", ""),
                purpose=value.get("purpose", ""),
                scope=value.get("scope", ""),
                grants=[Grant.from_dict(item) for item in value.get("grants", [])],
                conformant_for=list(value.get("conformant_for", [])),
                evidence=list(value.get("evidence", [])),
            )
        except (KeyError, TypeError) as exc:
            raise AdmissionError(f"invalid session: {exc}") from exc

    def canonical_json(self) -> str:
        """Deterministic serialization: byte-identical for identical state."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_canonical_json(cls, raw: str) -> "Session":
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AdmissionError(f"session is not valid JSON: {exc}") from exc
        return cls.from_dict(value)


def new_outside_session(
    identity: str = "anonymous",
    type: str = "unknown",
    provenance: str = "undeclared",
) -> Session:
    """Create an OUTSIDE session placeholder before identification."""
    return Session(participant=Participant(identity=identity, type=type, provenance=provenance))
