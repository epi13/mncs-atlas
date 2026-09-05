#!/usr/bin/env python3
"""Generate the executable MNCS admission corpus with model-derived expectations.

The corpus (``mncs/admission-corpus.json``) is the executable contract for
``mncs/admission.mncs``: every case carries ``expected`` values derived from
the rich Python admission model through :mod:`admission.mncs_glue`, so
``mncs experiment run`` verifies the MNCS module against owner-defined
semantics instead of against itself.

Regenerate after any vocabulary, adapter, glue, or scenario change::

    python3 mncs/gen_admission_corpus.py --check   # CI: fail on drift
    python3 mncs/gen_admission_corpus.py           # rewrite the corpus
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from admission import mncs_glue as glue
from admission.model import Participant, Session
from admission.router import Router
from admission.vocabulary import LIFECYCLE_STATES, capability_ids

CORPUS_PATH = ROOT / "mncs" / "admission-corpus.json"
MODULE = "mncs_atlas.admission"
I64 = {"bits": 64, "signed": True}

OK_BIT = 36028797018963968
REASON_BIT = 72057594037927936


def arg(value: int) -> dict:
    return {"integer": {"value": value, "type": dict(I64)}}


def case(case_id: str, function: str, arguments: list[int], expected: int,
         step_budget: int = 16384) -> dict:
    return {
        "id": case_id,
        "request": {
            "schema_version": "0.1",
            "target": {"module": MODULE, "function": function},
            "arguments": [arg(value) for value in arguments],
            "step_budget": step_budget,
        },
        "expected": [arg(expected)],
        "expected_status": "returned",
    }


def rich_session(table: glue.StringTable, state: str, identity: str,
                 scope: str = "", evidence: tuple[str, ...] = ()) -> Session:
    session = Session(participant=Participant(identity=identity))
    session.state = state
    session.scope = scope
    session.evidence = list(evidence)
    return session


def scalar_session_args(table: glue.StringTable, state: str, identity: str,
                        scope: str = "", evidence: int = 0,
                        conformant: int = 0) -> int:
    return glue.pack_session(
        glue.STATE_CODES[state], 0, bool(scope), table.intern(identity),
        evidence, conformant)


def build_cases() -> list[dict]:
    table = glue.StringTable()
    router = Router()
    cases: list[dict] = []
    p1 = table.intern("p1")

    outside = glue.pack_session(0, 0, False, p1)
    admitted = glue.pack_session(2, 0, False, p1)
    scoped = glue.pack_session(3, 0, True, p1)

    cases.append(case("identify-ok", "abi_identify", [outside, p1, 0],
                      glue.pack_session(1, 0, False, p1) + OK_BIT, 4096))
    cases.append(case("identify-bad-kind", "abi_identify", [outside, p1, 7],
                      outside + 5 * REASON_BIT, 4096))
    cases.append(case("admit-known", "abi_admit",
                      [glue.pack_session(1, 0, False, p1)],
                      glue.pack_session(2, 0, False, p1) + OK_BIT, 4096))
    cases.append(case("admit-outside-refused", "abi_admit", [outside],
                      outside + 2 * REASON_BIT, 4096))
    cases.append(case("bind-unbound-refused", "abi_bind_scope", [admitted, 0],
                      admitted + 4 * REASON_BIT, 4096))
    cases.append(case("bind-scope-ok", "abi_bind_scope", [admitted, 1],
                      scoped + OK_BIT, 4096))
    cases.append(case("record-evidence", "abi_record_evidence", [admitted, 3],
                      glue.pack_session(2, 0, False, p1, evidence=3), 4096))
    cases.append(case("mark-conformant", "abi_mark_conformant", [scoped, 4],
                      glue.pack_session(4, 0, True, p1, conformant=16), 4096))
    cases.append(case("mark-conformant-invalid-cap", "abi_mark_conformant",
                      [scoped, 99], scoped, 4096))

    bare15 = [0] * 13  # evidence..net_declared trailing zeros after cap/session

    def query_case(case_id: str, cap: str, session_pack: int,
                   session: Session, args_tail: list[int], **kwargs) -> None:
        flat = glue.derive_query_expectation(router, session, cap, **kwargs)
        expected = glue.pack_decision(
            flat["status"], flat["verdict"], authority=flat["authority"],
            missing=flat["missing"], need_confirmations=bool(flat["need"]),
            reason=flat["reason"])
        cases.append(case(case_id, "abi_query",
                          [glue.CAPABILITY_CODES[cap], session_pack] + args_tail,
                          expected))

    s_adm = rich_session(table, "ADMITTED", "p1")
    query_case("query-cap0-admitted", "orientation.read", admitted, s_adm,
               list(bare15))
    query_case("query-cap16-denied", "capability.grant", admitted, s_adm,
               list(bare15))
    query_case("query-cap3-unscoped", "change.propose", admitted, s_adm,
               list(bare15))

    s_sc = rich_session(table, "SCOPED", "p1", scope="s")
    evidence_bits = ((1 << glue.EVIDENCE_BITS["actions.conformant"])
                     | (1 << glue.EVIDENCE_BITS["provenance.complete"])
                     | (1 << glue.EVIDENCE_BITS["tests.passed"]))
    proposer = table.intern("p9")
    att0 = table.intern("p2")
    att1 = table.intern("p3")
    query_case(
        "query-cap12-full-evidence", "change.merge", scoped, s_sc,
        [evidence_bits, LIFECYCLE_STATES.index("confirmation"), 1, proposer,
         7, 0, att0, att1, 0, 0, 2, 0, 0],
        evidence=("actions.conformant", "provenance.complete", "tests.passed"),
        lifecycle_state="confirmation",
        action={"id": "a1", "proposed_by": "p9", "change_id": 7},
        attestations=({"by": "p2"}, {"by": "p3"}))
    query_case(
        "query-cap7-undeclared-net", "network.fetch", scoped, s_sc,
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        evidence=("session.scope",))

    # Per-capability bare-query pins: every code in the table gets its own
    # decision expectation, so table drift fails loudly per capability.
    for name in capability_ids():
        query_case(f"query-bare-{name}", name, scoped, s_sc, list(bare15))

    # Governance full-grant path: validator.modify with complete evidence
    # and two independent confirmations grants.
    gov_bits = ((1 << glue.EVIDENCE_BITS["actions.conformant"])
                | (1 << glue.EVIDENCE_BITS["provenance.complete"])
                | (1 << glue.EVIDENCE_BITS["forge.evaluation"]))
    query_case(
        "query-cap14-full-grant", "validator.modify", scoped, s_sc,
        [gov_bits, 0, 1, proposer, 7, 0, att0, att1, 0, 0, 2, 0, 0],
        evidence=("actions.conformant", "provenance.complete",
                  "forge.evaluation"),
        action={"id": "a1", "proposed_by": "p9", "change_id": 7},
        attestations=({"by": "p2"}, {"by": "p3"}))

    outside_session = rich_session(table, "OUTSIDE", "p1")
    statuses = []
    for name in capability_ids():
        decision = router.query(outside_session, name)
        statuses.append(glue.STATUS_CODES[decision["status"]])
    orient_pack = glue.pack_orientation(
        0, sum(1 for v in statuses if v == 0),
        sum(1 for v in statuses if v == 1), sum(1 for v in statuses if v == 2),
        sum(v * (4 ** i) for i, v in enumerate(statuses)))
    cases.append(case("orient-outside", "abi_orient", [outside], orient_pack,
                      300000))

    decision_pack, denial_pack = glue.derive_denial_expectation(
        router, s_sc, "change.merge")
    cases.append(case("denial-cap12", "abi_denial",
                      [glue.CAPABILITY_CODES["change.merge"], decision_pack],
                      denial_pack))

    # Bypass: logical event -> Python scan() expectation; MNCS kind code and
    # flag word are the glue-assigned scalar projection of the same event.
    bypass_events: list[tuple[str, dict, int]] = [
        ("bypass-direct-mutation",
         {"kind": "mutation", "paths": ["validators/check.py"]}, 1 << 12),
        ("bypass-self-validation",
         {"kind": "mutation", "action_id": "act-1", "paths": ["policy/gate.py"],
          "change_id": "c1", "validating_change_id": "c1"}, (1 << 0) | (1 << 1)),
        ("bypass-provenance-stripping",
         {"kind": "evidence", "provenance_stripped": True}, 1 << 2),
        ("bypass-fabricated-evidence",
         {"kind": "evidence", "digest": "not-a-digest"}, 1 << 3),
        ("bypass-undeclared-cross-repo",
         {"kind": "mutation", "paths": ["src/a.py"],
          "repos": ["mncs-fabric", "mncs-forge-mcp"]}, 1 << 4),
        ("bypass-undeclared-network",
         {"kind": "execution", "network_used": True}, 1 << 5),
        ("bypass-unauthorized-dispatch",
         {"kind": "execution", "worker_dispatched": True}, 1 << 7),
        ("bypass-ci-disabling",
         {"kind": "governance", "ci_disabled": True}, 1 << 9),
        ("bypass-promotion-outside",
         {"kind": "governance", "promoted": True, "lifecycle_to": "proposal"},
         1 << 10),
        ("bypass-none", {"kind": "mutation", "paths": ["src/a.py"]}, 0),
    ]
    for case_id, event, flags in bypass_events:
        if case_id == "bypass-none":
            from admission.bypass import scan
            assert scan([event]) == [], "none-event must produce no finding"
            expected = 0
        else:
            flat = glue.derive_bypass_expectation(event)
            expected = glue.pack_bypass(
                flat["code"], flat["severity"], flat["authority"],
                routes=flat["routes"], route_count=flat["route_count"])
        kind_code = glue.EVENT_KIND_CODES[event["kind"]]
        cases.append(case(case_id, "abi_bypass", [kind_code, 0, flags],
                          expected))

    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail if the checked-in corpus drifts")
    args = parser.parse_args()
    document = {"schema_version": "0.1", "name": "admission-abi-v1",
                "cases": build_cases()}
    rendered = json.dumps(document, indent=1) + "\n"
    if args.check:
        current = CORPUS_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(f"corpus drifts from {CORPUS_PATH}; regenerate it",
                  file=sys.stderr)
            return 1
        print(f"corpus matches ({len(document['cases'])} cases)")
        return 0
    CORPUS_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {CORPUS_PATH} ({len(document['cases'])} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
