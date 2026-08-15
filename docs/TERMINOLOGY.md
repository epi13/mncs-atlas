# MNCS Family Terminology

This index standardizes family-level usage. Project-specific specifications remain authoritative for formal definitions.

## A

**Acceptance** — A scoped decision by the layer authorized to decide whether a result is sufficient for its workflow. MNCS Harness or another deployment can accept a result for that deployment without establishing formal MNCS conformance.

**Agent** — A model-backed or software actor that can propose plans, code, hypotheses, tool requests, explanations, or candidate repairs. An agent is not automatically an evaluator or authority.

**Atlas** — The MNCS family-level orientation and documentation map. Non-normative.

**Authority** — The explicitly bounded right of a component, specification, evaluator, operator, or policy to make a particular decision or claim. Capability is not authority.

## C

**Candidate** — A particular proposed artifact, implementation, policy, configuration, or change under evaluation. Candidate identity and lineage should remain explicit.

**Commons** — The MNCS persistent structured coordination and knowledge-exchange layer. It provides durable shared/institutional memory; publication does not imply trust, execution permission, or acceptance.

**Conformance** — Satisfaction of the applicable normative MNCS requirements under the required evidence and evaluation boundary. Tool success, deployment acceptance, or execution success alone is not conformance.

**Control surface** — A bounded operator/client interface that exposes capabilities without automatically owning the services behind them. MNCS Control MCP is a deployment-specific control surface, not a source of conformance authority.

**Controller** — A persistent coordinating service or process that owns a bounded control/execution state, such as Fabric's controller. A controller is not necessarily a semantic router or evaluator.

**Custody** — Control over evidence, artifacts, challenges, or evaluation material. Local storage or signatures do not automatically establish protected or independent custody.

## E

**Evidence** — Identified observations, records, measurements, attestations, or verifier outputs used to support a bounded claim. Evidence must retain scope, provenance, and freshness requirements.

**Evaluator** — A component or party authorized to derive a bounded result under a declared protocol. Candidate-controlled evaluation should not be confused with independent evaluation.

## F

**Fabric** — MNCS persistent execution/evidence infrastructure for worker identity and presence, exact-target work, authenticated transport, capability/resource observation, retry/recovery, and durable execution records.

**Forge** — Non-normative development/evidence orchestration for declared providers, checks, candidate lineage, evidence gaps, and evaluator-mode boundaries.

## H

**Harness** — Reusable operator infrastructure that arranges model/tool interactions and accepts or rejects results for a particular workspace/deployment. In current family architecture, MNCS Harness consumes persistent Fabric and Commons services without owning their lifecycle. **Harness is not a normative MNCS requirement.**

## L

**Lifecycle owner** — The component authoritative for a declared persistent identity/history/recovery domain. Consumers do not inherit lifecycle ownership merely because they can query, invoke, or reconnect to that service.

## M

**MNCS** — Machine-Native Complexity Standard. An open experimental standard for accepting generated or machine-optimized implementations through bounded evidence. Normative implementation-evidence authority.

**MNCS Control MCP** — A current deployment-specific protected remote-workspace control surface. It exposes authorized development capabilities and bounded adapters to MNCS services; it does not own Fabric fleet lifecycle, Harness routing policy, Commons persistence, or MNCS conformance.

**MNCS Harness** — Reusable operator infrastructure for routing, governing, tool-enabling, approving, and accepting AI/model work. Published at https://github.com/epi13/mncs-harness. Not a normative MNCS requirement.

**MNCDS** — Machine-Native Complexity Development Specification. An independently versioned development-process specification governing decomposition, candidate lifecycle, evidence flow, and related development controls.

**MNEL** — Machine-Native Experimental Learning. An evidence-governed experimental learning framework using bounded interventions, causal attribution, and verified-experience distillation.

**Machine-native** — Designed so machine actors can operate on explicit semantic structure, contracts, identities, evidence, and bounded interfaces without making human inspection impossible. It does not mean machine-exclusive.

## O

**Operator stack** — The reference deployment topology used to do work (Control, Harness, Forge, Fabric, Commons, and related services). Descriptive, not a normative MNCS requirement.

## P

**PASS / FAIL / UNKNOWN** — Core result semantics. Family-level aggregation is conservative: `FAIL > UNKNOWN > PASS`. Missing or unsupported evidence must not be silently converted to `PASS`.

**Persistent service** — A long-lived component whose declared state and lifecycle survive individual client requests or disconnects. Persistence should have one explicit owner rather than being reconstructed independently by consumers.

**Provider** — A replaceable tool or execution capability used to produce observations or evidence, such as a compiler, analyzer, benchmark, mutation system, runtime harness, or verifier adapter.

**Provenance** — Traceable origin and transformation history for an artifact, claim, result, or knowledge record.

## R

**RAVEL** — Recursive Adaptive Vector Execution Lattice. An adaptive evidence strategy and learning layer that reasons beneath MNCS/MNCDS authority.

**Reference Study** — A controlled empirical study intended to test MNCS-related hypotheses against frozen workloads, upstream/reference behavior, or alternative implementations.

**Reference deployment** — A concrete operator stack used to do family work. It is descriptive orientation, not a personal laboratory and not a conformance requirement.

## S

**Service consumer** — A client that uses a service's public contract while leaving the service's private state, lifecycle, identity, and recovery authority with the service owner.

## V

**Verifier** — A bounded mechanism that checks a declared property or produces evidence. A verifier's result is limited to its supported claim and trust boundary.

## W

**Worker** — An identified execution participant capable of running admitted workloads and reporting factual capability/resource/runtime observations. Worker availability does not by itself imply trust, independence, or suitability for a particular claim.

## Usage rules

- Prefer **MNCS project family** or **MNCS ecosystem** for the collection of related repositories.
- Use **MNCS** only for the standard/authority layer when ambiguity would matter.
- Use **MNCDS** for the independently versioned development-process specification rather than treating it as a synonym for MNCS or as a subdirectory of MNCS.
- Distinguish **normative / specification authority** (MNCS, MNCDS) from **operator / development / research** components (Harness, Control, Fabric, Forge, Commons, Validator, Language, Reference Studies, RAVEL, MNEL, Atlas).
- Distinguish **deployment acceptance** from **MNCS conformance**.
- Distinguish a **service consumer** from the **lifecycle owner** of that service.
- Say **execution passed** when referring to execution checks; do not shorten that to **MNCS passed** unless formal MNCS validation is actually what occurred.
- Use **independent** only when the relevant evaluator, custody, and control requirements are actually independent.
- Treat **UNKNOWN** as an intentional result, not an error string to be optimized away.
- Prefer **reference deployment** or **operator stack** over laboratory or personal-lab language.
