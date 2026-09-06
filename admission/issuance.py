"""Atlas issuance authenticity (epi13/mncs-atlas#31).

A content digest proves integrity, not issuance: anyone holding the
public canonicalization can recompute sha256 over forged JSON. Authentic
issuance binds the exact issued bytes to an Atlas issuer key with
Ed25519, following the family attestation envelope convention
(algorithm ``ed25519`` plus ``key_id``, as in mncs-rights-provenance
attestations).

Ownership: Atlas decides (Router) and Atlas issuance authenticates
(this module). Harness verifies carried authority against operator trust
roots; it never decides policy. Fabric never re-decides. The semantic
contract (envelope shape, canonical signed bytes, verification
outcomes) lives in ``mncs-model::authority``; this module is the
Atlas-side host mechanism.

``cryptography`` is imported lazily so Atlas admission stays runnable
on bare interpreters (stdlib unittest gates); issuance simply requires
it. Envelope shape, additive over ``mncs.atlas-capability-decision/1``::

    "issuer": {"key_id": ..., "algorithm": "ed25519"},
    "issuer_signature": "<hex Ed25519 over canonical bytes minus
                         decision_digest and issuer_signature>"

Evidence attestations (``mncs.evidence-attestation/1``) use the same
issuer block and signature field, minus ``decision_digest``.
"""

from __future__ import annotations

import time
from typing import Any, Mapping

from .router import DECISION_DIGEST_ALG, canonical_decision_bytes, decision_digest

ISSUANCE_SIGNATURE_ALG = "ed25519"
EVIDENCE_SCHEMA = "mncs.evidence-attestation/1"


def _ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Atlas issuance needs the 'cryptography' package to sign; "
            "admission decisions without issuance stay unsigned"
        ) from exc
    return Ed25519PrivateKey


class AtlasIssuer:
    """One Atlas issuance identity: signs decisions and evidence."""

    def __init__(self, key_id: str, private_bytes: bytes) -> None:
        if not key_id:
            raise ValueError("issuer needs a key id")
        if len(private_bytes) != 32:
            raise ValueError("ed25519 private key must be 32 bytes")
        cls = _ed25519()
        self._key_id = key_id
        self._private = cls.from_private_bytes(private_bytes)

    @classmethod
    def generate(cls, key_id: str) -> "AtlasIssuer":
        private_cls = _ed25519()
        raw = private_cls.generate().private_bytes_raw()
        return cls(key_id, raw)

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def public_bytes(self) -> bytes:
        return self._private.public_key().public_bytes_raw()

    @property
    def public_hex(self) -> str:
        return self.public_bytes.hex()

    def _sign_bytes(self, payload: bytes) -> str:
        return self._private.sign(payload).hex()

    def sign_decision(self, decision: Mapping[str, Any]) -> dict[str, Any]:
        """Attach issuer authenticity to a Router decision. The signature
        covers the canonical bytes minus signature and digest (issuer
        block stays covered, binding key to payload); the content digest
        is recomputed last so it covers the signature too."""
        issued = dict(decision)
        issued.pop("decision_digest", None)
        issued.pop("issuer_signature", None)
        issued["issuer"] = {"key_id": self._key_id, "algorithm": ISSUANCE_SIGNATURE_ALG}
        signed = canonical_decision_bytes(issued)
        issued["issuer_signature"] = self._sign_bytes(signed)
        issued["decision_digest"] = decision_digest(issued)
        return issued

    def attest_evidence(
        self,
        *,
        name: str,
        participant: str,
        scope: str,
        source_subsystem: str,
        subject: str = "",
        issued_at: int | None = None,
    ) -> dict[str, Any]:
        """Attest one conditional-evidence item for a session. The
        attestation binds name, session, scope, optional subject, source
        subsystem, and issuance time to this issuer key; Harness accepts
        it for UNKNOWN-to-GRANTED promotion only when every term checks
        out against verifier trust roots."""
        if not name or not participant or not scope or not source_subsystem:
            raise ValueError("evidence attestation needs name/participant/scope/source")
        attestation: dict[str, Any] = {
            "schema_version": EVIDENCE_SCHEMA,
            "name": name,
            "participant": participant,
            "scope": scope,
            "subject": subject,
            "source_subsystem": source_subsystem,
            "issued_at": issued_at if issued_at is not None else int(time.time()),
            "issuer": {"key_id": self._key_id, "algorithm": ISSUANCE_SIGNATURE_ALG},
        }
        signed = canonical_decision_bytes(attestation)
        attestation["issuer_signature"] = self._sign_bytes(signed)
        return attestation
