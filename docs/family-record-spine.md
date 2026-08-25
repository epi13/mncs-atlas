# MNCS Family Record Spine and Concept Reconstruction Experiments

Status: descriptive architecture; bootstrap spine implemented through the MNCDS boundary

## Overview

The MNCS family is moving toward a common record flow in which each subsystem keeps ownership of its native semantics while Commons provides the shared coordination/index plane and MNCS remains the downstream assurance/conformance authority.

The proposal has two connected ideas:

1. **Family Record Spine** — producer-owned records connected by immutable identities, provenance and explicit references rather than copied into one universal schema.
2. **Concept Reconstruction Experiments (CREs)** — bounded studies where independent experimenters rebuild fundamental computing concepts using MNCS Language, allowing failures to teach both the language and the tooling family.

## Family flow

```text
MNCS Language ---- compiler / semantic records ----+
Fabric ----------- execution / host records -------+
Harness ---------- actor / routing provenance -----+
Control ---------- durable experiment identity ----+
Forge ------------ evaluator / verifier records ---+
                                                   |
                                                   v
                                    Concept Experiment envelope (Commons)
                                                   |
                                                   v
                                                 MNCDS
                        governed development record (0.2-alpha producer bindings;
                        validated by the independent MNCDS reference validator)
                                                   |
                                                   v
                                              MNCS Commons
                       DevelopmentRecord projection: exact record id + digest,
                       tri-state status preserved, supersession chain, typed
                       references back to every lower-layer identity
                                                   |
                         +-------------------------+-----------------------+
                         |                                                 |
                         v                                                 v
                 future MNEL analysis                             future RAVEL learning
                                                   |
                                                   v
                                             future MNCS
                                      assurance / conformance semantics

The implemented exercise path is:
Control -> Harness -> Language -> Fabric -> Forge -> Concept Experiment ->
MNCDS validation -> Commons; see MNCS-Commons scripts/exercise_family_record_spine.py.
```

RAVEL and MNEL are intentionally not prerequisites for the first CREs. Ordinary models can temporarily serve explicit investigator and adaptive-critic roles through Harness/Fabric while preserving their actual producer identity.

## Ownership map

- **Commons**: shared record graph, exchange, lifecycle projections, bounded queries and producer compatibility. Not correctness authority. Commons stores validated MNCDS development records as `DevelopmentRecord` projections with the exact record identity/digest and tri-state status; storage confers no semantic authority.
- **Control**: durable Concept Experiment lifecycle and coordination identity. Not scientific/evaluation authority.
- **Harness**: exact model/worker/tool routing and declared experiment roles. A role is not a project identity.
- **Fabric**: distributed execution, environment and receipt evidence. Execution success is not conformance.
- **Forge**: independent bounded candidate/verifier evaluation and `PASS`/`FAIL`/`UNKNOWN` observations. No promotion authority.
- **MNCS Language**: source legality, semantics, compiler stages, lowering and translation-validation records.
- **MNEL**: future scientific experiment interpretation/causal attribution.
- **RAVEL**: future adaptive strategy and retained learning.
- **MNCDS**: governed candidate lineage, feedback eligibility, selection, release/regeneration/replacement history. Its experimental `0.2-alpha.1` surface binds family-native evidence through versioned producer references while keeping every producer's semantics in its owning repository.
- **MNCS**: assurance, evidence acceptance and conformance semantics.

## Concept Reconstruction Experiments

A CRE does not ask an experimenter to port or transpile RAVEL, Forge, Fabric or another family component. It asks the experimenter to reconstruct one fundamental concept that such a system requires using the MNCS Language semantics currently available.

The existing implementation supplies requirements, invariants and later comparison targets. Where practical, the first candidate round should be blind to the implementation body.

The experiment loop is:

```text
fundamental concept
 -> independent MNCS Language candidates
 -> compiler + Fabric records
 -> Forge evaluation
 -> PASS / FAIL / UNKNOWN
 -> failure attribution
 -> language/compiler/tooling proposal
 -> rerun the same frozen study
```

Important failure classes include implementation error, language expressivity gap, semantic-model gap, compiler/lowering gap, verifier gap, tooling/orchestration gap, portability gap, specification ambiguity and unresolved evidence.

Failed studies are retained as regression experiments rather than discarded.

## Bootstrap roles

Before RAVEL and MNEL are operational, Harness may route ordinary models under explicit roles:

- `experimenter` / `builder`;
- `experiment-investigator`;
- `adaptive-experiment-critic`;
- `reviewer` / `skeptic`.

Their records preserve the exact model, worker, provider, Harness role and experiment identity. They must not claim to be RAVEL or MNEL.

These stand-ins later become control groups for testing whether RAVEL/MNEL actually improve experimental attribution or next-intervention selection.

## First end-to-end exercise

The recommended first CRE is the MNCS tri-state result lattice (`PASS`, `UNKNOWN`, `FAIL`). It has a tiny exhaustive state space, clear algebraic laws and can be compiled/evaluated across the current language and Fabric path.

A complete bootstrap exercise should preserve one experiment identity through:

```text
Control -> Harness -> Fabric -> Language -> Forge -> Commons -> MNCDS -> MNCS
```

The key acceptance criterion is not that every layer says PASS. It is that every layer preserves its own meaning, identities, disagreements and `UNKNOWN`s without silently strengthening another layer's evidence.

## Why no new central repository

Commons already provides the appropriate transport-neutral record/coordination plane. A new central record repository would risk duplicating Commons and collapsing authority boundaries.

A small neutral interoperability package may be extracted later only if multiple independent implementations genuinely need shared canonical reference/digest/envelope code. Domain semantics should remain in their owning repositories.
