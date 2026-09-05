"""Host-side scalar ABI glue for the MNCS admission module.

``mncs/admission.mncs`` is the executable admission, session,
capability-broker, denial, bypass, and orientation semantics. It speaks only
scalars (``i64``/``bool``). This module is the thin host glue that translates
between the rich Python admission model (:mod:`admission.vocabulary`,
:mod:`admission.router`, :mod:`admission.model`) and that scalar ABI.

Ownership stays distributed: the tables here project owner-defined
vocabulary (capability order, owners, evidence names, lifecycle states)
onto codes. They never re-decide what an owner has not decided. The
canonical composition mechanism is the MNCS module; this glue only encodes
and decodes its boundary.

Packing layouts (all fields little-endian bit ranges over ``i64``):

- session: state 0-2, kind 3-4, scope-bound 5, identity 6-29 (host-interned,
  24 bits), evidence 30-37, conformant 38-54. Transition results extend it:
  ok 55, reason 56-58.
- decision: status 0-1 (0 granted, 1 conditional, 2 denied), verdict 2-3
  (0 PASS, 1 FAIL, 2 UNKNOWN), malformed 4, authority 5-8, missing 9-16
  (evidence bits), need-confirmations 17, first-blocking reason 18-22.
- orientation: state 0-2, granted 3-7, conditional 8-12, denied 13-17,
  status pack 18-51 (two bits per capability, code order).
- denial: capability 0-4, authority 5-8, missing 9-16, need-confirmations 17,
  reason 18-22, path steps 23-42 (4 x 5 bits), path count 43-44.
- bypass: code 0-3, severity 4-5, authority 6-9, routes 10-27 (3 x 6 bits),
  route count 28-29.
"""

from __future__ import annotations

from .vocabulary import (
    ADMISSION_STATES,
    OWNERS,
    STATUSES,
    VERDICTS,
    capability_ids,
)

CAPABILITY_CODES: dict[str, int] = {
    name: code for code, name in enumerate(capability_ids())
}
OWNER_CODES: dict[str, int] = {
    name: code for code, name in enumerate(OWNERS)
}
STATE_CODES: dict[str, int] = {
    name: code for code, name in enumerate(ADMISSION_STATES)
}
STATUS_CODES: dict[str, int] = {name: code for code, name in enumerate(STATUSES)}
VERDICT_CODES: dict[str, int] = {name: code for code, name in enumerate(VERDICTS)}

# Evidence-string to missing-bit projection. Evidence the scalar ABI cannot
# name (admission-state rungs, lifecycle rungs, independent-forge-evaluation
# prose, participant identity) travels as a first-blocking reason code or
# via the need-confirmations flag instead; see derive_query_expectation.
EVIDENCE_BITS: dict[str, int] = {
    "session.scope": 0,
    "execution.target": 1,
    "network.declared": 2,
    "action.declared": 3,
    "actions.conformant": 4,
    "provenance.complete": 5,
    "tests.passed": 6,
    "forge.evaluation": 7,
}

# First-blocking reason codes, in canonical adapter order
# (posture, rights, lifecycle, forge, commons, fabric, actions).
# 0 ok/defer, 1 needs admission state, 2 needs scope,
# 3 needs provenance.complete, 4 governance confirmations insufficient,
# 5 independent confirmations missing, 6 lifecycle too early (refused),
# 7 lifecycle too early (advance first), 8 needs forge evaluation,
# 9 self-validation refused, 10 never granted by state,
# 11 needs execution target, 12 undeclared network use,
# 13 needs declared action, 14 action not conformant,
# 15 needs passing tests, 16 unknown capability, 17 unknown lifecycle,
# 18 undeclared execution scope.
_PASS = "PASS"

# Conformant-path step projection. Atlas defines this integer projection of
# the owning subsystems' conformant-path strings so denials and bypass
# findings can name routes in the scalar ABI. Keys are the EXACT strings
# produced by admission.vocabulary (capability conformant paths) and
# admission.bypass (finding conformant routes); a string change here fails
# parity loudly instead of silently renaming a route.
STEP_CODES: dict[str, int] = {
    "change.propose": 1,
    "validate": 2,
    "provide evidence": 3,
    "promotion": 4,
    "declare execution target": 5,
    "worker.dispatch": 6,
    "tests.execute": 7,
    "declare network use": 8,
    "declare intent as MNCS action": 9,
    "change.validate": 10,
    "record provenance": 11,
    "change.sign": 12,
    "promotion decision": 13,
    "release.publish": 14,
    "forge evaluation": 15,
    "independent confirmation": 16,
    "request capability": 17,
    "owning-authority review": 18,
    "scoped grant": 19,
    "fabric placement": 20,
    "re-attach provenance": 21,
    "re-validate": 22,
    "reproduce the artifact": 23,
    "re-record evidence with valid digests": 24,
    "declare a cross-repository action": 25,
    "per-repo authority review": 26,
    "re-enable the check": 27,
    "record a governed exception with expiry": 28,
    "advance through validation": 29,
    "independent forge evaluation": 30,
    "record transformation lineage": 31,
}

