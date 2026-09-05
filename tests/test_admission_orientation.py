"""Orientation, serialization, cross-repo, and contract-sync tests.

Covers: participant discovery/orientation, machine-readable projection,
human-readable projection from the same state, serialization and protocol
stability, cross-repository authority resolution, and vocabulary/map/MNCS
shape parity.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from admission import (
    Participant,
    Router,
    Session,
    capability_ids,
    human_orientation,
    load_atlas_map,
    machine_orientation,
    new_outside_session,
)

ROOT = Path(__file__).resolve().parents[1]

MACHINE_KEYS = (
    "where_am_i",
    "what_exists",
    "what_is_my_goal",
    "what_can_i_read",
    "what_can_i_do",
    "what_can_i_not_do",
    "why_is_it_denied",
    "what_conformant_path_exists",
    "what_evidence_is_required",
    "who_has_authority",
)


def _arriving_agent() -> Session:
    """An external agent that knows almost nothing about MNCS."""
    session = new_outside_session()
    session.identify(Participant(identity="new-agent-1", type="agent",
                                provenance="external-arrival"))
    session.admit("0.4.0")
    return session


class OrientationTests(unittest.TestCase):
    def test_machine_orientation_answers_arrival_questions(self) -> None:
        state = machine_orientation(_arriving_agent())
        self.assertEqual(state["schema_version"], "mncs.atlas-orientation/1")
        self.assertEqual(state["authority"], "orientation-only")
        for key in MACHINE_KEYS:
            self.assertIn(key, state, f"machine orientation missing {key}")

    def test_orientation_exposes_ecosystem(self) -> None:
        state = machine_orientation(_arriving_agent())
        ids = {item["id"] for item in state["what_exists"]["components"]}
        for expected in ("mncs", "mncds", "rights-provenance", "fabric",
                         "forge", "commons", "mncs-actions", "atlas"):
            self.assertIn(expected, ids)
        self.assertTrue(state["what_exists"]["entry_points"])

    def test_new_agent_may_inspect_but_not_merge(self) -> None:
        state = machine_orientation(_arriving_agent())
        doable = {item["capability"] for item in state["what_can_i_do"]}
        self.assertIn("orientation.read", doable)
        self.assertIn("ecosystem.inspect", doable)
        self.assertIn("change.merge", state["why_is_it_denied"])
        self.assertIn("validator.modify", state["why_is_it_denied"])

    def test_denied_entries_teach(self) -> None:
        state = machine_orientation(_arriving_agent())
        for capability, detail in state["why_is_it_denied"].items():
            self.assertTrue(detail["reason"], capability)
            self.assertTrue(detail["authority"], capability)
        self.assertIn("change.merge", state["what_conformant_path_exists"])
        self.assertIn("change.merge", state["what_evidence_is_required"])

    def test_understanding_grants_no_authority(self) -> None:
        # Reading the whole orientation twice changes nothing about status.
        session = _arriving_agent()
        first = machine_orientation(session)
        second = machine_orientation(session)
        self.assertEqual(first["what_can_i_not_do"], second["what_can_i_not_do"])
        denied = {item["capability"] for item in second["what_can_i_not_do"]}
        self.assertIn("change.merge", denied)
        self.assertIn("release.publish", denied)
        self.assertIn("capability.grant", denied)

    def test_human_orientation_derives_from_same_state(self) -> None:
        session = _arriving_agent()
        session.bind_scope("repo(mncs-fabric)", repository_context="mncs-fabric",
                           purpose="run tests")
        text = human_orientation(session)
        machine = machine_orientation(session)
        self.assertIn("Atlas grants entry, not trust", text)
        self.assertIn(session.participant.identity, text)
        self.assertIn(session.state, text)
        machine_denied = {item["capability"] for item in machine["what_can_i_not_do"]}
        for capability in machine_denied:
            self.assertIn(capability, text,
                          f"human view omits denied capability {capability}")
        for item in machine["what_can_i_do"]:
            self.assertIn(item["capability"], text)

    def test_human_orientation_names_conformant_path(self) -> None:
        text = human_orientation(_arriving_agent())
        self.assertIn("change.propose", text)
        self.assertIn("authority", text)


class SerializationTests(unittest.TestCase):
    def test_session_round_trip(self) -> None:
        session = _arriving_agent()
        session.bind_scope("repo(x)", repository_context="x", purpose="p")
        session.record_evidence("provenance.complete")
        clone = Session.from_dict(session.to_dict())
        self.assertEqual(clone.to_dict(), session.to_dict())

    def test_canonical_json_is_deterministic(self) -> None:
        session = _arriving_agent()
        self.assertEqual(session.canonical_json(), session.canonical_json())
        clone = Session.from_canonical_json(session.canonical_json())
        self.assertEqual(clone.canonical_json(), session.canonical_json())

    def test_malformed_session_rejected(self) -> None:
        from admission import AdmissionError
        with self.assertRaises(AdmissionError):
            Session.from_canonical_json("{not json")
        with self.assertRaises(AdmissionError):
            Session.from_dict({"schema_version": "mncs.atlas-admission/1"})
        with self.assertRaises(AdmissionError):
            Session.from_dict({"schema_version": "mncs.atlas-admission/99",
                               "participant": {"identity": "a"}})
        with self.assertRaises(AdmissionError):
            Session.from_dict("not-a-dict")  # type: ignore[arg-type]

    def test_decision_schema_versions_stable(self) -> None:
        session = _arriving_agent()
        decision = Router().query(session, "repo.read")
        self.assertEqual(decision["schema_version"], "mncs.atlas-capability-decision/1")
        self.assertIn(decision["status"], ("granted", "conditional", "denied"))
        self.assertIn(decision["verdict"], ("PASS", "FAIL", "UNKNOWN", "INVALID"))
        json.dumps(decision)  # must stay JSON-serializable

    def test_orientation_is_json_stable(self) -> None:
        state = machine_orientation(_arriving_agent())
        raw = json.dumps(state, sort_keys=True, separators=(",", ":"))
        self.assertEqual(
            json.loads(raw)["schema_version"], "mncs.atlas-orientation/1")


class CrossRepositoryTests(unittest.TestCase):
    def test_authority_map_resolves_to_known_components(self) -> None:
        from admission import load_admission_map
        atlas_map = load_atlas_map()
        admission_map = load_admission_map(atlas_map=atlas_map)
        known = {item["id"] for item in atlas_map["projects"]}
        known |= {item["id"] for item in atlas_map.get("operator_components", [])}
        state = machine_orientation(_arriving_agent(), atlas_map=atlas_map,
                                    admission_map=admission_map)
        for capability, owner in state["who_has_authority"].items():
            self.assertTrue(owner, capability)
        for item in admission_map["capabilities"]:
            self.assertIn(item["component"], known, item["id"])

    def test_vocabulary_matches_published_map(self) -> None:
        from admission import load_admission_map
        from admission.vocabulary import describe_capability
        admission_map = load_admission_map()
        published = {item["id"]: item for item in admission_map["capabilities"]}
        self.assertEqual(set(published), set(capability_ids()))
        for capability_id in capability_ids():
            local = describe_capability(capability_id)
            remote = published[capability_id]
            for field in ("owner", "component", "sensitivity", "scope_kind",
                          "default_posture", "grant_at_state"):
                self.assertEqual(remote[field], local[field],
                                 f"{capability_id}.{field} drifts from vocabulary")

    def test_map_version_matches_vocabulary(self) -> None:
        from admission import load_admission_map
        from admission.vocabulary import VOCABULARY_VERSION
        atlas_map = load_atlas_map()
        admission_map = load_admission_map(atlas_map=atlas_map)
        self.assertEqual(atlas_map["schema_version"], VOCABULARY_VERSION)
        self.assertEqual(atlas_map["admission"]["document"], "admission.json")
        self.assertEqual(atlas_map["admission"]["version"], VOCABULARY_VERSION)
        self.assertEqual(admission_map["version"], VOCABULARY_VERSION)
        self.assertEqual(admission_map["schema_version"], "mncs.atlas-admission-map/1")

    def test_orientation_reports_admission_document(self) -> None:
        state = machine_orientation(_arriving_agent())
        self.assertEqual(state["admission"]["document"], "admission.json")
        self.assertEqual(state["admission"]["capability_count"], len(capability_ids()))

    def test_no_duplicate_policy_engine(self) -> None:
        # Atlas decisions always name an owning subsystem. Atlas itself owns
        # only orientation data (its chartered role); every other capability
        # routes to a subsystem authority, never to an Atlas policy verdict.
        session = _arriving_agent()
        router = Router()
        for capability_id in capability_ids():
            decision = router.query(session, capability_id)
            self.assertTrue(decision["decision_by"], capability_id)
            if capability_id in ("orientation.read", "ecosystem.inspect"):
                self.assertEqual(decision["authority"], "atlas", capability_id)
            else:
                self.assertNotEqual(decision["authority"], "atlas",
                                    f"Atlas must not own {capability_id}")


class MncsShapeParityTests(unittest.TestCase):
    RECORDS = (
        "Participant", "Grant", "SessionContext", "CapabilityEntry",
        "CapabilityDecision", "Denial",
    )

    def test_mncs_model_declares_shared_records(self) -> None:
        text = (ROOT / "mncs" / "admission-model.mncs").read_text(encoding="utf-8")
        for record in self.RECORDS:
            self.assertIn(f"record {record} {{", text,
                          f"MNCS model missing record {record}")

    def test_mncs_model_uses_bounded_collections(self) -> None:
        text = (ROOT / "mncs" / "admission-model.mncs").read_text(encoding="utf-8")
        unbounded = re.findall(r":\s*\[(\w+)\](?!\s*;)", text)
        self.assertEqual(unbounded, [],
                         f"MNCS model must bound every collection: {unbounded}")


if __name__ == "__main__":
    unittest.main()
