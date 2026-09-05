"""Admission model, router, denial, and bypass tests.

Covers: unknown-participant admission, progression, scoped grants, denied
and conditional capabilities, structured denials with conformant paths,
authority routing, rights/actions/lifecycle integration, protected
capabilities, self-authorization protection, and bypass detection.
"""

from __future__ import annotations

import unittest

from admission import (
    AdmissionError,
    Grant,
    Participant,
    Router,
    Session,
    UnknownCapabilityError,
    build_denial,
    capability_ids,
    denial_from_decision,
    describe_capability,
    get_capability,
    new_outside_session,
    scan,
)


def _scoped_session(identity: str = "agent-7") -> Session:
    session = new_outside_session()
    session.identify(Participant(identity=identity, type="agent",
                                provenance="external-arrival"))
    session.admit("0.4.0", {"mncs": "experimental"})
    session.bind_scope("repo(mncs-fabric)", repository_context="mncs-fabric",
                       purpose="run tests")
    return session


class AdmissionProgressionTests(unittest.TestCase):
    def test_unknown_participant_admission(self) -> None:
        session = new_outside_session()
        self.assertEqual(session.state, "OUTSIDE")
        session.identify(Participant(identity="stranger-1"))
        self.assertEqual(session.state, "KNOWN")
        self.assertEqual(session.participant.type, "unknown")
        # KNOWN means MNCS knows about the participant, not that it is trusted.
        self.assertFalse(hasattr(session, "trusted"))

    def test_full_progression(self) -> None:
        session = _scoped_session()
        self.assertEqual(session.state, "SCOPED")
        session.mark_conformant("change.merge")
        self.assertEqual(session.state, "CONFORMANT_FOR_CAPABILITY")
        self.assertIn("change.merge", session.conformant_for)

    def test_conformance_is_per_capability_not_global(self) -> None:
        session = _scoped_session()
        session.mark_conformant("change.merge")
        self.assertNotIn("release.publish", session.conformant_for)

    def test_invalid_transitions_rejected(self) -> None:
        session = new_outside_session()
        with self.assertRaises(AdmissionError):
            session.admit("0.4.0")  # OUTSIDE -> ADMITTED skips KNOWN
        with self.assertRaises(AdmissionError):
            session.bind_scope("repo(x)")  # OUTSIDE -> SCOPED
        session.identify(Participant(identity="a"))
        with self.assertRaises(AdmissionError):
            session.identify(Participant(identity="b"))  # identify twice
        with self.assertRaises(AdmissionError):
            session.bind_scope("repo(x)")  # KNOWN -> SCOPED skips ADMITTED
        with self.assertRaises(AdmissionError):
            session.add_grant(Grant(capability="repo.read", scope="repo(x)"))

    def test_empty_scope_and_evidence_rejected(self) -> None:
        session = new_outside_session()
        session.identify(Participant(identity="a"))
        session.admit("0.4.0")
        with self.assertRaises(AdmissionError):
            session.bind_scope("")
        with self.assertRaises(AdmissionError):
            session.record_evidence("")
        with self.assertRaises(AdmissionError):
            Participant(identity="")
        with self.assertRaises(AdmissionError):
            Participant(identity="a", type="superuser")

    def test_unknown_capability_rejected(self) -> None:
        with self.assertRaises(UnknownCapabilityError):
            get_capability("root.everything")
        session = _scoped_session()
        with self.assertRaises(UnknownCapabilityError):
            Router().query(session, "root.everything")
        with self.assertRaises(UnknownCapabilityError):
            session.mark_conformant("root.everything")

    def test_no_universal_trusted_flag(self) -> None:
        session = _scoped_session()
        self.assertFalse(hasattr(session, "trusted"))
        self.assertFalse(hasattr(session.participant, "trusted"))


