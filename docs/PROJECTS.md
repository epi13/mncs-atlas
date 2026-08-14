# MNCS Project Directory

This directory is intentionally concise. Follow each repository's README for current implementation details. Atlas distinguishes **public family projects** from **deployment/operator implementations** so a private or local control surface is not mistaken for a normative requirement.

## Standards and semantics

### Machine-Native Complexity Standard

Repository: https://github.com/epi13/machine-native-complexity-standard

The standards repository for MNCS and the separate MNCDS development-process specification. It owns the primary technical authority, evidence/status semantics, claim boundaries, RFC work, schemas, examples, and release-candidate standards work.

### MNCS Language

Repository: https://github.com/epi13/mncs-language

Research and reference implementation for a general-purpose verification-native programming language built around MNCS principles. It explores canonical semantics, contracts, effects, capabilities, assumptions, evidence, IR/SSA, and machine-intent-aware transformations.

### Independent Rust Validator

Repository: https://github.com/epi13/mncs-validator-rs

An independent offline Rust validator for supported MNCS subsets. It is intentionally separate from the Python validator and does not execute evidence binaries.

## Development and execution infrastructure

### MNCS Forge MCP

Repository: https://github.com/epi13/mncs-forge-mcp

A non-normative MCP/CLI development and evidence control plane. Forge runs declared provider workflows, records candidate/evidence lineage, exposes bounded micro-verifiers, and preserves evaluator-mode boundaries while delegating normative decisions to MNCS/MNCDS validators.

### MNCS Fabric

Repository: https://github.com/epi13/mncs-fabric

A persistent operator-controlled execution and evidence fabric. Fabric handles identified workers, authenticated transport, exact-target admission, bounded execution, resource/capability observations, retries, durable detached execution, and execution evidence. It does not choose tools, models, semantic routes, or result acceptance.

## Operator implementations

The current laboratory has concrete operator components that matter to understanding the running system but are **deployment infrastructure rather than sources of MNCS authority**. Their implementation repositories may be private or environment-specific. Atlas documents the responsibility boundary, not an access promise.

### MNCS Control MCP

Current role: protected remote development control surface.

MNCS Control MCP exposes an authorized development workspace, Git, processes, project operations, tools, and bounded MNCS adapters through a fail-closed sandboxed boundary. It can consume Local Harness, Fabric, Forge, and Commons interfaces without taking ownership of their service lifecycles or authority domains.

It does **not** own Fabric worker presence or trust material, Local Harness routing policy, Commons persistence, or MNCS conformance.

See [OPERATING_MODEL.md](OPERATING_MODEL.md).

### Local Harness

Current role: model/tool policy and deployment-level result acceptance.

Local Harness owns workspace meaning, model and tool routing, guarded agent/tool loops, approvals, deterministic verification/escalation, metrics, and deployment-level result acceptance. In the intended persistent-service deployment it consumes Fabric and Commons rather than starting or owning those services.

It does **not** own Fabric exact-target admission/transport, Commons truth or command authority, or MNCS normative status.

See [OPERATING_MODEL.md](OPERATING_MODEL.md).

## Coordination and learning

### MNCS Commons

Repository: https://github.com/epi13/MNCS-Commons

A persistent structured coordination and knowledge-exchange layer for agents and humans. Commons records observations, claims, work requests, replications, advisories, decisions, and durable work history with provenance and evidence. Contributions remain untrusted by default and Commons never turns publication into execution permission.

### RAVEL

Repository: https://github.com/epi13/RAVEL

Recursive Adaptive Vector Execution Lattice: an adaptive intelligence layer for deciding which evidence to gather, what action to take next, and which validated experience to retain. RAVEL operates beneath MNCS/MNCDS authority and cannot promote its own memories into governing truth.

### Machine-Native Experimental Learning

Repository: https://github.com/epi13/Machine-Native-Experimental-Learning

An evidence-governed experimental learning framework. MNEL uses investigators, bounded experiments, causal attribution, negative memory, and verified-experience distillation to explore learning from persistent machine-readable experience.

## Empirical validation

### MNCS Reference Studies

Repository: https://github.com/epi13/mncs-reference-studies

The empirical companion to the standards work. It contains controlled case studies, historical research studies, and reference reimplementations designed to test behavioral correctness, performance, resource bounds, verifier coverage, agent modification outcomes, and other claims without collapsing them into a universal score.

## Orientation

### MNCS Atlas

Repository: https://github.com/epi13/mncs-atlas

This repository. Atlas owns no technical conformance authority. Its job is to maintain a coherent family map, common terminology, contributor orientation, the current operator-model boundary, and links into authoritative project documentation.

## Choosing where to start

| If you want to… | Start with… |
| --- | --- |
| understand evidence/status semantics or conformance | MNCS / MNCDS |
| author or run declared development/evidence workflows | Forge |
| route local-model and guarded tool work | Local Harness |
| operate the authorized development workspace remotely | MNCS Control MCP |
| execute on an exact persistent worker | Fabric |
| share findings, requests, replications, or decisions | Commons |
| learn from governed experience | RAVEL / MNEL |
| challenge claims empirically | Reference Studies |
| independently validate a supported record subset | Rust Validator + governing MNCS docs |
| understand how the family fits together | Atlas |

## Adding a project

A project belongs in this directory when it has a meaningful family-level role rather than merely using MNCS internally. Add it with:

1. its public repository or canonical home when one is available;
2. one paragraph describing what it owns;
3. one sentence describing what it explicitly does **not** own when that boundary matters;
4. a visibility/deployment note when the implementation is private, local-only, or operator-specific;
5. corresponding terminology/architecture/machine-map updates if the family model changes.
