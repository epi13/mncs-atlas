# MNCS Family Terminology

This index standardizes family-level usage. Project-specific specifications remain authoritative for formal definitions.

## A

**Agent** — A model-backed or software actor that can propose plans, code, hypotheses, tool requests, explanations, or candidate repairs. An agent is not automatically an evaluator or authority.

**Atlas** — The MNCS family-level orientation and documentation map. Non-normative.

**Authority** — The explicitly bounded right of a component, specification, evaluator, operator, or policy to make a particular decision or claim. Capability is not authority.

## C

**Candidate** — A particular proposed artifact, implementation, policy, configuration, or change under evaluation. Candidate identity and lineage should remain explicit.

**Commons** — The MNCS structured coordination and knowledge-exchange layer. Publication does not imply trust or acceptance.

**Conformance** — Satisfaction of the applicable normative MNCS requirements under the required evidence and evaluation boundary. Tool success alone is not conformance.

**Controller** — A persistent coordinating service or process that owns a bounded control/execution state, such as Fabric's controller. A controller is not necessarily a semantic router or evaluator.

**Custody** — Control over evidence, artifacts, challenges, or evaluation material. Local storage or signatures do not automatically establish protected or independent custody.

## E

**Evidence** — Identified observations, records, measurements, attestations, or verifier outputs used to support a bounded claim. Evidence must retain scope, provenance, and freshness requirements.

**Evaluator** — A component or party authorized to derive a bounded result under a declared protocol. Candidate-controlled evaluation should not be confused with independent evaluation.

## F

**Fabric** — MNCS persistent execution/evidence infrastructure for exact-target work, authenticated transport, capability/resource observation, and durable execution records.

**Forge** — Non-normative development/evidence orchestration for declared providers, checks, candidate lineage, and evaluator-mode boundaries.

## H

**Harness** — A policy layer that arranges model/tool interactions and accepts or rejects results for a particular workspace/deployment. In current family architecture, a local harness may consume Fabric without owning Fabric.

## M

**MNCS** — Machine-Native Complexity Standard. An open experimental standard for accepting generated or machine-optimized implementations through bounded evidence.

**MNCDS** — Machine-Native Complexity Development Standard. A separate development-process specification governing decomposition, candidate lifecycle, evidence flow, and related development controls.

**MNEL** — Machine-Native Experimental Learning. An evidence-governed experimental learning framework using bounded interventions, causal attribution, and verified-experience distillation.

**Machine-native** — Designed so machine actors can operate on explicit semantic structure, contracts, identities, evidence, and bounded interfaces without making human inspection impossible. It does not mean machine-exclusive.

## P

**PASS / FAIL / UNKNOWN** — Core result semantics. Family-level aggregation is conservative: `FAIL > UNKNOWN > PASS`. Missing or unsupported evidence must not be silently converted to `PASS`.

**Provider** — A replaceable tool or execution capability used to produce observations or evidence, such as a compiler, analyzer, benchmark, mutation system, runtime harness, or verifier adapter.

**Provenance** — Traceable origin and transformation history for an artifact, claim, result, or knowledge record.

## R

**RAVEL** — Recursive Adaptive Vector Execution Lattice. An adaptive evidence strategy and learning layer that reasons beneath MNCS/MNCDS authority.

**Reference Study** — A controlled empirical study intended to test MNCS-related hypotheses against frozen workloads, upstream/reference behavior, or alternative implementations.

## V

**Verifier** — A bounded mechanism that checks a declared property or produces evidence. A verifier's result is limited to its supported claim and trust boundary.

## W

**Worker** — An identified execution participant capable of running admitted workloads and reporting factual capability/resource/runtime observations. Worker availability does not by itself imply trust, independence, or suitability for a particular claim.

## Usage rules

- Prefer **MNCS project family** or **MNCS ecosystem** for the collection of related repositories.
- Use **MNCS** only for the standard/authority layer when ambiguity would matter.
- Use **MNCDS** for the development-process specification rather than treating it as a synonym for MNCS.
- Say **execution passed** when referring to execution checks; do not shorten that to **MNCS passed** unless formal MNCS validation is actually what occurred.
- Use **independent** only when the relevant evaluator, custody, and control requirements are actually independent.
- Treat **UNKNOWN** as an intentional result, not an error string to be optimized away.