class CapabilityDiscoveryTests(unittest.TestCase):
    def test_vocabulary_covers_expected_capabilities(self) -> None:
        ids = set(capability_ids())
        for expected in ("ecosystem.inspect", "repo.read", "repo.edit",
                         "tests.execute", "artifact.create", "network.fetch",
                         "worker.dispatch", "change.propose", "change.validate",
                         "change.sign", "change.merge", "release.publish",
                         "validator.modify", "policy.modify"):
            self.assertIn(expected, ids)

    def test_every_capability_names_owner_and_path(self) -> None:
        for capability_id in capability_ids():
            info = describe_capability(capability_id)
            self.assertTrue(info["owner"], capability_id)
            self.assertTrue(info["component"], capability_id)
            self.assertIn(info["sensitivity"], ("open", "scoped", "protected", "governance"))


class BrokerDecisionTests(unittest.TestCase):
    def test_scoped_granted_capability(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "repo.edit")
        self.assertEqual(decision["status"], "granted")
        self.assertEqual(decision["verdict"], "PASS")
        self.assertEqual(decision["scope"], "repo(mncs-fabric)")

    def test_outside_session_grants_nothing(self) -> None:
        session = new_outside_session()
        decision = Router().query(session, "orientation.read")
        self.assertNotEqual(decision["status"], "granted")

    def test_denied_capability(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "change.merge")
        self.assertEqual(decision["status"], "denied")
        self.assertEqual(decision["verdict"], "FAIL")

    def test_capability_grant_never_granted_by_state(self) -> None:
        session = _scoped_session()
        session.mark_conformant("capability.grant")
        decision = Router().query(session, "capability.grant")
        self.assertEqual(decision["status"], "denied")

    def test_conditional_capability_names_missing(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "tests.execute")
        self.assertEqual(decision["status"], "conditional")
        self.assertIn("execution.target", decision["missing"])

    def test_structured_denial(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "change.merge")
        denial = denial_from_decision(decision, requested="direct protected-state mutation")
        self.assertIsNotNone(denial)
        assert denial is not None
        self.assertEqual(denial["outcome"], "ACTION_DENIED")
        self.assertEqual(denial["requested"], "direct protected-state mutation")
        self.assertTrue(denial["reason"], "denial must explain why")
        self.assertEqual(denial["authority"], "rights-provenance")
        self.assertTrue(denial["missing"], "denial must name missing evidence")

    def test_conformant_path_offered(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "change.merge")
        denial = denial_from_decision(decision)
        assert denial is not None
        self.assertEqual(
            denial["conformant_path"],
            ["change.propose", "validate", "provide evidence", "promotion"],
        )

    def test_granted_decision_has_no_denial(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "repo.edit")
        self.assertIsNone(denial_from_decision(decision))

    def test_build_denial_shape(self) -> None:
        denial = build_denial(
            requested="validator.modify", reason="capability not granted",
            authority="mncs", missing=["independent_confirmations>=2"],
            conformant_path=["change.propose", "promotion"],
        )
        self.assertEqual(denial["schema_version"], "mncs.atlas-denial/1")
        self.assertEqual(denial["outcome"], "ACTION_DENIED")