# (adapter authority, reason substring, reason code). The substrings track
# adapter prose on purpose: if an adapter rewords a finding, parity fails
# loudly and the mapping is consciously re-confirmed.
REASON_RULES: tuple[tuple[str, str, int], ...] = (
    ("atlas-admission", "never granted", 10),
    ("atlas-admission", "becomes grantable", 1),
    ("atlas-admission", "requires a bound", 2),
    ("rights-provenance", "needs complete provenance", 3),
    ("rights-provenance", "needs 2 independent confirmations distinct", 4),
    ("rights-provenance", "needs 2 independent confirmations;", 5),
    ("mncds", "requires lifecycle", 6),
    ("forge", "Self-validation", 9),
    ("forge", "needs a Forge policy evaluation", 8),
    ("commons", "independent confirmations:", 5),
    ("fabric", "without a session scope", 18),
    ("fabric", "needs a declared Fabric execution target", 11),
    ("fabric", "Undeclared network", 12),
    ("mncs-actions", "without a declared MNCS action", 13),
    ("mncs-actions", "should travel through", 13),
    ("mncs-actions", "declared but not yet conformant", 14),
    ("mncs-actions", "needs passing tests", 15),
)

# Event-kind projection for the bypass scalar ABI: 0 mutation, 1 evidence,
# 2 execution, 3 governance.
EVENT_KIND_CODES: dict[str, int] = {
    "mutation": 0,
    "evidence": 1,
    "execution": 2,
    "governance": 3,
}
_BYPASS_CODES: dict[str, int] = {
    "DIRECT_PROTECTED_MUTATION": 1,
    "SELF_VALIDATION": 2,
    "PROVENANCE_STRIPPING": 3,
    "FABRICATED_EVIDENCE": 4,
    "UNDECLARED_CROSS_REPO_MUTATION": 5,
    "UNDECLARED_NETWORK_USE": 6,
    "UNAUTHORIZED_WORKER_DISPATCH": 7,
    "CI_CONFORMANCE_DISABLING": 8,
    "PROMOTION_OUTSIDE_LIFECYCLE": 9,
}
_SEVERITY_CODES: dict[str, int] = {"medium": 1, "high": 2}


def first_blocking_reason_code(findings: list, capability_id: str) -> int:
    """First non-PASS finding in canonical adapter order, as a reason code."""
    for finding in findings:
        if finding.verdict == _PASS:
            continue
        for adapter, fragment, code in REASON_RULES:
            if finding.authority == adapter and fragment in finding.reason:
                if adapter == "mncds" and code == 6 and capability_id not in (
                    "change.merge",
                    "release.publish",
                ):
                    return 7
                return code
        raise ValueError(f"unmapped finding reason: {finding.authority}: {finding.reason}")
    return 0


def derive_query_expectation(router, session, capability_id: str, **kwargs) -> dict[str, int]:
    """Scalar decision expectation derived from the rich router decision."""
    from .router import Query, get_capability

    decision = router.query(session, capability_id, **kwargs)
    cap = get_capability(capability_id)
    query = Query(
        capability=cap,
        session=session,
        scope=kwargs.get("scope", "") or session.scope,
        evidence=tuple(kwargs.get("evidence", ())),
        lifecycle_state=kwargs.get("lifecycle_state", "proposal"),
        action=dict(kwargs.get("action") or {}),
        attestations=tuple(kwargs.get("attestations", ())),
        execution_target=kwargs.get("execution_target", ""),
        network_declared=kwargs.get("network_declared", False),
    )
    findings = [
        adapter.evaluate(query)
        for adapter in router.adapters
        if adapter.handles(capability_id)
    ]
    missing_bits = 0
    for item in decision["missing"]:
        if item in EVIDENCE_BITS:
            missing_bits |= 1 << EVIDENCE_BITS[item]
    return {
        "status": STATUS_CODES[decision["status"]],
        "verdict": VERDICT_CODES[decision["verdict"]],
        "authority": OWNER_CODES[decision["authority"]],
        "missing": missing_bits,
        "need": 1 if "independent_confirmations>=2" in decision["missing"] else 0,
        "reason": first_blocking_reason_code(findings, capability_id),
    }


