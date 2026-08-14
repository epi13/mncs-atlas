# MNCS Atlas Agent Orientation

This file is the family-level starting point for coding and research agents working from MNCS Atlas.

## First principle

Do not infer family architecture from repository names alone. Establish the owning project's documented authority boundary before changing cross-project behavior.

## Orientation sequence

1. Read this file.
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
3. Read [docs/PROJECTS.md](docs/PROJECTS.md) and identify the repository that owns the requested behavior.
4. Read that repository's current README and relevant architecture/specification documents.
5. If the change crosses a boundary, read the adjacent project's public contract before modifying either side.
6. Preserve evidence and authority semantics in code, documentation, tests, and prompts.

For automated discovery, [site/atlas.json](site/atlas.json) provides a compact machine-readable family map. It is orientation-only and never outranks the owning project's current documentation or specifications.

## Family-wide invariants

- **MNCS defines technical acceptance/conformance semantics.** MNCDS separately governs the development process.
- **No tool promotes itself.** A generator, agent, Forge workflow, Fabric execution, RAVEL policy, MNEL investigator, or Commons record cannot silently turn its own output into governing truth.
- **`FAIL > UNKNOWN > PASS`.** Missing, stale, unsupported, unavailable, or insufficient evidence must not be reported as `PASS`.
- **Execution is not conformance.** Successfully running a bounded workload proves only the claims established by that execution record.
- **Transport is not trust.** Moving authenticated data or work between machines does not create independent evaluation, protected custody, or correctness.
- **Coordination is not command authority.** Commons records are structured knowledge/work opportunities, not an unrestricted instruction channel.
- **Learning is advisory until governed.** RAVEL and MNEL may propose, prioritize, retain, and distill experience; they do not redefine the status of underlying evidence.
- **Human readability is relocated, not eliminated.** Machine-oriented representation still requires inspectable contracts, provenance, scope, and evidence boundaries.

## Responsibility shorthand

- **MNCS / MNCDS:** authority, standards, evidence/status semantics, development governance.
- **MNCS Language:** verification-native language and semantic representation research.
- **Forge:** bounded development/evidence control plane and provider orchestration.
- **Fabric:** persistent exact-target execution, transport, resource/capability observation, and execution evidence.
- **Local harnesses:** model routing, tool choice, workspace policy, approvals, and result acceptance for a deployment.
- **Commons:** shared coordination and structured knowledge exchange.
- **RAVEL:** adaptive evidence strategy, memory, and learning beneath governing authority.
- **MNEL:** evidence-governed experimental learning and causal experience distillation.
- **Reference Studies:** controlled empirical studies and reimplementations.
- **Rust validator:** independent offline cross-implementation validation for supported MNCS subsets.
- **Atlas:** orientation only.

## When documentation conflicts

Use this precedence for implementation questions:

1. current normative specification or accepted project contract;
2. owning repository's current architecture/docs and tests;
3. owning repository README;
4. Atlas family-level summary.

Do not repair a disagreement by silently changing normative meaning. Surface the mismatch explicitly.

## Working style for agents

Prefer narrow, evidence-backed changes. Preserve provenance. Reuse public interfaces rather than reaching into sibling internals. Do not add hidden fallback behavior across machines, models, evaluators, or trust boundaries. When evidence is absent, report the gap.

When changing the Atlas website, edit only the canonical `site/` tree, run `python scripts/sync_pages_root.py`, and let CI verify that the root GitHub Pages compatibility mirror remains byte-for-byte current.
