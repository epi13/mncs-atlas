"""Parity between the rich Python admission model and the MNCS scalar ABI.

The executable contract is ``mncs/admission-corpus.json``: every case
carries ``expected`` values derived from the Python model through
:mod:`admission.mncs_glue`, so ``mncs experiment run`` checks the MNCS
module against owner-defined semantics. These tests pin the derivation
itself: the checked-in corpus must match a fresh derivation (no silent
drift), and the glue projections must cover the full vocabulary (no
capability, owner, evidence string, or path step outside the ABI).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

sys.path.insert(0, str(ROOT / "mncs"))
import gen_admission_corpus as gen

from admission import mncs_glue as glue
from admission.bypass import scan
from admission.model import Participant, Session
from admission.router import Router
from admission.vocabulary import (
    CAPABILITIES,
    OWNERS,
    RIGHTS_SCOPE_FOR_CAPABILITY,
    capability_ids,
)


def make_session(state="OUTSIDE", identity="p1", scope=""):
    session = Session(participant=Participant(identity=identity))
    session.state = state
    session.scope = scope
    return session


class CorpusDerivationTest(unittest.TestCase):
    def test_checked_in_corpus_matches_fresh_derivation(self) -> None:
        corpus = json.loads((ROOT / "mncs" / "admission-corpus.json").read_text())
        fresh = {"schema_version": "0.1", "name": "admission-abi-v1",
                 "cases": gen.build_cases()}
        self.assertEqual(corpus, fresh)

    def test_every_case_has_an_expectation(self) -> None:
        corpus = json.loads((ROOT / "mncs" / "admission-corpus.json").read_text())
        for item in corpus["cases"]:
            self.assertEqual(item["expected_status"], "returned", item["id"])
            self.assertEqual(len(item["expected"]), 1, item["id"])
            value = item["expected"][0]["integer"]
            self.assertEqual(value["type"], {"bits": 64, "signed": True})
            self.assertIsInstance(value["value"], int)


class GlueCoverageTest(unittest.TestCase):
    def test_capability_codes_cover_vocabulary(self) -> None:
        self.assertEqual(set(glue.CAPABILITY_CODES), set(capability_ids()))
        self.assertEqual(sorted(glue.CAPABILITY_CODES.values()), list(range(17)))

    def test_owner_codes_cover_owners(self) -> None:
        self.assertEqual(set(glue.OWNER_CODES), set(OWNERS))

    def test_rights_scopes_all_have_owner_codes(self) -> None:
        for capability_id in RIGHTS_SCOPE_FOR_CAPABILITY:
            self.assertIn(capability_id, CAPABILITIES)

    def test_conformant_path_strings_all_project(self) -> None:
        from admission.vocabulary import get_capability

        for capability_id in capability_ids():
            for step in get_capability(capability_id).conformant_path:
                self.assertIn(step, glue.STEP_CODES, capability_id)

    def test_bypass_routes_all_project(self) -> None:
        events = [
            {"kind": "mutation", "paths": ["validators/x.py"]},
            {"kind": "mutation", "action_id": "a",
             "paths": ["policy/g.py"], "change_id": "c",
             "validating_change_id": "c"},
            {"kind": "mutation", "paths": ["src/a.py"],
             "repos": ["r1", "r2"]},
            {"kind": "evidence", "provenance_stripped": True},
            {"kind": "evidence", "digest": "bad"},
            {"kind": "execution", "network_used": True},
            {"kind": "execution", "worker_dispatched": True},
            {"kind": "governance", "ci_disabled": True},
            {"kind": "governance", "promoted": True,
             "lifecycle_to": "proposal"},
        ]
        codes = set()
        for event in events:
            flat = glue.derive_bypass_expectation(event)
            codes.add(flat["code"])
            self.assertIn(flat["authority"], glue.OWNER_CODES.values())
            for step in scan([event])[0]["conformant_route"]:
                self.assertIn(step, glue.STEP_CODES)
        self.assertEqual(codes, set(range(1, 10)))

    def test_query_derivation_covers_all_capabilities_bare(self) -> None:
        router = Router()
        session = make_session("SCOPED", scope="s")
        seen_statuses = set()
        for capability_id in capability_ids():
            flat = glue.derive_query_expectation(router, session, capability_id)
            seen_statuses.add(flat["status"])
            self.assertIn(flat["verdict"], (0, 1, 2))
            self.assertIn(flat["authority"], glue.OWNER_CODES.values())
            self.assertLess(flat["reason"], 32)
        self.assertEqual(seen_statuses, {0, 1, 2})

    def test_session_pack_round_trip(self) -> None:
        packed = glue.pack_session(3, 0, True, 7, evidence=5, conformant=9)
        flat = glue.unpack_session(packed)
        self.assertEqual(
            (flat["state"], flat["kind"], flat["scope_bound"],
             flat["identity"], flat["evidence"], flat["conformant"], flat["ok"]),
            (3, 0, 1, 7, 5, 9, 0))

    def test_site_catalog_matches_executable_contract(self) -> None:
        """site/admission.json rows agree with the corpus bare decisions.

        The catalog prose stays in the vocabulary (fixed-envelope bound);
        the scalar code table lives in the MNCS module. This test binds
        them: every catalog row's owner must equal the authority of the
        model-derived bare-query decision the corpus pins, and a denied
        posture must surface as a denied decision on the never-granted
        reason.
        """
        from admission.orientation import load_admission_map

        admission_map = load_admission_map()
        rows = {item["id"]: item for item in admission_map["capabilities"]}
        corpus = json.loads(
            (ROOT / "mncs" / "admission-corpus.json").read_text())
        bare = {}
        for item in corpus["cases"]:
            if item["id"].startswith("query-bare-"):
                bare[item["id"][len("query-bare-"):]] = (
                    item["expected"][0]["integer"]["value"])
        self.assertEqual(set(bare), set(capability_ids()))
        for capability_id in capability_ids():
            flat = glue.unpack_decision(bare[capability_id])
            row = rows[capability_id]
            self.assertEqual(
                flat["authority"], glue.OWNER_CODES[row["owner"]],
                capability_id)
            if row["default_posture"] == "denied":
                self.assertEqual(flat["status"], 2, capability_id)
                self.assertEqual(flat["reason"], 10, capability_id)
            else:
                self.assertNotEqual(flat["reason"], 10, capability_id)

    def test_decision_pack_round_trip(self) -> None:
        packed = glue.pack_decision(2, 1, authority=2, missing=40,
                                    need_confirmations=True, reason=3)
        self.assertEqual(glue.unpack_decision(packed), {
            "status": 2, "verdict": 1, "malformed": 0, "authority": 2,
            "missing": 40, "need_confirmations": 1, "reason": 3})


if __name__ == "__main__":
    unittest.main()