class AuthorityRoutingTests(unittest.TestCase):
    def test_merge_routed_to_rights_and_lifecycle(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "change.merge")
        self.assertEqual(decision["authority"], "rights-provenance")
        self.assertIn("rights-provenance", decision["decision_by"])
        self.assertIn("mncds", decision["decision_by"])
        self.assertIn("mncs-actions", decision["decision_by"])

    def test_execution_routed_to_fabric(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "tests.execute", execution_target="linux-x86_64")
        self.assertEqual(decision["authority"], "fabric")
        self.assertIn("fabric", decision["decision_by"])

    def test_validation_routed_to_actions(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "change.validate", action={"id": "act-1"})
        self.assertEqual(decision["authority"], "mncs-actions")
        self.assertIn("mncs-actions", decision["decision_by"])

    def test_governance_routed_to_forge(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "policy.modify",
            action={"id": "act-9", "proposed_by": "agent-7"},
            evidence=("provenance.complete", "forge.evaluation"),
            attestations=({"by": "alice", "claim": "review"},
                          {"by": "bob", "claim": "review"}),
            lifecycle_state="confirmation",
        )
        self.assertIn("forge", decision["decision_by"])
        self.assertEqual(decision["status"], "granted")

    def test_pluggable_live_authority(self) -> None:
        from admission import AuthorityAdapter, AuthorityFinding

        class LiveRights(AuthorityAdapter):
            name = "rights-provenance"

            def handles(self, capability_id: str) -> bool:
                return capability_id == "change.sign"

            def evaluate(self, query) -> AuthorityFinding:  # type: ignore[no-untyped-def]
                return AuthorityFinding(
                    authority=self.name, verdict="PASS",
                    reason="live rights service attests scope may_attest.")

        from admission import AdmissionPostureAdapter
        router = Router(adapters=[AdmissionPostureAdapter(), LiveRights()])
        decision = router.query(_scoped_session(), "change.sign")
        self.assertEqual(decision["status"], "granted")
        self.assertIn("live rights service", decision["reason"])


class EvidenceLifecycleTests(unittest.TestCase):
    def test_merge_granted_with_full_evidence(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "change.merge",
            evidence=("actions.conformant", "provenance.complete", "tests.passed"),
            attestations=({"by": "alice", "claim": "review"},
                          {"by": "bob", "claim": "review"}),
            lifecycle_state="confirmation",
            action={"id": "act-1", "proposed_by": "agent-7"},
        )
        self.assertEqual(decision["status"], "granted")
        self.assertEqual(decision["missing"], [])

    def test_proposal_is_not_promotion(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "change.merge",
            evidence=("actions.conformant", "provenance.complete", "tests.passed"),
            attestations=({"by": "alice", "claim": "review"},
                          {"by": "bob", "claim": "review"}),
            lifecycle_state="proposal",  # valid proposal, wrong lifecycle state
            action={"id": "act-1", "proposed_by": "agent-7"},
        )
        self.assertEqual(decision["status"], "denied")

    def test_undeclared_merge_is_direct_mutation(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "change.merge",
            evidence=("actions.conformant", "provenance.complete", "tests.passed"),
            attestations=({"by": "alice", "claim": "review"},
                          {"by": "bob", "claim": "review"}),
            lifecycle_state="confirmation",
            action={},  # no declared action
        )
        self.assertEqual(decision["status"], "denied")
        self.assertIn("action.declared", decision["missing"])

    def test_undeclared_network_refused(self) -> None:
        session = _scoped_session()
        decision = Router().query(session, "network.fetch")
        self.assertEqual(decision["status"], "denied")
        self.assertIn("network.declared", decision["missing"])

    def test_protected_capability_denied_bare(self) -> None:
        session = _scoped_session()
        for capability_id in ("validator.modify", "policy.modify", "release.publish"):
            decision = Router().query(session, capability_id)
            self.assertEqual(decision["status"], "denied", capability_id)


class SelfAuthorizationTests(unittest.TestCase):
    def test_self_validation_refused(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "validator.modify",
            evidence=("actions.conformant", "provenance.complete", "forge.evaluation"),
            attestations=({"by": "alice", "claim": "review"},
                          {"by": "bob", "claim": "review"}),
            lifecycle_state="confirmation",
            action={"id": "act-1", "proposed_by": "agent-7",
                    "change_id": "c1", "validating_change_id": "c1"},
        )
        self.assertEqual(decision["status"], "denied")
        self.assertIn("Self-validation", decision["reason"])

    def test_self_attestation_does_not_count(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "change.merge",
            evidence=("actions.conformant", "provenance.complete", "tests.passed"),
            attestations=({"by": "agent-7", "claim": "self-approval"},
                          {"by": "alice", "claim": "review"}),
            lifecycle_state="confirmation",
            action={"id": "act-1", "proposed_by": "agent-7"},
        )
        # Only alice counts; one independent confirmation is not enough.
        self.assertNotEqual(decision["status"], "granted")

    def test_proposer_attestation_does_not_count(self) -> None:
        session = _scoped_session()
        decision = Router().query(
            session, "change.merge",
            evidence=("actions.conformant", "provenance.complete", "tests.passed"),
            attestations=({"by": "proposer-p", "claim": "looks good"},
                          {"by": "proposer-p", "claim": "again"}),
            lifecycle_state="confirmation",
            action={"id": "act-1", "proposed_by": "proposer-p"},
        )
        self.assertNotEqual(decision["status"], "granted")


