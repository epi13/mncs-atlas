# MNCS Atlas Agent Orientation

This file is the family-level starting point for coding and research agents working from MNCS Atlas.

## First principle

Do not infer family architecture from repository names alone. Establish the owning project's documented authority boundary **and lifecycle owner** before changing cross-project behavior.

## Orientation sequence

1. Read this file.
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) to establish family authority boundaries.
3. If the task touches a running deployment, service ownership, model routing, remote control, Harness, Fabric, or Commons, read [docs/OPERATING_MODEL.md](docs/OPERATING_MODEL.md).
4. Read [docs/PROJECTS.md](docs/PROJECTS.md) and identify the repository or deployment component that owns the requested behavior.
5. Read that owning project's current README and relevant architecture/specification documents.
6. If the change crosses a boundary, read the adjacent project's public contract before modifying either side.
7. Preserve evidence, lifecycle, and authority semantics in code, documentation, tests, and prompts.

For automated discovery, [site/atlas.json](site/atlas.json) provides a compact machine-readable family map with stable component IDs, operator components, relationships, and task entry points. Its schema is [site/schema/atlas.schema.json](site/schema/atlas.schema.json). Both are orientation-only and never outrank the owning project's current documentation or specifications.

## Family-wide invariants

- **MNCS defines technical acceptance/conformance semantics.** MNCDS is an independently versioned specification that separately governs the development process.
- **No tool promotes itself.** A generator, agent, Forge workflow, Fabric execution, RAVEL policy, MNEL investigator, Commons record, Control action, or Harness result cannot silently turn its own output into governing truth.
- **`FAIL > UNKNOWN > PASS`.** Missing, stale, unsupported, unavailable, or insufficient evidence must not be reported as `PASS`.
- **Execution is not conformance.** Successfully running a bounded workload proves only the claims established by that execution record.
- **Transport is not trust.** Moving authenticated data or work between machines does not create independent evaluation, protected custody, or correctness.
- **Coordination is not command authority.** Commons records are structured knowledge/work opportunities and durable coordination state, not an unrestricted instruction channel.
- **Learning is advisory until governed.** RAVEL and MNEL may propose, prioritize, retain, and distill experience; they do not redefine the status of underlying evidence.
- **Persistence implies ownership.** A long-lived service owns the identity, lifecycle, recovery, and history it explicitly declares. Consumers must not recreate a shadow authority merely because they can observe or call that service.
- **Human readability is relocated, not eliminated.** Machine-oriented representation still requires inspectable contracts, provenance, scope, and evidence boundaries.

## Responsibility shorthand

### Normative / specification authority

- **MNCS:** normative implementation-evidence standard; technical acceptance, evidence/status semantics, and claim boundaries. Repository: https://github.com/epi13/machine-native-complexity-standard
- **MNCDS:** independently versioned development-process specification; candidate lifecycle, evidence flow, and development governance. Repository: https://github.com/epi13/machine-native-complexity-development-specification

### Operator / development / research

- **MNCS Harness:** reusable operator infrastructure for model/tool routing, workspace policy, approvals, agent loops, verification/escalation, and deployment-level result acceptance. It consumes Fabric and Commons rather than owning their persistence. **Not a normative MNCS requirement.**
- **MNCS Control MCP:** protected remote workspace, Git/process/project/tool surface, and bounded adapters to MNCS services. It is a consumer of Fabric/Commons service contracts, not their lifecycle owner.
- **Forge:** bounded development/evidence control plane and provider orchestration.
- **Fabric:** persistent exact-target execution, worker presence, transport, resource/capability observation, retry/recovery, and execution evidence.
- **Commons:** durable shared/institutional memory; persistent structured coordination, knowledge exchange, and durable work history.
- **Rust validator:** independent offline cross-implementation validation for supported MNCS subsets.
- **MNCS Language:** verification-native language and semantic representation research.
- **Reference Studies:** controlled empirical studies and reimplementations.
- **RAVEL:** adaptive evidence strategy, memory, and learning beneath governing authority.
- **MNEL:** evidence-governed experimental learning and causal experience distillation.
- **Atlas:** orientation only.

None of the operator, development, or research components is mandatory for MNCS conformance. Operator implementations may be private, local-only, or deployment-specific. Their presence in Atlas does not make them normative MNCS requirements.

## Before changing a cross-project integration

Answer these questions explicitly:

1. **Who owns the semantic decision?** For example, Harness may choose a model while Fabric must not.
2. **Who owns lifecycle and persistence?** For example, the persistent Fabric controller owns worker presence; a client disconnect must not rewrite that fact.
3. **Who owns transport/execution?** Do not duplicate Fabric behavior in Control or Harness merely because they need execution.
4. **Who owns storage/history?** Do not bypass Commons service boundaries by opening its store from a consumer.
5. **What is the public record/interface?** Prefer versioned contracts, sockets, envelopes, schemas, or adapters over sibling internals.
6. **What remains UNKNOWN?** Do not fill unsupported capabilities with fallback claims.
7. **What does success actually prove?** A tool return, Fabric PASS, Commons ingestion, or Forge workflow completion each establishes a different bounded fact.

## When documentation conflicts

Use this precedence for implementation questions:

1. current normative specification or accepted project contract;
2. owning repository's current architecture/docs and tests;
3. owning repository README;
4. Atlas family-level summary.

For deployment-specific behavior, the current owning deployment repository outranks Atlas's operating-model description.

Do not repair a disagreement by silently changing normative meaning. Surface the mismatch explicitly.

## Working style for agents

Prefer narrow, evidence-backed changes. Preserve provenance. Reuse public interfaces rather than reaching into sibling internals. Do not add hidden fallback behavior across machines, models, evaluators, or trust boundaries. When evidence is absent, report the gap.

When changing the Atlas website, edit only the canonical `site/` tree, run `python scripts/sync_pages_root.py`, and let CI verify that the root GitHub Pages compatibility mirror remains byte-for-byte current. When changing `site/atlas.json`, keep stable IDs when possible, update its schema/relationships/entry points as needed, and verify every referenced component exists.
