"""Canonical Journal event log tests: mechanics, policy refusals, tampering.

Mechanical tests run through FakeEvaluator, an explicit test double for the
MNCS policy verdicts. It exists so chain/render/refusal behavior can be
proven without a toolchain; it never authorizes anything. Live-toolchain
tests below (gated on MNCS_JOURNAL_EVALUATOR) prove the same scenarios
through real mncs.family.journal.v1 execution, which is the only parity
that matters.

Interpreter split: chain, digest, link, refusal, and projection tests use
unsigned raw events and run on bare stdlib-only interpreters (like Atlas
CI). Anything that signs or verifies signatures skips without the
'cryptography' package, following the test_issuance.py precedent.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from journal_maintainer import journal_events as je

ROOT = Path(__file__).resolve().parents[1]

# Deterministic test-only issuer key. Never an Atlas trust root: production
# keys are operator-managed and published via site/journal-events/KEYS.json.
TEST_KEY_ID = "journal-test-1"
TEST_PRIVATE = bytes(range(32))


def _finite_name(value):
    return value["finite"]["variant_identity"].rsplit("::", 1)[-1]


def _fields(value):
    return {name: item for name, item in value["record"]["fields"]}


def _int(value):
    return value["integer"]["value"]


def _bool(value):
    return value["boolean"]["value"]


class FakeEvaluator(je.PolicyEvaluator):
    """Test double mirroring the journal corpus expectations.

    Any drift between this double and mncs.family.journal.v1 is caught by
    the live-toolchain tests, which replay the refusal scenarios through
    real MNCS execution.
    """

    def __init__(self, backend="fake-test-double"):
        self._backend = backend

    @property
    def identity(self):
        return {
            "module": je.MNCS_JOURNAL_MODULE,
            "evaluator": "fake-test-double",
            "backend": self._backend,
        }

    def _gate(self, tally):
        Casino = _fields(tally)
        required = _int(Casino["required"])
        satisfied = _int(Casino["satisfied"])
        missing = _int(Casino["missing_refs"])
        stale = _int(Casino["stale_refs"])
        ok = _bool(Casino["evidence_ok"])
        if required <= 0:
            return "UNKNOWN"
        if satisfied < 0 or missing < 0 or stale < 0:
            return "FAIL"
        if satisfied > required:
            return "FAIL"
        if stale > 0:
            return "FAIL"
        if ok:
            if satisfied == required and missing == 0:
                return "PASS"
            return "UNKNOWN"
        return "FAIL"

    def evaluate(
        self,
        *,
        tally,
        validator,
        duplicate,
        model_only,
        trust_from,
        trust_event,
        render_guard,
    ):
        gate = self._gate(tally)
        if duplicate:
            admission, reason = "Reject", 3
        elif model_only:
            admission, reason = "Reject", 4
        elif validator == "FAIL":
            admission, reason = "Reject", 1
        elif validator == "UNKNOWN":
            admission, reason = "Hold", 5
        elif gate == "PASS":
            admission, reason = "Admit", 0
        elif gate == "FAIL":
            admission, reason = "Reject", 2
        else:
            admission, reason = "Hold", 5
        upgrades = {
            ("observed", "LocalProof"): "locally_proven",
            ("locally_proven", "IndependentConfirmation"): "independently_confirmed",
            ("independently_confirmed", "CommonsPromotion"): "commons_promoted",
        }
        stays = {
            ("locally_proven", "LocalProof"),
            ("independently_confirmed", "LocalProof"),
            ("independently_confirmed", "IndependentConfirmation"),
            ("commons_promoted", "LocalProof"),
            ("commons_promoted", "IndependentConfirmation"),
            ("commons_promoted", "CommonsPromotion"),
        }
        if trust_from == "legacy_unattested":
            accepted, after, treason = False, trust_from, 3
        elif (trust_from, trust_event) in upgrades:
            following = upgrades[(trust_from, trust_event)]
            if gate == "PASS":
                accepted, after, treason = True, following, 0
            else:
                accepted, after, treason = False, following, 2
        elif (trust_from, trust_event) in stays:
            accepted, after, treason = True, trust_from, 0
        else:
            accepted, after, treason = False, trust_from, 1
        guard = _fields(render_guard)
        if _bool(guard["security_detail"]):
            render_public = _bool(guard["redaction_reviewed"])
        else:
            render_public = gate == "PASS"
        digest = hashlib.sha256(
            json.dumps(
                {"gate": gate, "admission": admission, "trust": after},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return je.MncsVerdicts(
            gate=gate,
            admission=admission,
            admission_reason=reason,
            trust_accepted=accepted,
            trust_following=after,
            trust_reason=treason,
            render_public=render_public,
            backend=self._backend,
            result_digest="sha256:" + digest,
        )


class HoldingEvaluator(je.PolicyEvaluator):
    @property
    def identity(self):
        return {
            "module": je.MNCS_JOURNAL_MODULE,
            "evaluator": "holding",
            "backend": "none",
        }

    def evaluate(self, **kwargs):
        raise je.EvaluatorUnavailable("toolchain absent in this test")


def make_log(test):
    tmp = Path(tempfile.mkdtemp(prefix="mncs-journal-test-"))
    test.addCleanup(shutil.rmtree, tmp, True)
    return je.EventLog(tmp / "log")


def make_proposal(head="genesis", **over):
    params = {
        "project": "epi13/mncs-atlas",
        "event_kind": "pressure.discovered",
        "subject": "test pressure",
        "previous_state": "unknown",
        "resulting_state": "observed",
        "evidence": [{"id": "e1", "kind": "commit", "uri": "abc123"}],
        "provenance": {"producer": "test", "synthesizer": "heuristic"},
        "validators": [{"name": "test-validator", "verdict": "PASS", "ref": "t1"}],
        "previous_event_digest": head,
    }
    params.update(over)
    return je.build_proposal(**params)


def admit_ok(test, log, proposal, evaluator=None, trust_event="LocalProof"):
    result = je.admit(
        log,
        proposal,
        evaluator or FakeEvaluator(),
        TEST_KEY_ID,
        TEST_PRIVATE,
        trust_event=trust_event,
    )
    test.assertTrue(result.admitted, f"expected admission: {result.reason}")
    return result


CRYPTO = je.crypto_available()

NEEDS_CRYPTO = "Ed25519 issuance unavailable ('cryptography' package missing)"


def write_raw_event(log, content):
    """Write a self-consistent but unsigned event file for chain tests.

    Digests recompute under stdlib hashlib; only the signature is
    synthetic, so chain/link/tamper mechanics run on bare interpreters
    while authenticity stays in the crypto-gated tests.
    """
    event = dict(content)
    event["event_id"] = je.compute_event_id(event)
    event.setdefault("issuer", {"key_id": "raw-test", "algorithm": "ed25519"})
    event["issuer_signature"] = "0" * 128
    event["event_digest"] = je.compute_event_digest(event)
    path = log.root / f"{event['event_id']}.json"
    log.root.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return event


def raw_content(head="genesis", **over):
    content = make_proposal(head=head, **over)
    content["trust"] = "locally_proven"
    content["mncs_evaluation"] = {"verdicts": {"render_public": True}}
    return content


def set_head(log, digest):
    (log.root / "HEAD").write_text(digest + "\n", encoding="utf-8")


class ProposalTests(unittest.TestCase):
    def test_propose_and_query_roundtrip(self):
        log = make_log(self)
        receipt = je.propose(log, make_proposal(), author="gauntlet-agent")
        self.assertTrue(receipt.event_id.startswith("je-"))
        rows = je.query(log)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].admitted)
        self.assertEqual(rows[0].trust, "proposal")
        self.assertEqual(log.event_files(), [])

    def test_propose_rejects_unknown_kind(self):
        log = make_log(self)
        with self.assertRaises(je.EventLogError):
            je.propose(
                log, make_proposal(event_kind="vibes.happened"), author="gauntlet-agent"
            )

    def test_propose_rejects_empty_evidence(self):
        log = make_log(self)
        with self.assertRaises(je.EventLogError):
            je.propose(log, make_proposal(evidence=[]), author="gauntlet-agent")

    def test_propose_rejects_tampered_event_id(self):
        log = make_log(self)
        proposal = make_proposal()
        proposal["subject"] = "rewritten after id computation"
        with self.assertRaises(je.EventLogError):
            je.propose(log, proposal, author="gauntlet-agent")

    def test_propose_needs_author(self):
        log = make_log(self)
        with self.assertRaises(je.EventLogError):
            je.propose(log, make_proposal(), author="  ")


class AdmitMechanicalTests(unittest.TestCase):
    @unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
    def test_admit_happy_path_advances_head(self):
        log = make_log(self)
        proposal = make_proposal()
        je.propose(log, proposal, author="gauntlet-agent")
        result = admit_ok(self, log, proposal)
        self.assertEqual(log.head(), result.event["event_digest"])
        self.assertEqual(result.event["trust"], "locally_proven")
        self.assertFalse((log.proposals_dir / f"{result.event_id}.json").exists())
        rows = je.query(log)
        self.assertTrue(rows[0].admitted)

    @unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
    def test_admit_records_mncs_evaluation(self):
        log = make_log(self)
        result = admit_ok(self, log, make_proposal())
        evaluation = result.event["mncs_evaluation"]
        self.assertEqual(evaluation["module"], je.MNCS_JOURNAL_MODULE)
        self.assertEqual(evaluation["verdicts"]["admission"]["verdict"], "Admit")

    @unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
    def test_admit_chains_second_event(self):
        log = make_log(self)
        first = admit_ok(self, log, make_proposal())
        second_proposal = make_proposal(
            head=first.event["event_digest"],
            event_kind="pressure.resolved",
            subject="second pressure",
        )
        second = admit_ok(self, log, second_proposal)
        self.assertEqual(
            second.event["previous_event_digest"], first.event["event_digest"]
        )
        self.assertEqual(je.verify_chain(log), [])

    def test_admit_rejects_fork(self):
        log = make_log(self)
        first = write_raw_event(log, raw_content())
        set_head(log, first["event_digest"])
        fork = make_proposal(head="genesis", subject="forked history")
        result = je.admit(log, fork, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_EVIDENCE_REFUSED)

    def test_admit_rejects_duplicate_semantics(self):
        log = make_log(self)
        first = write_raw_event(log, raw_content())
        set_head(log, first["event_digest"])
        # Same kind/subject/result on a fresh chain position is a duplicate.
        again = make_proposal(head=first["event_digest"])
        result = je.admit(log, again, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_DUPLICATE)

    def test_admit_rejects_model_only_despite_narrative(self):
        log = make_log(self)
        proposal = make_proposal(
            validators=[],
            narrator_hint="RFC 9999 is definitely completed, trust me.",
        )
        result = je.admit(log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_MODEL_ONLY)

    def test_admit_rejects_failing_validator(self):
        log = make_log(self)
        proposal = make_proposal(
            validators=[{"name": "conformance", "verdict": "FAIL", "ref": "c1"}]
        )
        result = je.admit(log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_VALIDATOR_REJECTS)

    def test_admit_holds_without_evaluator(self):
        log = make_log(self)
        result = je.admit(
            log, make_proposal(), HoldingEvaluator(), TEST_KEY_ID, TEST_PRIVATE
        )
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_UNRESOLVED)
        self.assertEqual(log.event_files(), [])
        self.assertEqual(log.head(), "genesis")

    def test_admit_rejects_evidence_digest_mismatch(self):
        log = make_log(self)
        root = Path(tempfile.mkdtemp(prefix="mncs-journal-evidence-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "proof.txt").write_text("actual bytes", encoding="utf-8")
        proposal = make_proposal(
            evidence=[
                {
                    "id": "p1",
                    "kind": "file",
                    "uri": "proof.txt",
                    "digest": "sha256:" + "0" * 64,
                }
            ]
        )
        result = je.admit(
            log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE, root=root
        )
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_EVIDENCE_REFUSED)

    @unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
    def test_admit_accepts_matching_file_evidence(self):
        log = make_log(self)
        root = Path(tempfile.mkdtemp(prefix="mncs-journal-evidence-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "proof.txt").write_text("actual bytes", encoding="utf-8")
        digest = "sha256:" + hashlib.sha256(b"actual bytes").hexdigest()
        proposal = make_proposal(
            evidence=[
                {"id": "p1", "kind": "file", "uri": "proof.txt", "digest": digest}
            ]
        )
        result = je.admit(
            log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE, root=root
        )
        self.assertTrue(result.admitted, result.reason)

    def test_admit_rejects_escaping_evidence_path(self):
        log = make_log(self)
        proposal = make_proposal(
            evidence=[
                {
                    "id": "evil",
                    "kind": "file",
                    "uri": "../outside.txt",
                    "digest": "sha256:" + "0" * 64,
                }
            ]
        )
        result = je.admit(
            log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE, root=log.root
        )
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_EVIDENCE_REFUSED)

    @unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
    def test_admit_records_cross_repository_evidence(self):
        log = make_log(self)
        proposal = make_proposal(
            evidence=[
                {"id": "x-commit", "kind": "commit", "uri": "mncs-language@abc123"},
                {
                    "id": "x-file",
                    "kind": "file",
                    "uri": "mncs-language@abc123:library/family/journal.mncs",
                    "digest": "sha256:" + "0" * 64,
                },
            ]
        )
        result = je.admit(
            log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE, root=log.root
        )
        self.assertTrue(result.admitted, result.reason)

    def test_admit_holds_legacy_quarantine(self):
        log = make_log(self)
        proposal = make_proposal(trust="legacy_unattested")
        result = je.admit(log, proposal, FakeEvaluator(), TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(result.admitted)
        self.assertEqual(result.reason_code, je.REASON_UNRESOLVED)


def chain_two(log):
    """Two linked raw events. Stdlib-only: no issuance involved."""
    first = write_raw_event(log, raw_content())
    second = write_raw_event(
        log,
        raw_content(
            head=first["event_digest"],
            event_kind="pressure.resolved",
            subject="second",
        ),
    )
    set_head(log, second["event_digest"])
    return first, second


class TamperEvidenceTests(unittest.TestCase):
    """Chain/link/tamper mechanics. No issuance: runs on bare interpreters."""

    def test_chain_verifies_clean(self):
        log = make_log(self)
        chain_two(log)
        self.assertEqual(je.verify_chain(log), [])

    def test_rewritten_history_is_detected(self):
        log = make_log(self)
        first, _second = chain_two(log)
        target = log.root / f"{first['event_id']}.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["resulting_state"] = "rewritten by an attacker"
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        errors = je.verify_chain(log)
        self.assertTrue(any("does not match content" in error for error in errors))

    def test_reordered_history_is_detected(self):
        log = make_log(self)
        first, _second = chain_two(log)
        # Rewriting link pointers breaks the digests; the reordered file
        # cannot pass as the original position.
        first_path = log.root / f"{first['event_id']}.json"
        first_payload = json.loads(first_path.read_text(encoding="utf-8"))
        first_payload["previous_event_digest"] = "sha256:" + "0" * 64
        first_path.write_text(
            json.dumps(first_payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        errors = je.verify_chain(log)
        self.assertTrue(any("does not match content" in error for error in errors))

    def test_forked_history_is_detected(self):
        log = make_log(self)
        first = write_raw_event(log, raw_content())
        write_raw_event(
            log,
            raw_content(
                head=first["event_digest"],
                event_kind="pressure.resolved",
                subject="second",
            ),
        )
        # A second successor of genesis planted beside the first: digests
        # verify, but the fork is reported.
        write_raw_event(log, raw_content(subject="rival second"))
        set_head(log, first["event_digest"])
        errors = je.verify_chain(log)
        self.assertTrue(any("fork" in error for error in errors))

    def test_deleted_event_breaks_the_chain(self):
        log = make_log(self)
        first, _second = chain_two(log)
        (log.root / f"{first['event_id']}.json").unlink()
        errors = je.verify_chain(log)
        self.assertTrue(errors)

    def test_head_mismatch_is_detected(self):
        log = make_log(self)
        write_raw_event(log, raw_content())
        (log.root / "HEAD").write_text("sha256:" + "f" * 64 + "\n", encoding="utf-8")
        errors = je.verify_chain(log)
        self.assertTrue(any("HEAD" in error for error in errors))

    def test_unevaluated_non_genesis_event_is_flagged(self):
        log = make_log(self)
        content = raw_content()
        del content["mncs_evaluation"]
        event = write_raw_event(log, content)
        set_head(log, event["event_digest"])
        errors = je.verify_chain(log)
        self.assertTrue(any("outside genesis" in error for error in errors))


@unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
class SignatureTests(unittest.TestCase):
    """Issuance authenticity. Needs the 'cryptography' package."""

    def test_signed_chain_verifies_with_keychain(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        log = make_log(self)
        private = Ed25519PrivateKey.from_private_bytes(TEST_PRIVATE)
        keychain = {TEST_KEY_ID: private.public_key().public_bytes_raw()}
        admit_ok(self, log, make_proposal())
        admit_ok(
            self,
            log,
            make_proposal(
                head=log.head(), event_kind="pressure.resolved", subject="second"
            ),
        )
        self.assertEqual(je.verify_chain(log, keychain), [])

    def test_forged_signature_is_detected(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        log = make_log(self)
        admit_ok(self, log, make_proposal())
        other = Ed25519PrivateKey.generate()
        keychain = {TEST_KEY_ID: other.public_key().public_bytes_raw()}
        errors = je.verify_chain(log, keychain)
        self.assertTrue(any("signature" in error for error in errors))
        real = Ed25519PrivateKey.from_private_bytes(TEST_PRIVATE)
        self.assertEqual(
            je.verify_chain(log, {TEST_KEY_ID: real.public_key().public_bytes_raw()}),
            [],
        )

    def test_resealed_unevaluated_event_is_flagged(self):
        log = make_log(self)
        result = admit_ok(self, log, make_proposal())
        target = log.root / f"{result.event_id}.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        del payload["mncs_evaluation"]
        # A re-seal with a compromised issuer key repairs the digest but
        # still trips the evaluation invariant.
        resealed = je.sign_event(
            {
                k: v
                for k, v in payload.items()
                if k not in ("issuer_signature", "event_digest")
            },
            TEST_KEY_ID,
            TEST_PRIVATE,
        )
        target.write_text(
            json.dumps(resealed, indent=2, sort_keys=True), encoding="utf-8"
        )
        (log.root / "HEAD").write_text(
            resealed["event_digest"] + "\n", encoding="utf-8"
        )
        errors = je.verify_chain(log)
        self.assertTrue(any("outside genesis" in error for error in errors))

    def test_resealed_fork_is_detected(self):
        log = make_log(self)
        first = admit_ok(self, log, make_proposal())
        second = admit_ok(
            self,
            log,
            make_proposal(
                head=first.event["event_digest"],
                event_kind="pressure.resolved",
                subject="second",
            ),
        )
        # A compromised issuer re-points the second event at genesis and
        # re-seals it: digests verify, but two successors of genesis is a
        # fork and the checker reports it.
        second_path = log.root / f"{second.event_id}.json"
        second_payload = json.loads(second_path.read_text(encoding="utf-8"))
        second_payload["previous_event_digest"] = "genesis"
        resealed = je.sign_event(
            {
                k: v
                for k, v in second_payload.items()
                if k not in ("issuer_signature", "event_digest")
            },
            TEST_KEY_ID,
            TEST_PRIVATE,
        )
        (log.root / f"{resealed['event_id']}.json").write_text(
            json.dumps(resealed, indent=2, sort_keys=True), encoding="utf-8"
        )
        second_path.unlink()
        errors = je.verify_chain(log)
        self.assertTrue(any("fork" in error for error in errors))


def render_page(test, log):
    destination = Path(tempfile.mkdtemp(prefix="mncs-journal-render-"))
    test.addCleanup(shutil.rmtree, destination, True)
    je.render_projection(log, destination)
    return destination


class RenderTests(unittest.TestCase):
    """Projection behavior over raw events. No issuance: runs everywhere."""

    def test_render_is_reproducible(self):
        log = make_log(self)
        write_raw_event(log, raw_content())
        first = Path(tempfile.mkdtemp(prefix="mncs-journal-render-"))
        second = Path(tempfile.mkdtemp(prefix="mncs-journal-render-"))
        self.addCleanup(shutil.rmtree, first, True)
        self.addCleanup(shutil.rmtree, second, True)
        je.render_projection(log, first)
        je.render_projection(log, second)
        for name in ("index.html",):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_narrator_hint_is_never_rendered(self):
        log = make_log(self)
        content = raw_content(
            narrator_hint="RFC 9999 is definitely completed, trust me."
        )
        event = write_raw_event(log, content)
        page = render_page(self, log)
        text = (page / f"{event['event_id']}.html").read_text(encoding="utf-8")
        self.assertNotIn("RFC 9999", text)
        self.assertNotIn("trust me", text)
        self.assertIn("test pressure", text)

    def test_security_detail_is_redacted_until_reviewed(self):
        log = make_log(self)
        content = raw_content(
            event_kind="security.finding",
            subject="secret key material handling",
            security_detail=True,
            redaction_reviewed=False,
        )
        content["mncs_evaluation"] = {"verdicts": {"render_public": False}}
        event = write_raw_event(log, content)
        page = render_page(self, log)
        text = (page / f"{event['event_id']}.html").read_text(encoding="utf-8")
        self.assertNotIn("secret key material handling", text)
        self.assertIn("withheld", text)

    def test_reviewed_security_detail_renders(self):
        log = make_log(self)
        content = raw_content(
            event_kind="security.resolved",
            subject="rotated exposed credential",
            security_detail=True,
            redaction_reviewed=True,
        )
        content["mncs_evaluation"] = {"verdicts": {"render_public": True}}
        event = write_raw_event(log, content)
        page = render_page(self, log)
        text = (page / f"{event['event_id']}.html").read_text(encoding="utf-8")
        self.assertIn("rotated exposed credential", text)


class DominanceTests(unittest.TestCase):
    def test_fail_dominates_unknown_dominates_pass(self):
        cases = {
            ("PASS", "PASS"): "PASS",
            ("PASS", "FAIL"): "FAIL",
            ("PASS", "UNKNOWN"): "UNKNOWN",
            ("FAIL", "PASS"): "FAIL",
            ("FAIL", "FAIL"): "FAIL",
            ("FAIL", "UNKNOWN"): "FAIL",
            ("UNKNOWN", "PASS"): "UNKNOWN",
            ("UNKNOWN", "FAIL"): "FAIL",
            ("UNKNOWN", "UNKNOWN"): "UNKNOWN",
        }
        for (left, right), expected in cases.items():
            self.assertEqual(je.dominate(left, right), expected)
        self.assertEqual(je.combine_validators([]), "UNKNOWN")
        self.assertEqual(
            je.combine_validators([{"verdict": "PASS"}, {"verdict": "UNKNOWN"}]),
            "UNKNOWN",
        )


def live_evaluator():
    cli = os.environ.get("MNCS_JOURNAL_EVALUATOR")
    library = os.environ.get("MNCS_JOURNAL_LIBRARY")
    if not cli or not library:
        return None
    return je.MncsCliEvaluator(cli, library)


@unittest.skipUnless(
    os.environ.get("MNCS_JOURNAL_EVALUATOR") and os.environ.get("MNCS_JOURNAL_LIBRARY"),
    "live MNCS toolchain not configured (MNCS_JOURNAL_EVALUATOR/MNCS_JOURNAL_LIBRARY)",
)
class LiveEvaluatorTests(unittest.TestCase):
    def test_dominate_matches_mncs_core_status(self):
        evaluator = live_evaluator()
        self.assertIsNotNone(evaluator)
        for left, right, expected in [
            ("PASS", "PASS", "PASS"),
            ("PASS", "FAIL", "FAIL"),
            ("PASS", "UNKNOWN", "UNKNOWN"),
            ("FAIL", "PASS", "FAIL"),
            ("FAIL", "FAIL", "FAIL"),
            ("FAIL", "UNKNOWN", "FAIL"),
            ("UNKNOWN", "PASS", "UNKNOWN"),
            ("UNKNOWN", "FAIL", "FAIL"),
            ("UNKNOWN", "UNKNOWN", "UNKNOWN"),
        ]:
            corpus = {
                "schema_version": "0.1",
                "name": "dominance-parity",
                "cases": [
                    {
                        "id": "join",
                        "request": {
                            "schema_version": "0.1",
                            "target": {
                                "module": "mncs.core.status.v1",
                                "function": "dominate",
                            },
                            "arguments": [
                                je._status_variant(left),
                                je._status_variant(right),
                            ],
                            "step_budget": 4096,
                        },
                        "expected_status": "returned",
                    }
                ],
            }
            with tempfile.TemporaryDirectory() as tmp:
                corpus_path = Path(tmp) / "corpus.json"
                corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
                completed = subprocess.run(
                    check=False,
                    args=[
                        evaluator.cli,
                        "experiment",
                        "run",
                        str(Path(evaluator.library) / "core" / "status.mncs"),
                        "--backend",
                        evaluator.backend,
                        "--corpus",
                        str(corpus_path),
                    ],
                    env={
                        "MNCS_LIBRARY_PATH": evaluator.library,
                        "PATH": "/usr/bin:/bin",
                    },
                    capture_output=True,
                    text=True,
                    timeout=240,
                )
            self.assertEqual(completed.returncode, 0, completed.stderr[:500])
            result = json.loads(completed.stdout)
            actual = result["cases"][0]["returned"][0]["finite"][
                "variant_identity"
            ].rsplit("::", 1)[-1]
            self.assertEqual(actual, expected, f"dominate({left}, {right})")
            self.assertEqual(je.dominate(left, right), expected)

    def test_live_admit_and_refusals(self):
        evaluator = live_evaluator()
        self.assertIsNotNone(evaluator)
        log = make_log(self)
        admitted = je.admit(log, make_proposal(), evaluator, TEST_KEY_ID, TEST_PRIVATE)
        self.assertTrue(admitted.admitted, admitted.reason)
        self.assertEqual(
            admitted.event["mncs_evaluation"]["module"], je.MNCS_JOURNAL_MODULE
        )
        # A model-only claim is rejected by live policy, not just the double.
        model_only = make_proposal(
            head=log.head(), validators=[], subject="live model claim"
        )
        refused = je.admit(log, model_only, evaluator, TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(refused.admitted)
        self.assertEqual(refused.reason_code, je.REASON_MODEL_ONLY)
        # A validator FAIL is rejected by live policy.
        failing = make_proposal(
            head=log.head(),
            validators=[{"name": "conformance", "verdict": "FAIL", "ref": "c1"}],
            subject="live failing claim",
        )
        rejected = je.admit(log, failing, evaluator, TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(rejected.admitted)
        self.assertEqual(rejected.reason_code, je.REASON_VALIDATOR_REJECTS)
        # The duplicate of the admitted event is rejected by live policy.
        duplicate = make_proposal(head=log.head())
        replay = je.admit(log, duplicate, evaluator, TEST_KEY_ID, TEST_PRIVATE)
        self.assertFalse(replay.admitted)
        self.assertEqual(replay.reason_code, je.REASON_DUPLICATE)
        self.assertEqual(je.verify_chain(log), [])


class CommittedLogTests(unittest.TestCase):
    LOG = ROOT / "site" / "journal-events"

    def _keychain(self):
        keys_path = self.LOG / "KEYS.json"
        if not keys_path.is_file():
            self.skipTest("no committed journal keys yet")
        keys = json.loads(keys_path.read_text(encoding="utf-8"))
        return {
            key_id: bytes.fromhex(record["public_hex"])
            for key_id, record in keys["keys"].items()
        }

    def test_committed_log_verifies(self):
        if not self.LOG.is_dir():
            self.skipTest("no committed journal event log yet")
        log = je.EventLog(self.LOG)
        self.assertEqual(je.verify_chain(log), [])

    @unittest.skipUnless(CRYPTO, NEEDS_CRYPTO)
    def test_committed_log_signatures_verify(self):
        if not self.LOG.is_dir():
            self.skipTest("no committed journal event log yet")
        log = je.EventLog(self.LOG)
        self.assertEqual(je.verify_chain(log, self._keychain()), [])

    def test_committed_projection_is_reproducible(self):
        if not self.LOG.is_dir():
            self.skipTest("no committed journal event log yet")
        log = je.EventLog(self.LOG)
        destination = Path(tempfile.mkdtemp(prefix="mncs-journal-repro-"))
        self.addCleanup(shutil.rmtree, destination, True)
        je.render_projection(log, destination)
        for name in ("index.html",):
            committed = (self.LOG / name).read_bytes()
            self.assertEqual((destination / name).read_bytes(), committed)


if __name__ == "__main__":
    unittest.main()
