"""Canonical MNCS Journal event log.

The public Development Journal prose is an editorial surface; this module
owns the canonical semantic history underneath it:

```text
claim / proposal  (any agent or human; untrusted, never history)
  !=
attestation  (a validator's signed statement about evidence)
  !=
canonical Journal event  (admitted only through the policy path below)
  !=
human-readable rendering  (deterministic projection of canonical events)
```

- ``propose`` / ``query`` are the ordinary public surface.
- ``admit`` is the restricted canonical path. It verifies mechanical facts
  (schema, digests, chain continuity, signatures, duplicates) and requires
  live policy verdicts from ``mncs.family.journal.v1`` executed through the
  MNCS toolchain. Without those verdicts it holds (UNKNOWN), never admits.
- ``verify_chain`` recomputes every digest, signature, and link so silent
  rewriting of history is detectable.
- ``render_projection`` regenerates the human-readable view deterministically
  from canonical events. Model prose is never rendered as history.

Cryptography follows the Atlas issuance convention (``admission/issuance.py``,
family attestation envelope): Ed25519 over canonical bytes, ``cryptography``
imported lazily so mechanical verification stays stdlib-only.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENT_SCHEMA = "mncs.journal.event.v1"
EVENT_DIGEST_ALG = "sha256"
GENESIS_PREVIOUS = "genesis"

EVENT_KINDS = (
    "capability.added",
    "capability.proven",
    "capability.regressed",
    "rfc.advanced",
    "rfc.completed",
    "backend.conformant",
    "backend.regressed",
    "stdlib.expanded",
    "pressure.discovered",
    "pressure.resolved",
    "security.finding",
    "security.resolved",
    "commons.promoted",
    "project.migrated",
    "release.created",
    "architecture.changed",
)

TRUST_LEVELS = (
    "observed",
    "locally_proven",
    "independently_confirmed",
    "commons_promoted",
    "legacy_unattested",
)

VERDICTS = ("PASS", "FAIL", "UNKNOWN")

EVENT_ID_RE = re.compile(r"^je-[0-9a-f]{12}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

MNCS_JOURNAL_MODULE = "mncs.family.journal.v1"

# Admission reason codes mirror mncs.family.journal.v1 AdmissionVerdict.
REASON_VALIDATOR_REJECTS = 1
REASON_EVIDENCE_REFUSED = 2
REASON_DUPLICATE = 3
REASON_MODEL_ONLY = 4
REASON_UNRESOLVED = 5


class EventLogError(ValueError):
    """Mechanical rejection of a proposal, event, or chain state."""


class EvaluatorUnavailable(RuntimeError):
    """The MNCS policy evaluator cannot run; the caller must hold, not admit."""


def canonical_event_bytes(event: Mapping[str, Any]) -> bytes:
    """Deterministic bytes for hashing and signing (router convention)."""
    body = {key: value for key, value in event.items() if key != "event_digest"}
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _content_for_id(proposal: Mapping[str, Any]) -> dict[str, Any]:
    # event_id identifies the claim (kind, subject, states, evidence,
    # validators, ...), never the admission outcome. Outcome fields (trust
    # standing, evaluation, issuer, signature, digest) and proposal
    # bookkeeping are covered by the signature and chain instead, so a
    # proposal keeps its id from candidacy through admission. A trust
    # promotion therefore always cites new confirmation evidence, which
    # gives it a new claim id; re-admitting identical content is a
    # duplicate by construction.
    return {
        key: value
        for key, value in proposal.items()
        if key
        not in (
            "event_id",
            "issuer",
            "issuer_signature",
            "event_digest",
            "mncs_evaluation",
            "proposal_author",
            "proposal_at",
            "trust",
        )
    }


def compute_event_id(proposal: Mapping[str, Any]) -> str:
    body = _content_for_id(proposal)
    raw = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "je-" + hashlib.sha256(raw).hexdigest()[:12]


def compute_event_digest(event: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_event_bytes(event)).hexdigest()


def crypto_available() -> bool:
    """Whether Ed25519 issuance can run here. Chain/digest checks are stdlib."""
    try:
        import importlib.util

        return importlib.util.find_spec("cryptography") is not None
    except (ImportError, ValueError):
        return False


def _ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Journal admission needs the 'cryptography' package to sign; "
            "unsigned claims stay proposals"
        ) from exc
    return Ed25519PrivateKey, Ed25519PublicKey


def sign_event(
    content: Mapping[str, Any], key_id: str, private_bytes: bytes
) -> dict[str, Any]:
    """Attach issuer authenticity to admitted content (issuance convention)."""
    private_cls, _ = _ed25519()
    if len(private_bytes) != 32:
        raise ValueError("ed25519 private key must be 32 bytes")
    event = dict(content)
    event.pop("issuer_signature", None)
    event.pop("event_digest", None)
    # Identity follows claim content: admission outcome fields stay excluded
    # by _content_for_id, so this is a no-op on the admit path and a new
    # id for any re-sealed mutation (which is then a fork, not an edit).
    event["event_id"] = compute_event_id(event)
    event["issuer"] = {"key_id": key_id, "algorithm": "ed25519"}
    signed = canonical_event_bytes(event)
    private = private_cls.from_private_bytes(private_bytes)
    event["issuer_signature"] = private.sign(signed).hex()
    event["event_digest"] = compute_event_digest(event)
    return event


def verify_signature(event: Mapping[str, Any], public_bytes: bytes) -> bool:
    """Verify one event signature against an explicit trust-root key."""
    _, public_cls = _ed25519()
    try:
        signature = bytes.fromhex(str(event.get("issuer_signature") or ""))
        claimed = dict(event)
        claimed.pop("issuer_signature", None)
        claimed.pop("event_digest", None)
        payload = json.dumps(
            claimed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        public_cls.from_public_bytes(public_bytes).verify(signature, payload)
        return True
    except Exception:  # noqa: BLE001 - every verification failure mode means False
        return False


def utc_timestamp(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    return (
        moment.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def validate_schema_shape(event: Mapping[str, Any]) -> list[str]:
    """Mechanical shape checks mirroring schema/journal-event.schema.json."""
    errors: list[str] = []
    if event.get("schema") != EVENT_SCHEMA:
        errors.append("unsupported event schema")
    if not isinstance(event.get("event_id"), str) or not EVENT_ID_RE.match(
        event["event_id"]
    ):
        errors.append("malformed event_id")
    if event.get("event_kind") not in EVENT_KINDS:
        errors.append(
            f"event_kind outside the bounded vocabulary: {event.get('event_kind')!r}"
        )
    for name in ("project", "subject", "previous_state", "resulting_state"):
        if not isinstance(event.get(name), str) or not event[name].strip():
            errors.append(f"{name} must be a non-empty string")
    if not isinstance(event.get("timestamp"), str) or not TIMESTAMP_RE.match(
        event["timestamp"]
    ):
        errors.append("timestamp must be UTC RFC-3339 without microseconds")
    evidence = event.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
    else:
        seen: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict):
                errors.append("evidence item must be an object")
                continue
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id or item_id in seen:
                errors.append("evidence ids must be non-empty and unique")
            seen.add(str(item_id))
            if not isinstance(item.get("uri"), str) or not item["uri"]:
                errors.append(f"evidence {item_id!r} needs a uri")
            digest = item.get("digest")
            if digest is not None and (
                not isinstance(digest, str) or not DIGEST_RE.match(digest)
            ):
                errors.append(f"evidence {item_id!r} has a malformed digest")
    for validator in event.get("validators", []):
        if not isinstance(validator, dict) or validator.get("verdict") not in VERDICTS:
            errors.append("validator verdicts must be PASS, FAIL, or UNKNOWN")
    security = event.get("security")
    if not isinstance(security, dict) or not isinstance(
        security.get("contains_detail"), bool
    ):
        errors.append("security.contains_detail must be a boolean")
    if event.get("trust") not in TRUST_LEVELS:
        errors.append(f"trust outside the vocabulary: {event.get('trust')!r}")
    previous = event.get("previous_event_digest")
    if not isinstance(previous, str) or (
        previous != GENESIS_PREVIOUS and not DIGEST_RE.match(previous)
    ):
        errors.append("previous_event_digest must be genesis or a sha256 digest")
    return errors


@dataclass
class EventLog:
    """Canonical event store rooted at one directory (proposals + events)."""

    root: Path

    @property
    def proposals_dir(self) -> Path:
        return self.root / "proposals"

    def head(self) -> str:
        head_file = self.root / "HEAD"
        if not head_file.is_file():
            return GENESIS_PREVIOUS
        return head_file.read_text(encoding="utf-8").strip()

    def event_files(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted(self.root.glob("je-*.json"))

    def load_event(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def events(self) -> list[dict[str, Any]]:
        return [self.load_event(path) for path in self.event_files()]

    def semantic_keys(self) -> set[tuple[str, str, str]]:
        keys = set()
        for event in self.events():
            keys.add(
                (
                    event.get("event_kind", ""),
                    event.get("subject", ""),
                    event.get("resulting_state", ""),
                )
            )
        return keys


def build_proposal(
    *,
    project: str,
    event_kind: str,
    subject: str,
    previous_state: str,
    resulting_state: str,
    evidence: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
    validators: Sequence[Mapping[str, Any]] = (),
    commons_confirmations: Sequence[Mapping[str, Any]] = (),
    affected_rfcs: Sequence[str] = (),
    affected_repositories: Sequence[str] = (),
    pressure_origin: str | None = None,
    security_detail: bool = False,
    redaction_reviewed: bool = False,
    trust: str = "observed",
    previous_event_digest: str = GENESIS_PREVIOUS,
    timestamp: str | None = None,
    narrator_hint: str | None = None,
    classifier_hint: str | None = None,
) -> dict[str, Any]:
    """Build an unsigned candidate. Public: any agent or human may propose."""
    proposal: dict[str, Any] = {
        "schema": EVENT_SCHEMA,
        "event_id": "je-pending",
        "project": project,
        "event_kind": event_kind,
        "subject": subject,
        "previous_state": previous_state,
        "resulting_state": resulting_state,
        "timestamp": timestamp or utc_timestamp(),
        "evidence": [dict(item) for item in evidence],
        "provenance": dict(provenance),
        "validators": [dict(item) for item in validators],
        "commons_confirmations": [dict(item) for item in commons_confirmations],
        "affected_rfcs": list(affected_rfcs),
        "affected_repositories": list(affected_repositories),
        "pressure_origin": pressure_origin,
        "security": {
            "contains_detail": bool(security_detail),
            "redaction_reviewed": bool(redaction_reviewed),
        },
        "trust": trust,
        "previous_event_digest": previous_event_digest,
        "mncs_evaluation": None,
    }
    interpretation: dict[str, str] = {}
    if narrator_hint:
        interpretation["narrator_hint"] = narrator_hint
    if classifier_hint:
        interpretation["classifier_hint"] = classifier_hint
    if interpretation:
        proposal["interpretation"] = interpretation
    proposal["event_id"] = compute_event_id(proposal)
    return proposal


@dataclass
class ProposalReceipt:
    event_id: str
    path: str


def propose(log: EventLog, proposal: Mapping[str, Any], author: str) -> ProposalReceipt:
    """Record an untrusted candidate. Anyone may propose; nothing is admitted."""
    errors = validate_schema_shape({**proposal, "event_id": proposal.get("event_id")})
    if errors:
        raise EventLogError("; ".join(errors))
    if not author or not author.strip():
        raise EventLogError("proposal needs a named author")
    event_id = compute_event_id(proposal)
    if event_id != proposal.get("event_id"):
        raise EventLogError("proposal event_id does not match its content")
    log.proposals_dir.mkdir(parents=True, exist_ok=True)
    path = log.proposals_dir / f"{event_id}.json"
    record = dict(proposal)
    record["proposal_author"] = author
    record["proposal_at"] = utc_timestamp()
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return ProposalReceipt(event_id=event_id, path=str(path))


@dataclass
class QueryResult:
    event_id: str
    event_kind: str
    subject: str
    trust: str
    event_digest: str
    admitted: bool


def query(log: EventLog) -> list[QueryResult]:
    """Observe canonical history and outstanding proposals. Public."""
    results = [
        QueryResult(
            event_id=event.get("event_id", "?"),
            event_kind=event.get("event_kind", "?"),
            subject=event.get("subject", "?"),
            trust=event.get("trust", "?"),
            event_digest=event.get("event_digest", ""),
            admitted=True,
        )
        for event in log.events()
    ]
    if log.proposals_dir.is_dir():
        for path in sorted(log.proposals_dir.glob("*.json")):
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            results.append(
                QueryResult(
                    event_id=candidate.get("event_id", path.stem),
                    event_kind=candidate.get("event_kind", "?"),
                    subject=candidate.get("subject", "?"),
                    trust="proposal",
                    event_digest="",
                    admitted=False,
                )
            )
    return results


def dominate(left: str, right: str) -> str:
    """FAIL > UNKNOWN > PASS evidence join (mncs.core.status.v1 parity).

    Mechanical lattice join only; journal admission policy itself always
    comes from live ``mncs.family.journal.v1`` evaluation. Parity against
    the MNCS ``dominate`` function is pinned by the live-evaluator tests.
    """
    if left not in VERDICTS or right not in VERDICTS:
        raise EventLogError("cannot join non-status verdicts")
    if left == "PASS":
        return right
    if left == "FAIL":
        return "FAIL"
    return "UNKNOWN" if right == "PASS" else right


def combine_validators(validators: Sequence[Mapping[str, Any]]) -> str:
    """Fold validator verdicts. No validators means no attestation (UNKNOWN)."""
    verdicts = [item.get("verdict") for item in validators]
    if not verdicts:
        return "UNKNOWN"
    combined = "PASS"
    for verdict in verdicts:
        combined = dominate(combined, str(verdict))
    return combined


I64 = {"bits": 64, "signed": True}
I32 = {"bits": 32, "signed": True}
STATUS_MODULE = "mncs.core.status.v1"

_TRUST_LEVELS_MNCS = (
    "Observed",
    "LocallyProven",
    "IndependentlyConfirmed",
    "CommonsPromoted",
    "LegacyUnattested",
)
_TRUST_EVENTS_MNCS = ("LocalProof", "IndependentConfirmation", "CommonsPromotion")


def _finite(
    module: str, type_name: str, variant: str, discriminant: int, payload: Any = None
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "type_identity": f"mncs:0.2:finite-type:{module}::{type_name}",
        "variant_identity": f"mncs:0.2:finite-variant:{module}::{type_name}::{variant}",
        "discriminant": discriminant,
    }
    if payload is not None:
        value["payload"] = payload
    return {"finite": value}


def _status_variant(name: str) -> dict[str, Any]:
    return _finite(
        STATUS_MODULE, "Status", name, {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[name]
    )


def _record(
    module: str, name: str, fields: Sequence[tuple[str, str]], values: Mapping[str, Any]
) -> dict[str, Any]:
    inner = "".join(f"{field}%3A{kind}%3B" for field, kind in fields)
    return {
        "record": {
            "type_identity": f"mncs:0.2:record-type:{module}::{name}::{inner}",
            "name": name,
            "fields": [[field, values[field]] for field, _ in fields],
        }
    }


def _boolean(value: bool) -> dict[str, Any]:
    return {"boolean": {"value": bool(value)}}


def _integer(value: int, width: Mapping[str, Any]) -> dict[str, Any]:
    return {"integer": {"value": value, "type": dict(width)}}


def evidence_tally_arg(
    evidence: Sequence[Mapping[str, Any]], digests_ok: bool
) -> dict[str, Any]:
    """Mechanical tally facts; the PASS/FAIL/UNKNOWN verdict is MNCS policy."""
    return _record(
        MNCS_JOURNAL_MODULE,
        "EvidenceTally",
        [
            ("evidence_ok", "bool"),
            ("missing_refs", "i64"),
            ("required", "i64"),
            ("satisfied", "i64"),
            ("stale_refs", "i64"),
        ],
        {
            "evidence_ok": _boolean(digests_ok),
            "missing_refs": _integer(0, I64),
            "required": _integer(len(evidence), I64),
            "satisfied": _integer(len(evidence) if digests_ok else 0, I64),
            "stale_refs": _integer(0, I64),
        },
    )


def admission_case_arg(
    gate: str, validator: str, duplicate: bool, model_only: bool
) -> dict[str, Any]:
    return _record(
        MNCS_JOURNAL_MODULE,
        "AdmissionCase",
        [
            ("duplicate_known", "bool"),
            ("gate", "Status"),
            ("model_only", "bool"),
            ("validator", "Status"),
        ],
        {
            "duplicate_known": _boolean(duplicate),
            "gate": _status_variant(gate),
            "model_only": _boolean(model_only),
            "validator": _status_variant(validator),
        },
    )


def _trust_arg(level: str) -> dict[str, Any]:
    names = {
        "observed": "Observed",
        "locally_proven": "LocallyProven",
        "independently_confirmed": "IndependentlyConfirmed",
        "commons_promoted": "CommonsPromoted",
        "legacy_unattested": "LegacyUnattested",
    }
    variant = names[level]
    return _finite(
        MNCS_JOURNAL_MODULE, "TrustLevel", variant, _TRUST_LEVELS_MNCS.index(variant)
    )


@dataclass
class MncsVerdicts:
    gate: str
    admission: str
    admission_reason: int
    trust_accepted: bool
    trust_following: str
    trust_reason: int
    render_public: bool
    backend: str
    result_digest: str


class PolicyEvaluator:
    """Policy source for admission. Only a live MNCS evaluation admits."""

    @property
    def identity(self) -> dict[str, Any]:
        raise NotImplementedError

    def evaluate(
        self,
        *,
        tally: Mapping[str, Any],
        validator: str,
        duplicate: bool,
        model_only: bool,
        trust_from: str,
        trust_event: str,
        render_guard: Mapping[str, Any],
    ) -> MncsVerdicts:
        raise NotImplementedError


class MncsCliEvaluator(PolicyEvaluator):
    """Evaluate journal policy by executing mncs.family.journal.v1.

    One temporary single-function corpus per question, run through the MNCS
    toolchain. Any toolchain failure raises EvaluatorUnavailable so the
    caller holds instead of admitting.
    """

    def __init__(
        self,
        cli: str | Path,
        library: str | Path,
        backend: str = "mncs-research-bytecode",
        timeout_seconds: int = 240,
    ) -> None:
        self.cli = str(cli)
        self.library = str(library)
        self.backend = backend
        self.timeout_seconds = timeout_seconds

    @property
    def identity(self) -> dict[str, Any]:
        return {
            "module": MNCS_JOURNAL_MODULE,
            "evaluator": f"mncs-cli:{Path(self.cli).name}",
            "backend": self.backend,
        }

    def _run_function(
        self, function: str, arguments: Sequence[Mapping[str, Any]]
    ) -> Any:
        corpus = {
            "schema_version": "0.1",
            "name": "journal-admit",
            "cases": [
                {
                    "id": "admit",
                    "request": {
                        "schema_version": "0.1",
                        "target": {"module": MNCS_JOURNAL_MODULE, "function": function},
                        "arguments": list(arguments),
                        "step_budget": 4096,
                    },
                    "expected_status": "returned",
                }
            ],
        }
        with tempfile.TemporaryDirectory(prefix="mncs-journal-admit-") as tmp:
            corpus_path = Path(tmp) / "corpus.json"
            corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
            try:
                completed = subprocess.run(
                    check=False,
                    args=[
                        self.cli,
                        "experiment",
                        "run",
                        str(Path(self.library) / "family" / "journal.mncs"),
                        "--backend",
                        self.backend,
                        "--corpus",
                        str(corpus_path),
                    ],
                    env={
                        "MNCS_LIBRARY_PATH": str(self.library),
                        "PATH": "/usr/bin:/bin",
                    },
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise EvaluatorUnavailable(
                    f"MNCS evaluator did not run: {exc}"
                ) from exc
        if completed.returncode != 0:
            raise EvaluatorUnavailable(
                f"MNCS evaluator failed: {completed.stderr.strip()[:500]}"
            )
        try:
            result = json.loads(completed.stdout)
            case = result["cases"][0]
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            raise EvaluatorUnavailable("MNCS evaluator returned no case") from exc
        if case.get("status") != "returned":
            raise EvaluatorUnavailable(
                f"MNCS evaluator did not return: {case.get('failure_reason')}"
            )
        return case["returned"][0]

    @staticmethod
    def _finite_name(value: Mapping[str, Any]) -> str:
        return str(value["finite"]["variant_identity"]).rsplit("::", 1)[-1]

    def evaluate(
        self,
        *,
        tally: Mapping[str, Any],
        validator: str,
        duplicate: bool,
        model_only: bool,
        trust_from: str,
        trust_event: str,
        render_guard: Mapping[str, Any],
    ) -> MncsVerdicts:
        gate_value = self._run_function("gate_admit", [tally])
        gate = self._finite_name(gate_value)
        case = admission_case_arg(gate, validator, duplicate, model_only)
        admission_value = self._run_function("admission_decision", [case])
        admission_name = self._finite_name(admission_value)
        payload = admission_value["finite"].get("payload") or []
        reason = 0
        for key, integer in payload:
            if key == "reason":
                reason = int(integer["integer"]["value"])
        trust_value = self._run_function(
            "trust_transition",
            [
                _trust_arg(trust_from),
                _finite(
                    MNCS_JOURNAL_MODULE,
                    "TrustEvent",
                    trust_event,
                    _TRUST_EVENTS_MNCS.index(trust_event),
                ),
                _status_variant(gate),
            ],
        )
        fields = {name: val for name, val in trust_value["record"]["fields"]}
        following = self._finite_name(fields["following"])
        following_snake = {
            "Observed": "observed",
            "LocallyProven": "locally_proven",
            "IndependentlyConfirmed": "independently_confirmed",
            "CommonsPromoted": "commons_promoted",
            "LegacyUnattested": "legacy_unattested",
        }[following]
        render_value = self._run_function(
            "may_render_public", [render_guard, _status_variant(gate)]
        )
        digest = hashlib.sha256(
            json.dumps(
                {"gate": gate, "admission": admission_name, "trust": following_snake},
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return MncsVerdicts(
            gate=gate,
            admission=admission_name,
            admission_reason=reason,
            trust_accepted=bool(fields["accepted"]["boolean"]["value"]),
            trust_following=following_snake,
            trust_reason=int(fields["reason"]["integer"]["value"]),
            render_public=bool(render_value["boolean"]["value"]),
            backend=self.backend,
            result_digest="sha256:" + digest,
        )


@dataclass
class AdmitResult:
    admitted: bool
    event_id: str
    reason: str
    reason_code: int
    event: dict[str, Any] = field(default_factory=dict)


def _resolve_evidence(
    evidence: Sequence[Mapping[str, Any]], root: Path
) -> tuple[bool, list[str]]:
    """Mechanical evidence check: every digest-bearing local file must match.

    Returns (digests_ok, problems). A ``file`` item whose URI is a plain
    contained relative path is resolved against ``root`` and verified.
    Anything else (commits, PRs, records, cross-repository ``repo@rev:path``
    locators, absolute paths) is recorded, not re-fetched here; validator
    attestations carry those claims into the MNCS gate through the
    validator verdicts.
    """
    problems: list[str] = []
    ok = True
    for item in evidence:
        digest = item.get("digest")
        uri = str(item.get("uri") or "")
        if item.get("kind") != "file" or not digest:
            continue
        if "@" in uri or "://" in uri:
            # Cross-repository locator: recorded, carried by attestations.
            continue
        if uri.startswith("/") or ".." in Path(uri).parts:
            problems.append(
                f"evidence {item.get('id')}: file uri must be contained or cross-repository"
            )
            ok = False
            continue
        candidate = (root / uri).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            problems.append(f"evidence {item.get('id')}: path escapes the root")
            ok = False
            continue
        if not candidate.is_file():
            problems.append(f"evidence {item.get('id')}: missing file {uri}")
            ok = False
            continue
        actual = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != digest:
            problems.append(f"evidence {item.get('id')}: digest mismatch for {uri}")
            ok = False
    return ok, problems


def admit(
    log: EventLog,
    proposal: Mapping[str, Any],
    evaluator: PolicyEvaluator,
    key_id: str,
    private_bytes: bytes,
    *,
    trust_event: str = "LocalProof",
    root: Path | None = None,
) -> AdmitResult:
    """Restricted canonical path: verify mechanics, evaluate policy, sign.

    Anyone may call ``propose``; ``admit`` additionally requires the
    issuer key and a live MNCS policy evaluation. Every refusal explains
    itself with the journal reason code. A missing evaluator never admits.
    """
    base = dict(proposal)
    base.pop("proposal_author", None)
    base.pop("proposal_at", None)
    base.pop("issuer", None)
    base.pop("issuer_signature", None)
    base.pop("event_digest", None)
    base.pop("mncs_evaluation", None)

    errors = validate_schema_shape({**base, "event_id": base.get("event_id")})
    if errors:
        return AdmitResult(
            False,
            str(base.get("event_id") or "?"),
            "; ".join(errors),
            REASON_EVIDENCE_REFUSED,
        )
    if compute_event_id(base) != base.get("event_id"):
        return AdmitResult(
            False,
            str(base.get("event_id") or "?"),
            "event_id does not match content",
            REASON_EVIDENCE_REFUSED,
        )
    if trust_event not in ("LocalProof", "IndependentConfirmation", "CommonsPromotion"):
        return AdmitResult(
            False,
            str(base.get("event_id")),
            "unknown trust event",
            REASON_EVIDENCE_REFUSED,
        )

    head = log.head()
    if base.get("previous_event_digest") != head:
        return AdmitResult(
            False,
            str(base.get("event_id")),
            f"previous digest does not continue HEAD ({head})",
            REASON_EVIDENCE_REFUSED,
        )

    semantic = (
        str(base.get("event_kind")),
        str(base.get("subject")),
        str(base.get("resulting_state")),
    )
    if semantic in log.semantic_keys():
        return AdmitResult(
            False,
            str(base.get("event_id")),
            "semantic duplicate of a canonical event",
            REASON_DUPLICATE,
        )

    evidence = list(base.get("evidence") or [])
    if not evidence:
        return AdmitResult(
            False,
            str(base.get("event_id")),
            "canonical admission requires evidence",
            REASON_EVIDENCE_REFUSED,
        )
    digests_ok, problems = _resolve_evidence(evidence, root or log.root)
    if problems:
        return AdmitResult(
            False,
            str(base.get("event_id")),
            "; ".join(problems),
            REASON_EVIDENCE_REFUSED,
        )

    validators = list(base.get("validators") or [])
    # No validator attestation means the claim rests on interpretation alone,
    # however much narrative it carries. The MNCS gate rejects it as
    # model-only; narrative volume never substitutes for attestation.
    model_only = not validators
    validator_status = combine_validators(validators)
    duplicate = False
    tally = evidence_tally_arg(evidence, digests_ok)

    security = base.get("security") or {}
    render_guard = _record(
        MNCS_JOURNAL_MODULE,
        "Sensitivity",
        [("redaction_reviewed", "bool"), ("security_detail", "bool")],
        {
            "redaction_reviewed": _boolean(bool(security.get("redaction_reviewed"))),
            "security_detail": _boolean(bool(security.get("contains_detail"))),
        },
    )
    try:
        final = evaluator.evaluate(
            tally=tally,
            validator=validator_status,
            duplicate=duplicate,
            model_only=model_only,
            trust_from=str(base.get("trust") or "observed"),
            trust_event=trust_event,
            render_guard=render_guard,
        )
    except EvaluatorUnavailable as exc:
        return AdmitResult(
            False, str(base.get("event_id")), f"held: {exc}", REASON_UNRESOLVED
        )

    if final.admission != "Admit":
        code = final.admission_reason or REASON_UNRESOLVED
        return AdmitResult(
            False,
            str(base.get("event_id")),
            f"policy refuses: {final.admission} reason {code}",
            code,
        )
    if not final.trust_accepted:
        return AdmitResult(
            False,
            str(base.get("event_id")),
            f"trust transition refused reason {final.trust_reason}",
            REASON_UNRESOLVED,
        )

    event = dict(base)
    event["trust"] = final.trust_following
    event["mncs_evaluation"] = {
        **evaluator.identity,
        "result_digest": final.result_digest,
        "verdicts": {
            "gate": final.gate,
            "admission": {"verdict": final.admission, "reason": final.admission_reason},
            "trust": {
                "accepted": final.trust_accepted,
                "following": final.trust_following,
                "reason": final.trust_reason,
            },
            "render_public": final.render_public,
        },
    }
    try:
        signed = sign_event(event, key_id, private_bytes)
    except RuntimeError as exc:
        return AdmitResult(
            False, str(base.get("event_id")), f"held: {exc}", REASON_UNRESOLVED
        )

    log.root.mkdir(parents=True, exist_ok=True)
    path = log.root / f"{signed['event_id']}.json"
    if path.exists():
        return AdmitResult(
            False,
            str(base.get("event_id")),
            "event file already exists",
            REASON_DUPLICATE,
        )
    path.write_text(
        json.dumps(signed, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (log.root / "HEAD").write_text(signed["event_digest"] + "\n", encoding="utf-8")
    # An admitted proposal leaves the candidate pool: history has one writer.
    candidate = log.proposals_dir / f"{signed['event_id']}.json"
    if candidate.is_file():
        candidate.unlink()
    return AdmitResult(True, str(signed["event_id"]), "admitted", 0, signed)


def verify_chain(
    log: EventLog, keychain: Mapping[str, bytes] | None = None
) -> list[str]:
    """Recompute every digest, signature, and link. Silent rewrites surface.

    Events are followed through their ``previous_event_digest`` links, not
    through filename order, so presentation order can never hide a fork,
    an orphan, or a broken link.
    """
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    signatures_checkable = True
    if keychain is not None and not crypto_available():
        errors.append("signatures unverifiable: 'cryptography' package unavailable")
        signatures_checkable = False
    for path in log.event_files():
        try:
            event = log.load_event(path)
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path.name}: unreadable ({exc})")
            continue
        if not isinstance(event, dict):
            errors.append(f"{path.name}: event is not an object")
            continue
        events.append(event)
        event_id = event.get("event_id", "?")
        if compute_event_id(event) != event_id:
            errors.append(f"{event_id}: event_id does not match content")
        if compute_event_digest(event) != event.get("event_digest"):
            errors.append(f"{event_id}: event_digest does not match content")
        if keychain is not None and signatures_checkable:
            issuer = event.get("issuer") or {}
            public = keychain.get(str(issuer.get("key_id") or ""))
            if public is None:
                errors.append(f"{event_id}: unknown issuer key")
            elif not verify_signature(event, public):
                errors.append(f"{event_id}: signature does not verify")
        # Trust-root discipline: evaluation presence marks canonical events.
        # The only record allowed without a live MNCS evaluation is the
        # genesis baseline, and it must stay quarantined. Anything else
        # claiming unattested standing is not history.
        if isinstance(event.get("mncs_evaluation"), dict):
            if event.get("trust") == "legacy_unattested":
                errors.append(f"{event_id}: quarantine standing on an evaluated event")
        elif (
            event.get("previous_event_digest") != GENESIS_PREVIOUS
            or event.get("trust") != "legacy_unattested"
        ):
            errors.append(f"{event_id}: event without MNCS evaluation outside genesis")
    previous: Any = GENESIS_PREVIOUS
    seen: set[Any] = set()
    while True:
        successors = [
            event
            for event in events
            if event.get("previous_event_digest") == previous
            and event.get("event_id") not in seen
        ]
        if not successors:
            break
        if len(successors) > 1:
            errors.append(
                f"chain fork at {previous}: "
                + ", ".join(str(item.get("event_id")) for item in successors)
            )
            break
        current = successors[0]
        seen.add(current.get("event_id"))
        previous = current.get("event_digest")
    for event in events:
        if event.get("event_id") not in seen:
            errors.append(
                f"{event.get('event_id')}: event is not linked into the chain"
            )
    head_file = log.root / "HEAD"
    if head_file.is_file():
        head = head_file.read_text(encoding="utf-8").strip()
        if head != previous and not (head == GENESIS_PREVIOUS and not events):
            errors.append(f"HEAD does not match the chain tip ({previous})")
    return errors


_KIND_VERBS = {
    "capability.added": "gained the capability",
    "capability.proven": "proved the capability",
    "capability.regressed": "recorded a regression in",
    "rfc.advanced": "advanced RFC",
    "rfc.completed": "completed RFC",
    "backend.conformant": "proved backend conformance for",
    "backend.regressed": "recorded a backend regression in",
    "stdlib.expanded": "expanded the standard library with",
    "pressure.discovered": "discovered language pressure in",
    "pressure.resolved": "resolved language pressure in",
    "security.finding": "recorded a security finding in",
    "security.resolved": "resolved a security finding in",
    "commons.promoted": "saw Commons promotion of",
    "project.migrated": "migrated",
    "release.created": "cut the release",
    "architecture.changed": "changed the architecture:",
}


def narrate(event: Mapping[str, Any]) -> str:
    """Deterministic human sentence. Model hints are never narrated."""
    verb = _KIND_VERBS.get(str(event.get("event_kind")), "recorded progress on")
    return (
        f"{event.get('project')} {verb} {event.get('subject')} "
        f"({event.get('previous_state')} -> {event.get('resulting_state')})."
    )


def render_projection(log: EventLog, destination: Path) -> list[Path]:
    """Regenerate the human-readable view from canonical events only."""
    destination.mkdir(parents=True, exist_ok=True)
    events = log.events()
    order: list[dict[str, Any]] = []
    previous = GENESIS_PREVIOUS
    for _ in range(len(events) + 1):
        nxt = next(
            (
                event
                for event in events
                if event.get("previous_event_digest") == previous
                and event.get("event_id")
                not in {item.get("event_id") for item in order}
            ),
            None,
        )
        if nxt is None:
            break
        order.append(nxt)
        previous = nxt.get("event_digest", "")
    written: list[Path] = []
    cards: list[str] = []
    for event in order:
        evaluation = event.get("mncs_evaluation") or {}
        verdicts = evaluation.get("verdicts") or {}
        render_public = verdicts.get("render_public", True)
        if render_public:
            narrative = narrate(event)
            heading_subject = str(event.get("subject"))
            redacted = ""
        else:
            # Withheld means withheld: neither the narrative nor the heading
            # may carry the unreviewed subject or state details.
            narrative = (
                f"{event.get('project')} recorded a {event.get('event_kind')} event "
                f"whose details are withheld pending redaction review."
            )
            heading_subject = "withheld pending redaction review"
            redacted = ' <span class="redacted">[details withheld]</span>'
        if render_public:
            evidence_items = "".join(
                f"<li><code>{html.escape(str(item.get('id', '?')))}</code> "
                f"({html.escape(str(item.get('kind', '?')))}): "
                f"{html.escape(str(item.get('uri', '?')))}</li>"
                for item in event.get("evidence", [])
            )
        else:
            # Evidence locators stay out of the public view until review;
            # only the count is shown so reviewers know material exists.
            evidence_items = (
                f"<li>{len(list(event.get('evidence', [])))} evidence item(s) "
                "withheld pending redaction review</li>"
            )
        validators = (
            ", ".join(
                f"{item.get('name')}: {item.get('verdict')}"
                for item in event.get("validators", [])
            )
            or "none recorded"
        )
        card = (
            f'<article class="journal-event" id="{html.escape(str(event.get("event_id")))}">\n'
            f"<h3>{html.escape(str(event.get('event_kind')))} — "
            f"{html.escape(heading_subject)}{redacted}</h3>\n"
            f"<p>{html.escape(narrative)}</p>\n"
            f"<ul>{evidence_items}</ul>\n"
            f"<p>Validators: {html.escape(validators)}. "
            f"Trust: {html.escape(str(event.get('trust')))}. "
            f"Digest: <code>{html.escape(str(event.get('event_digest')))}</code></p>\n"
            "</article>\n"
        )
        page = destination / f"{event.get('event_id')}.html"
        page.write_text(
            '<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8">\n'
            f"<title>{html.escape(str(event.get('event_id')))}</title></head>\n"
            f"<body>\n{card}</body>\n</html>\n",
            encoding="utf-8",
        )
        written.append(page)
        cards.append(card)
    index = destination / "index.html"
    index.write_text(
        '<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8">\n'
        "<title>MNCS Journal — canonical events</title></head>\n<body>\n"
        "<h1>MNCS Journal — canonical progress events</h1>\n"
        "<p>Generated projection of the canonical event log. "
        "The structured events are history; this page is a view.</p>\n"
        + "\n".join(cards)
        + "\n</body>\n</html>\n",
        encoding="utf-8",
    )
    written.append(index)
    return written


def describe_evaluation(
    verdicts: MncsVerdicts, identity: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        **dict(identity),
        "result_digest": verdicts.result_digest,
        "verdicts": {
            "gate": verdicts.gate,
            "admission": {
                "verdict": verdicts.admission,
                "reason": verdicts.admission_reason,
            },
            "trust": {
                "accepted": verdicts.trust_accepted,
                "following": verdicts.trust_following,
                "reason": verdicts.trust_reason,
            },
            "render_public": verdicts.render_public,
        },
    }
