"""Capability router: compose owning-subsystem authority into broker decisions.

Atlas routes; it does not re-decide. Each bundled adapter speaks for one
owning subsystem using that subsystem's declared rules (rights scopes,
MNCDS lifecycle order, Forge separation-of-duties, Commons independent
confirmation, Fabric placement, action declaration). The router combines
findings with the family verdict lattice (FAIL > UNKNOWN > PASS) and always
names the deciding authority in the response.

Live subsystem services can replace any bundled adapter: implement
:meth:`AuthorityAdapter.evaluate` against the real authority and register it
with :class:`Router`. The decision shape is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Session
from .vocabulary import (
    CAPABILITIES,
    LIFECYCLE_GATE,
    LIFECYCLE_STATES,
    RIGHTS_SCOPE_FOR_CAPABILITY,
    Capability,
    get_capability,
)

_STATE_ORDER = {"OUTSIDE": 0, "KNOWN": 1, "ADMITTED": 2, "SCOPED": 3,
                "CONFORMANT_FOR_CAPABILITY": 4}
_LIFECYCLE_ORDER = {name: index for index, name in enumerate(LIFECYCLE_STATES)}

GOVERNANCE_CAPABILITIES = frozenset(
    cap_id for cap_id, cap in CAPABILITIES.items()
    if cap.sensitivity == "governance"
)


@dataclass(frozen=True)
class AuthorityFinding:
    """One owning subsystem's evaluation of a capability query."""

    authority: str
    verdict: str  # PASS | FAIL | UNKNOWN | INVALID
    reason: str
    missing: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass
class Query:
    """Normalized capability query routed to authority adapters."""

    capability: Capability
    session: Session
    scope: str = ""
    evidence: tuple[str, ...] = ()
    lifecycle_state: str = "proposal"
    action: dict = field(default_factory=dict)
    attestations: tuple[dict, ...] = ()
    execution_target: str = ""
    network_declared: bool = False

    def all_evidence(self) -> set[str]:
        return set(self.session.evidence) | set(self.evidence)


class AuthorityAdapter:
    """Interface for an owning subsystem's authority evaluation."""

    name = "base"

    def handles(self, capability_id: str) -> bool:
        raise NotImplementedError

    def evaluate(self, query: Query) -> AuthorityFinding:
        raise NotImplementedError


def _fail(authority: str, reason: str, missing: tuple[str, ...] = ()) -> AuthorityFinding:
    return AuthorityFinding(authority=authority, verdict="FAIL", reason=reason, missing=missing)


def _unknown(authority: str, reason: str, missing: tuple[str, ...] = ()) -> AuthorityFinding:
    return AuthorityFinding(authority=authority, verdict="UNKNOWN", reason=reason, missing=missing)


def _pass(authority: str, reason: str, evidence_refs: tuple[str, ...] = ()) -> AuthorityFinding:
    return AuthorityFinding(authority=authority, verdict="PASS", reason=reason,
                            evidence_refs=evidence_refs)


