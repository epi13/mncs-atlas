"""Atlas issuance authenticity (epi13/mncs-atlas#31).

A content digest proves integrity, not issuance. These tests pin that a
Router decision signed by an Atlas issuer carries a verifiable Ed25519
issuer block, and that unsigned/tampered envelopes stay distinguishable.
Cryptographic verification itself is exercised by downstream hosts
(mncs-cli, Harness); here the shape, canonical bytes, and digest
coverage are pinned.

Requires the 'cryptography' package; skipped on bare interpreters
where admission must stay stdlib-only.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest

from admission import Participant, Router, new_outside_session
from admission.issuance import AtlasIssuer
from admission.router import canonical_decision_bytes

CRYPTO = importlib.util.find_spec("cryptography") is not None


def _session():
    session = new_outside_session()
    session.identify(Participant(identity="gauntlet-agent", type="agent",
                                 provenance="issuance-test"))
    session.admit("0.4.0", {"mncs": "experimental"})
    session.bind_scope("repo(mncs-harness)", repository_context="mncs-harness",
                       purpose="issuance test")
    return session


@unittest.skipUnless(CRYPTO, "cryptography package unavailable")
class IssuanceTests(unittest.TestCase):
    def test_signed_router_decision_verifies(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        issuer = AtlasIssuer.generate("atlas-test-1")
        decision = Router().query(
            _session(), "tests.execute", execution_target="controller", issuer=issuer
        )
        self.assertEqual(decision["issuer"],
                         {"key_id": "atlas-test-1", "algorithm": "ed25519"})
        signature = bytes.fromhex(decision["issuer_signature"])
        self.assertEqual(len(signature), 64)
        signed = canonical_decision_bytes(
            {k: v for k, v in decision.items()
             if k not in ("decision_digest", "issuer_signature")}
        )
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(issuer.public_hex)).verify(
            signature, signed
        )
        # The content digest covers the signature too.
        body = {k: v for k, v in decision.items() if k != "decision_digest"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode()
        self.assertEqual(decision["decision_digest"], hashlib.sha256(canonical).hexdigest())

    def test_unsigned_router_decision_carries_no_issuer(self):
        decision = Router().query(_session(), "tests.execute", execution_target="controller")
        self.assertNotIn("issuer", decision)
        self.assertNotIn("issuer_signature", decision)

    def test_attest_evidence_binds_terms(self):
        issuer = AtlasIssuer.generate("atlas-test-1")
        attestation = issuer.attest_evidence(
            name="lab.safety-cert",
            participant="e2e-agent",
            scope="repo(mncs-language)",
            source_subsystem="lab-safety",
            issued_at=1700000000,
        )
        self.assertEqual(attestation["schema_version"], "mncs.evidence-attestation/1")
        self.assertEqual(attestation["issued_at"], 1700000000)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(issuer.public_hex)).verify(
            bytes.fromhex(attestation["issuer_signature"]),
            canonical_decision_bytes(
                {k: v for k, v in attestation.items() if k != "issuer_signature"}
            ),
        )

    def test_key_id_must_be_nonempty(self):
        with self.assertRaises(ValueError):
            AtlasIssuer.generate("")


if __name__ == "__main__":
    unittest.main()