class BypassDetectionTests(unittest.TestCase):
    def test_direct_protected_mutation(self) -> None:
        findings = scan([{"kind": "mutation", "actor": "agent-7",
                          "paths": ["validators/check.py"]}])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "DIRECT_PROTECTED_MUTATION")
        self.assertTrue(findings[0]["conformant_route"])

    def test_declared_action_is_not_bypass(self) -> None:
        findings = scan([{"kind": "mutation", "actor": "agent-7",
                          "action_id": "act-1",
                          "paths": ["validators/check.py"],
                          "change_id": "c1", "validating_change_id": "c2"}])
        self.assertEqual(findings, [])

    def test_self_validation_finding(self) -> None:
        findings = scan([{"kind": "mutation", "actor": "agent-7",
                          "action_id": "act-1", "paths": ["policy/gate.py"],
                          "change_id": "c1", "validating_change_id": "c1"}])
        self.assertEqual(findings[0]["code"], "SELF_VALIDATION")

    def test_provenance_stripping(self) -> None:
        findings = scan([{"kind": "evidence", "actor": "agent-7",
                          "provenance_stripped": True}])
        self.assertEqual(findings[0]["code"], "PROVENANCE_STRIPPING")

    def test_fabricated_evidence(self) -> None:
        findings = scan([{"kind": "evidence", "actor": "agent-7",
                          "digest": "not-a-digest"}])
        self.assertEqual(findings[0]["code"], "FABRICATED_EVIDENCE")
        valid = scan([{"kind": "evidence", "actor": "agent-7",
                       "digest": "a" * 64}])
        self.assertEqual(valid, [])

    def test_undeclared_cross_repo(self) -> None:
        findings = scan([{"kind": "mutation", "actor": "agent-7",
                          "paths": ["src/a.py"], "repos": ["mncs-fabric", "mncs-forge-mcp"]}])
        self.assertEqual(findings[0]["code"], "UNDECLARED_CROSS_REPO_MUTATION")

    def test_undeclared_network_and_dispatch(self) -> None:
        findings = scan([{"kind": "execution", "actor": "agent-7",
                          "network_used": True}])
        self.assertEqual(findings[0]["code"], "UNDECLARED_NETWORK_USE")
        findings = scan([{"kind": "execution", "actor": "agent-7",
                          "worker_dispatched": True}])
        self.assertEqual(findings[0]["code"], "UNAUTHORIZED_WORKER_DISPATCH")

    def test_ci_disabling_and_promotion_outside_lifecycle(self) -> None:
        findings = scan([{"kind": "governance", "actor": "agent-7", "ci_disabled": True}])
        self.assertEqual(findings[0]["code"], "CI_CONFORMANCE_DISABLING")
        findings = scan([{"kind": "governance", "actor": "agent-7",
                          "promoted": True, "lifecycle_to": "proposal"}])
        self.assertEqual(findings[0]["code"], "PROMOTION_OUTSIDE_LIFECYCLE")
        ok = scan([{"kind": "governance", "actor": "agent-7",
                    "promoted": True, "lifecycle_to": "confirmation"}])
        self.assertEqual(ok, [])

    def test_unknown_event_kinds_ignored(self) -> None:
        self.assertEqual(scan([{"kind": "telepathy"}]), [])
        self.assertEqual(scan(["not-a-dict"]), [])


if __name__ == "__main__":
    unittest.main()
