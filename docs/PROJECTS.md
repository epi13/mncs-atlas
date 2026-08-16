# MNCS Project Directory

This directory is intentionally concise. Follow each repository's README for current implementation details. Atlas distinguishes **normative specification authority**, **incubating institutional specifications**, and **operator / development / research components** so family membership is not confused with conformance authority or runtime dependency.

Maturity is descriptive, not ranked. See [MATURITY.md](MATURITY.md).

## Normative / specification authority

### Machine-Native Complexity Standard

Repository: https://github.com/epi13/machine-native-complexity-standard

MNCS is the normative implementation-evidence standard. It owns technical acceptance, evidence and status semantics, claim boundaries, RFC work, schemas, examples, and release-candidate standards work.

MNCS does **not** own the independently versioned MNCDS development-process specification.

### Machine-Native Complexity Development Specification

Repository: https://github.com/epi13/machine-native-complexity-development-specification

MNCDS is the independently versioned development-process specification. It governs decomposition, candidate lifecycle, evidence flow, selection, release, monitoring, regeneration, replacement, and related development controls.

MNCDS may bind to MNCS results through explicit versioned contracts. It does **not** share or rewrite MNCS normative meaning.

## Incubating institutional specifications

### MNCS Rights & Provenance

Repository: https://github.com/epi13/mncs-rights-provenance

Maturity: **Incubating**.

MNCS Rights & Provenance develops machine-native vocabulary, schemas, evidence models, and reference validation for artifact origin, transformation lineage, contribution provenance, authorship uncertainty, rights basis, artifact licensing, and release-facing rights evidence.

It is an official MNCS family project because those questions cross source code, Fabric receipts, Commons knowledge, Forge lineage, experiment artifacts, model outputs, future training corpora, and releases. Its current role is to **observe, model, experiment, and learn** from real MNCS workflows.

It is deliberately not yet a new software license, does not replace Apache-2.0, does not determine copyrightability automatically, and is not a hard runtime dependency for Fabric, Forge, Commons, MNEL, MNCS, or MNCDS. Future adoption by governing specifications must be explicit and versioned.

Core boundary: **provenance is evidence about origin and transformation; it is not by itself a conclusion about authorship, ownership, or copyrightability.**

## Operator / development / research

The following components are part of the project family or reference operator stack. None of them is a source of MNCS or MNCDS conformance authority, and none is mandatory for MNCS conformance.

### MNCS Language

Repository: https://github.com/epi13/mncs-language

Research and reference implementation for a general-purpose verification-native programming language built around MNCS principles. It explores canonical semantics, contracts, effects, capabilities, assumptions, evidence, IR/SSA, and machine-intent-aware transformations.

### Independent Rust Validator

Repository: https://github.com/epi13/mncs-validator-rs

An independent offline Rust validator for supported MNCS subsets. It is intentionally separate from the Python validator and does not execute evidence binaries.

### MNCS Forge MCP

Repository: https://github.com/epi13/mncs-forge-mcp

A non-normative MCP/CLI development and evidence control plane. Forge determines and evaluates declared development workflows, evidence, experiments, and gaps. It records candidate/evidence lineage, exposes bounded micro-verifiers, and preserves evaluator-mode boundaries while delegating normative decisions to MNCS and MNCDS validators.

### MNCS Fabric

Repository: https://github.com/epi13/mncs-fabric

A persistent operator-controlled execution and evidence fabric. Fabric gets work executed through the persistent distributed execution substrate: identified workers, authenticated transport, exact-target admission, bounded execution, resource/capability observations, retries, durable detached execution, and execution evidence. It does not choose tools, models, semantic routes, or result acceptance.

## Operator implementations

The reference operator stack has concrete operator components that matter to understanding the running system but are **operator infrastructure rather than sources of MNCS authority**. Some implementation repositories may be private or environment-specific. Atlas documents the responsibility boundary, not an access promise.

### MNCS Control MCP

Current role: protected remote development control surface.

MNCS Control MCP gets a human or external agent in and constrains where remote/operator actions may occur. It exposes an authorized development workspace, Git, processes, project operations, tools, and bounded MNCS adapters through a fail-closed sandboxed boundary. It can consume MNCS Harness, Fabric, Forge, and Commons interfaces without taking ownership of their service lifecycles or authority domains.

It does **not** own Fabric worker presence or trust material, MNCS Harness routing policy, Commons persistence, or MNCS conformance.

See [OPERATING_MODEL.md](OPERATING_MODEL.md).

### MNCS Harness

Repository: https://github.com/epi13/mncs-harness

Current role: reusable operator infrastructure for model/tool policy and deployment-level result acceptance.

MNCS Harness decides how AI/model work is routed, governed, tool-enabled, approved, and accepted. It owns workspace meaning, model and tool routing, guarded agent/tool loops, approvals, deterministic verification/escalation, metrics, and deployment-level result acceptance. In the intended persistent-service deployment it consumes Fabric and Commons rather than starting or owning those services.

It does **not** own Fabric exact-target admission/transport, Commons truth or command authority, or MNCS normative status. **Harness is not a normative MNCS requirement.**

See [OPERATING_MODEL.md](OPERATING_MODEL.md).

## Coordination and learning

### MNCS Commons

Repository: https://github.com/epi13/MNCS-Commons

A persistent structured coordination and knowledge-exchange layer for agents and humans. Commons provides durable shared/institutional memory: observations, claims, work requests, replications, advisories, decisions, and durable work history with provenance and evidence. Contributions remain untrusted by default and Commons never turns publication into execution permission.

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

This repository. Atlas owns no technical conformance authority. Its job is to maintain a coherent family map, common terminology, maturity vocabulary, contributor orientation, the current operator-model boundary, and machine-readable relationships/entry points.

## Choosing where to start

| If you want to… | Start with… |
| --- | --- |
| understand evidence/status semantics or conformance | MNCS |
| understand development-process governance or candidate lifecycle | MNCDS |
| understand artifact provenance, rights basis, or authorship uncertainty | MNCS Rights & Provenance |
| author or run declared development/evidence workflows | Forge |
| route model and guarded tool work | MNCS Harness |
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
3. an explicit maturity value and authority class;
4. one sentence describing what it explicitly does **not** own when that boundary matters;
5. a visibility/deployment note when the implementation is private, local-only, or operator-specific;
6. explicit `atlas.json` relationship records for material cross-project boundaries;
7. corresponding terminology/architecture/machine-map updates if the family model changes.