class AdmissionPostureAdapter(AuthorityAdapter):
    """Atlas-side admission posture: state, scope, and held grants.

    Authority: atlas (orientation-only). This adapter reports what admission
    state alone establishes. It never grants conditional or denied-posture
    capabilities; those need owning-subsystem evidence (UNKNOWN) or are
    refused at the Atlas boundary (FAIL for capability.grant).
    """

    name = "atlas-admission"

    def handles(self, capability_id: str) -> bool:
        return True

    def evaluate(self, query: Query) -> AuthorityFinding:
        cap = query.capability
        session = query.session
        if cap.default_posture == "denied":
            return _fail(
                self.name,
                f"{cap.id} is never granted by admission state; "
                f"routed to {cap.owner} for an explicit scoped grant.",
                missing=list(cap.evidence),
            )
        if cap.default_posture == "conditional":
            # Atlas never grants conditional capabilities itself; it defers
            # to the owning subsystem adapters, whose FAIL/UNKNOWN findings
            # decide the outcome. A PASS here only means "no Atlas-side bar".
            return _pass(
                self.name,
                f"{cap.id} is conditional: admission state is no bar, "
                f"owning authority {cap.owner} decides on evidence.",
            )
        # grantable posture: check admission state and scope.
        required = cap.grant_at_state or "ADMITTED"
        if _STATE_ORDER.get(session.state, 0) < _STATE_ORDER[required]:
            return _unknown(
                self.name,
                f"{cap.id} becomes grantable at {required}; "
                f"session is {session.state}.",
                missing=[f"admission-state:{required}"],
            )
        if cap.sensitivity != "open":
            scope = query.scope or session.scope
            if not scope:
                return _unknown(
                    self.name, f"{cap.id} requires a bound session scope.",
                    missing=["session.scope"],
                )
        return _pass(
            self.name,
            f"admission state {session.state} establishes {cap.id}"
            + (f" in scope {query.scope or session.scope}."
               if cap.sensitivity != "open" else "."),
        )


class RightsAdapter(AuthorityAdapter):
    """Rights/provenance authority: scopes attach to actions, not identity.

    Source vocabulary: mncs-rights-provenance AUTHORITY_SCOPES (may_*).
    Checks required scope evidence and, for governance capabilities,
    separation of duties between proposer and confirmer.
    """

    name = "rights-provenance"

    def handles(self, capability_id: str) -> bool:
        return capability_id in RIGHTS_SCOPE_FOR_CAPABILITY

    def evaluate(self, query: Query) -> AuthorityFinding:
        cap = query.capability
        evidence = query.all_evidence()
        required_scope = RIGHTS_SCOPE_FOR_CAPABILITY[cap.id]
        if "provenance.complete" in cap.evidence and "provenance.complete" not in evidence:
            return _unknown(
                self.name,
                f"{cap.id} needs complete provenance before rights scope "
                f"{required_scope} can attach.",
                missing=["provenance.complete"],
            )
        if cap.sensitivity == "governance":
            confirmations = _independent_confirmations(query)
            if len(confirmations) < 2:
                return _fail(
                    self.name,
                    f"{cap.id} needs 2 independent confirmations distinct from "
                    f"proposer and requestor; found {len(confirmations)}. "
                    "Self-approval cannot satisfy governance evidence.",
                    missing=["independent_confirmations>=2"],
                )
            return _pass(
                self.name,
                f"rights scope {required_scope} attaches with "
                f"{len(confirmations)} independent confirmations.",
                evidence_refs=tuple(sorted(confirmations)),
            )
        if cap.id == "change.merge":
            confirmations = _independent_confirmations(query)
            if len(confirmations) < 2:
                return _unknown(
                    self.name,
                    f"{cap.id} needs 2 independent confirmations; "
                    f"found {len(confirmations)}.",
                    missing=["independent_confirmations>=2"],
                )
        return _pass(self.name, f"rights scope {required_scope} attaches to the declared action.")


def _independent_confirmations(query: Query) -> set[str]:
    """Attesters distinct from the requestor and the proposer."""
    requestor = query.session.participant.identity
    proposer = (query.action or {}).get("proposed_by", requestor)
    excluded = {requestor, proposer}
    return {
        item["by"] for item in query.attestations
        if isinstance(item, dict) and item.get("by") and item["by"] not in excluded
    }


