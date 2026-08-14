# MNCS Project Directory

This directory is intentionally concise. Follow each repository's README for current implementation details.

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

A persistent operator-controlled execution and evidence fabric. Fabric handles identified workers, authenticated transport, exact-target admission, bounded execution, resource/capability observations, retries, and durable execution evidence. It does not choose tools, models, semantic routes, or result acceptance.

### Local harness and operator control surfaces

MNCS deployments may use operator-specific local harnesses and remote control surfaces. These own model routing, workspace policy, approvals, and acceptance while consuming Fabric's persistent service. They are deployment infrastructure rather than sources of MNCS authority.

## Coordination and learning

### MNCS Commons

Repository: https://github.com/epi13/MNCS-Commons

A structured coordination and knowledge-exchange layer for agents and humans. Commons records observations, claims, work requests, replications, advisories, and decisions with provenance and evidence. Contributions remain untrusted by default.

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

This repository. Atlas owns no technical conformance authority. Its job is to maintain a coherent family map, common terminology, contributor orientation, and links into authoritative project documentation.

## Adding a project

A project belongs in this directory when it has a meaningful family-level role rather than merely using MNCS internally. Add it with:

1. its public repository or canonical home;
2. one paragraph describing what it owns;
3. one sentence describing what it explicitly does **not** own when that boundary matters;
4. corresponding terminology/architecture updates if the family model changes.