def derive_denial_expectation(
    router, session, capability_id: str, **kwargs
) -> tuple[int, int]:
    """(decision_pack, denial_pack) derived from the rich decision chain."""
    from .denials import denial_from_decision
    from .vocabulary import get_capability

    decision = router.query(session, capability_id, **kwargs)
    flat = derive_query_expectation(router, session, capability_id, **kwargs)
    decision_pack = pack_decision(
        flat["status"],
        flat["verdict"],
        authority=flat["authority"],
        missing=flat["missing"],
        need_confirmations=bool(flat["need"]),
        reason=flat["reason"],
    )
    denial = denial_from_decision(decision)
    assert denial is not None, f"expected a denied decision for {capability_id}"
    steps = [STEP_CODES[step] for step in denial["conformant_path"]]
    padded = tuple((steps + [0, 0, 0, 0])[:4])
    denial_pack = pack_denial(
        CAPABILITY_CODES[capability_id],
        OWNER_CODES[denial["authority"]],
        flat["missing"],
        bool(flat["need"]),
        flat["reason"],
        paths=padded,
        path_count=len(steps),
    )
    return decision_pack, denial_pack


def derive_bypass_expectation(event: dict) -> dict[str, int]:
    """Scalar bypass-finding expectation derived from Python scan()."""
    from .bypass import scan

    findings = scan([event])
    assert len(findings) == 1, f"expected one finding for {event}"
    finding = findings[0]
    routes = [STEP_CODES[step] for step in finding["conformant_route"]]
    padded = tuple((routes + [0, 0, 0])[:3])
    return {
        "code": _BYPASS_CODES[finding["code"]],
        "severity": _SEVERITY_CODES[finding["severity"]],
        "authority": OWNER_CODES[finding["authority"]],
        "routes": padded,
        "route_count": len(routes),
    }


class StringTable:
    """Host interning of identity/attester strings to nonzero i64.

    Only equality is ever observed (self-attestation exclusion), so any
    injective mapping preserves semantics. 0 means unset.
    """

    def __init__(self) -> None:
        self._codes: dict[str, int] = {}

    def intern(self, name: str) -> int:
        if name not in self._codes:
            self._codes[name] = len(self._codes) + 1
        return self._codes[name]


def pack_session(
    state: int,
    kind: int = 0,
    scope_bound: bool = False,
    identity: int = 0,
    evidence: int = 0,
    conformant: int = 0,
) -> int:
    return (
        state
        + kind * 8
        + (32 if scope_bound else 0)
        + (identity % 16777216) * 64
        + (evidence % 256) * 1073741824
        + (conformant % 131072) * 274877906944
    )


def unpack_session(packed: int) -> dict[str, int]:
    return {
        "state": packed % 8,
        "kind": (packed // 8) % 4,
        "scope_bound": (packed // 32) % 2,
        "identity": (packed // 64) % 16777216,
        "evidence": (packed // 1073741824) % 256,
        "conformant": (packed // 274877906944) % 131072,
        "ok": (packed // 36028797018963968) % 2,
        "reason": (packed // 72057594037927936) % 8,
    }


def pack_decision(
    status: int,
    verdict: int,
    malformed: bool = False,
    authority: int = 0,
    missing: int = 0,
    need_confirmations: bool = False,
    reason: int = 0,
) -> int:
    return (
        status
        + verdict * 4
        + (16 if malformed else 0)
        + (authority % 16) * 32
        + (missing % 256) * 512
        + (131072 if need_confirmations else 0)
        + (reason % 32) * 262144
    )


def unpack_decision(packed: int) -> dict[str, int]:
    return {
        "status": packed % 4,
        "verdict": (packed // 4) % 4,
        "malformed": (packed // 16) % 2,
        "authority": (packed // 32) % 16,
        "missing": (packed // 512) % 256,
        "need_confirmations": (packed // 131072) % 2,
        "reason": (packed // 262144) % 32,
    }


def pack_orientation(state: int, granted: int, conditional: int, denied: int, pack: int) -> int:
    return state + granted * 8 + conditional * 256 + denied * 8192 + pack * 262144


def unpack_orientation(packed: int) -> dict[str, int]:
    return {
        "state": packed % 8,
        "granted": (packed // 8) % 32,
        "conditional": (packed // 256) % 32,
        "denied": (packed // 8192) % 32,
        "pack": (packed // 262144),
    }


def pack_denial(
    cap: int,
    authority: int,
    missing: int,
    need_confirmations: bool,
    reason: int,
    paths: tuple[int, int, int, int] = (0, 0, 0, 0),
    path_count: int = 0,
) -> int:
    return (
        (cap % 32)
        + (authority % 16) * 32
        + (missing % 256) * 512
        + (131072 if need_confirmations else 0)
        + (reason % 32) * 262144
        + (paths[0] % 32) * 8388608
        + (paths[1] % 32) * 268435456
        + (paths[2] % 32) * 8589934592
        + (paths[3] % 32) * 274877906944
        + path_count * 8796093022208
    )


def pack_bypass(
    code: int,
    severity: int,
    authority: int,
    routes: tuple[int, int, int] = (0, 0, 0),
    route_count: int = 0,
) -> int:
    return (
        (code % 16)
        + (severity % 4) * 16
        + (authority % 16) * 64
        + (routes[0] % 64) * 1024
        + (routes[1] % 64) * 65536
        + (routes[2] % 64) * 4194304
        + route_count * 268435456
    )
