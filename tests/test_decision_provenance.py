"""Decision provenance binding (epi13/mncs-atlas#28).

Every capability decision must carry the context it was issued for plus a
content digest, so downstream enforcement (mncs-harness) can distinguish an
Atlas-issued grant from a fabricated Atlas-shaped object.
"""

from __future__ import annotations

import copy
import unittest

from admission import Participant, Router, new_outside_session
from admission.router import (
    DECISION_DIGEST_ALG,
    canonical_decision_bytes,
    decision_digest,
)


def _scoped_session(identity: str = "agent-7"):
    session = new_outside_session()
    session.identify(Participant(identity=identity, type="agent",
                                provenance="external-arrival"))
    session.admit("0.4.0", {"mncs": "experimental"})
    session.bind_scope("repo(mncs-fabric)", repository_context="mncs-fabric",
                       purpose="run tests")
    return session


class DecisionProvenanceTests(unittest.TestCase):
    def test_decision_carries_digest_session_and_target(self) -> None:
        decision = Router().query(
            _scoped_session(), "tests.execute",
            execution_target="mncs:target:research-bytecode-0.1",
        )
        self.assertEqual(decision["decision_digest_alg"], DECISION_DIGEST_ALG)
        self.assertEqual(decision["decision_digest"], decision_digest(decision))
        self.assertEqual(
            decision["session"],
            {"participant": "agent-7", "scope": "repo(mncs-fabric)"},
        )
        self.assertEqual(
            decision["execution_target"], "mncs:target:research-bytecode-0.1"
        )

    def test_digest_recomputation_is_stable(self) -> None:
        session = _scoped_session()
        first = Router().query(session, "orientation.read")
        second = Router().query(session, "orientation.read")
        self.assertEqual(first["decision_digest"], second["decision_digest"])

    def test_post_issuance_edit_breaks_digest(self) -> None:
        decision = Router().query(_scoped_session(), "orientation.read")
        forged = copy.deepcopy(decision)
        forged["status"] = "denied"
        forged["verdict"] = "FAIL"
        self.assertNotEqual(
            forged["decision_digest"], decision_digest(forged),
            "a status flip after issuance must invalidate the digest",
        )

    def test_digest_covers_session_echo(self) -> None:
        decision = Router().query(_scoped_session("agent-7"), "orientation.read")
        replayed = copy.deepcopy(decision)
        replayed["session"] = {"participant": "intruder-9", "scope": "repo(other)"}
        self.assertNotEqual(
            replayed["decision_digest"], decision_digest(replayed),
            "a session swap after issuance must invalidate the digest",
        )

    def test_canonical_bytes_exclude_digest_field(self) -> None:
        decision = Router().query(_scoped_session(), "orientation.read")
        renumbered = copy.deepcopy(decision)
        renumbered["decision_digest"] = "0" * 64
        self.assertEqual(
            canonical_decision_bytes(renumbered),
            canonical_decision_bytes(decision),
            "the digest field itself must not participate in the digest",
        )

    def test_scope_override_echoes_request_scope(self) -> None:
        decision = Router().query(
            _scoped_session(), "orientation.read", scope="repo(mncs-harness)"
        )
        self.assertEqual(decision["scope"], "repo(mncs-harness)")
        self.assertEqual(decision["session"]["scope"], "repo(mncs-harness)")


if __name__ == "__main__":
    unittest.main()