class LifecycleAdapter(AuthorityAdapter):
    """MNCDS lifecycle authority: proposal is never promotion."""

    name = "mncds"

    def handles(self, capability_id: str) -> bool:
        return capability_id in LIFECYCLE_GATE

    def evaluate(self, query: Query) -> AuthorityFinding:
        cap = query.capability
        required = LIFECYCLE_GATE[cap.id]
        actual = query.lifecycle_state or "proposal"
        if actual not in _LIFECYCLE_ORDER:
            return AuthorityFinding(
                authority=self.name, verdict="INVALID",
                reason=f"unknown lifecycle state: {actual!r}",
            )
        if _LIFECYCLE_ORDER[actual] < _LIFECYCLE_ORDER[required]:
            if cap.id in ("change.merge", "release.publish"):
                return _fail(
                    self.name,
                    f"{cap.id} requires lifecycle state {required}; "
                    f"change is at {actual}. A valid proposal does not "
                    "confer promotion authority.",
                    missing=[f"lifecycle:{required}"],
                )
            return _unknown(
                self.name,
                f"{cap.id} requires lifecycle state {required}; at {actual}.",
                missing=[f"lifecycle:{required}"],
            )
        return _pass(self.name, f"lifecycle state {actual} satisfies {required} for {cap.id}.")


class ForgeAdapter(AuthorityAdapter):
    """Forge policy authority for protected and governance transitions."""

    name = "forge"

    _PROTECTED = frozenset({"validator.modify", "policy.modify", "release.publish"})

    def handles(self, capability_id: str) -> bool:
        return capability_id in self._PROTECTED

    def evaluate(self, query: Query) -> AuthorityFinding:
        cap = query.capability
        action = query.action or {}
        change_id = action.get("change_id")
        validating = action.get("validating_change_id")
        if change_id and validating and change_id == validating and cap.id in (
            "validator.modify", "policy.modify", "change.merge",
        ):
            return _fail(
                self.name,
                "Self-validation refused: the change under review cannot be "
                "the validator that approves it. Route through an independent "
                "evaluation.",
                missing=["independent forge evaluation"],
            )
        evidence = query.all_evidence()
        if "forge.evaluation" not in evidence:
            return _unknown(
                self.name,
                f"{cap.id} needs a Forge policy evaluation on record.",
                missing=["forge.evaluation"],
            )
        return _pass(self.name, f"Forge evaluation on record for {cap.id}.")


class CommonsAdapter(AuthorityAdapter):
    """Commons evidence authority: independent confirmation accounting."""

    name = "commons"

    def handles(self, capability_id: str) -> bool:
        cap = get_capability(capability_id)
        return "independent_confirmations>=2" in cap.evidence

    def evaluate(self, query: Query) -> AuthorityFinding:
        confirmations = _independent_confirmations(query)
        if len(confirmations) >= 2:
            return _pass(
                self.name,
                f"{len(confirmations)} independent confirmations accumulated.",
                evidence_refs=tuple(sorted(confirmations)),
            )
        return _unknown(
            self.name,
            f"independent confirmations: {len(confirmations)}/2 recorded. "
            "Commons coordination can accumulate the remainder; Atlas does "
            "not manufacture them.",
            missing=["independent_confirmations>=2"],
        )


class FabricAdapter(AuthorityAdapter):
    """Fabric execution authority: placement and declared execution bounds."""

    name = "fabric"

    _EXECUTION = frozenset({
        "tests.execute", "artifact.create", "network.fetch", "worker.dispatch",
    })

    def handles(self, capability_id: str) -> bool:
        return capability_id in self._EXECUTION

    def evaluate(self, query: Query) -> AuthorityFinding:
        cap = query.capability
        if not (query.scope or query.session.scope):
            return _fail(
                self.name,
                f"{cap.id} without a session scope is undeclared execution.",
                missing=["session.scope"],
            )
        if cap.id in ("tests.execute", "worker.dispatch") and not query.execution_target:
            return _unknown(
                self.name,
                f"{cap.id} needs a declared Fabric execution target; "
                "placement is Fabric's decision.",
                missing=["execution.target"],
            )
        if cap.id == "network.fetch" and not query.network_declared:
            return _fail(
                self.name,
                "Undeclared network use is refused; declare the fetch first.",
                missing=["network.declared"],
            )
        return _pass(self.name, f"execution bounds declared for {cap.id}.")


class ActionsAdapter(AuthorityAdapter):
    """mncs-actions structural conformance: consequential effects need actions."""

    name = "mncs-actions"

    # repo.edit is intentionally absent: a scoped working-tree edit is the
    # declared context itself. Durable effects (merge, publish, promotion)
    # are action-gated instead.
    _ACTION_SHAPED = frozenset({
        "change.validate", "change.sign", "change.merge", "release.publish",
        "validator.modify", "policy.modify",
    })

    def handles(self, capability_id: str) -> bool:
        return capability_id in self._ACTION_SHAPED

    def evaluate(self, query: Query) -> AuthorityFinding:
        cap = query.capability
        action = query.action or {}
        if not action.get("id"):
            if cap.id in ("change.merge", "release.publish", "validator.modify",
                           "policy.modify"):
                return _fail(
                    self.name,
                    f"{cap.id} without a declared MNCS action is a direct "
                    "mutation; declare intent as an action first.",
                    missing=["action.declared"],
                )
            return _unknown(
                self.name,
                f"{cap.id} should travel through a declared MNCS action.",
                missing=["action.declared"],
            )
        evidence = query.all_evidence()
        if cap.id in ("change.merge", "release.publish") and "actions.conformant" not in evidence:
            return _unknown(
                self.name,
                f"action {action.get('id')} is declared but not yet conformant.",
                missing=["actions.conformant"],
            )
        if "tests.passed" in cap.evidence and "tests.passed" not in evidence:
            return _unknown(
                self.name,
                f"action {action.get('id')} needs passing tests on record.",
                missing=["tests.passed"],
            )
        return _pass(self.name, f"action {action.get('id')} is structurally conformant.")


DEFAULT_ADAPTERS: tuple[type[AuthorityAdapter], ...] = (
    AdmissionPostureAdapter,
    RightsAdapter,
    LifecycleAdapter,
    ForgeAdapter,
    CommonsAdapter,
    FabricAdapter,
    ActionsAdapter,
)


class Router:
    """Compose owning-subsystem findings into one broker decision."""

    def __init__(self, adapters: list[AuthorityAdapter] | None = None) -> None:
        self.adapters = adapters if adapters is not None else [cls() for cls in DEFAULT_ADAPTERS]

    def query(
        self,
        session: Session,
        capability_id: str,
        scope: str = "",
        evidence: tuple[str, ...] | list[str] = (),
        lifecycle_state: str = "proposal",
        action: dict | None = None,
        attestations: tuple[dict, ...] | list[dict] = (),
        execution_target: str = "",
        network_declared: bool = False,
    ) -> dict:
        cap = get_capability(capability_id)
        request = Query(
            capability=cap,
            session=session,
            scope=scope or session.scope,
            evidence=tuple(evidence),
            lifecycle_state=lifecycle_state,
            action=dict(action or {}),
            attestations=tuple(attestations),
            execution_target=execution_target,
            network_declared=network_declared,
        )
        findings = [
            adapter.evaluate(request)
            for adapter in self.adapters
            if adapter.handles(capability_id)
        ]
        verdict = "PASS"
        for finding in findings:
            if finding.verdict == "INVALID":
                verdict = "INVALID"
                break
            if finding.verdict == "FAIL":
                verdict = "FAIL"
                break
            if finding.verdict == "UNKNOWN":
                verdict = "UNKNOWN"
        if verdict == "PASS":
            status = "granted"
        elif verdict == "UNKNOWN":
            status = "conditional"
        else:
            status = "denied"
        missing: list[str] = []
        for finding in findings:
            for item in finding.missing:
                if item not in missing:
                    missing.append(item)
        reasons = "; ".join(f"{item.authority}: {item.reason}" for item in findings)
        return {
            "schema_version": "mncs.atlas-capability-decision/1",
            "capability": capability_id,
            "status": status,
            "verdict": verdict,
            "authority": cap.owner,
            "decision_by": [item.authority for item in findings],
            "reason": reasons,
            "missing": missing,
            "evidence_required": list(cap.evidence),
            "conformant_path": list(cap.conformant_path),
            "scope": request.scope,
        }
