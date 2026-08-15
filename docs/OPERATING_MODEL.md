# MNCS Operating Model

MNCS Atlas distinguishes the **project-family authority model** from the **operator runtime used to do work**. They overlap, but they are not the same diagram.

The authority model answers: *who is allowed to claim what?*

The operator model answers: *how does a human or agent currently get bounded work done across the MNCS family?*

This document is descriptive and non-normative. Deployment implementations may change faster than the standards. When this document disagrees with an owning repository's current contract, the owning repository wins and Atlas should be updated.

Harness, Control, Fabric, Forge, Commons, RAVEL, and MNEL are not mandatory for MNCS conformance.

## Current operator path

A representative reference deployment looks like:

```text
Human / external agent
                 |
                 v
          MNCS Control MCP
 constrains where remote/operator
 actions may occur
                 |
        +--------+---------+
        |                  |
        v                  v
   MNCS Harness         MNCS Forge
 routes, governs,       development workflows,
 approves, accepts      evidence, experiments, gaps
        |                  |
        +--------+---------+
                 |
                 v
            MNCS Fabric
 persistent distributed execution
 substrate + execution evidence
                 |
                 v
      workers / providers / models

                 Commons
  durable shared/institutional memory
        |
        v
   RAVEL / MNEL
 governed learning and experiment strategy

           validators / studies
  bounded evaluation, comparison, challenge
```

The drawing is representative, not a mandatory call graph. A client may use Forge without MNCS Harness, MNCS Harness may consume Fabric directly, and Control can expose bounded Fabric or Commons operations without owning those services.

## Component boundaries

| Component | Owns in the operator model | Explicitly does not own |
| --- | --- | --- |
| **Client** | User intent, requested task, approvals supplied through its UI | MNCS conformance, worker trust, result truth |
| **MNCS Control MCP** | Protected remote access to an authorized development workspace; filesystem, Git, process, project, and bounded MNCS integration surfaces | Fabric fleet lifecycle, Harness routing policy, Commons storage authority, MNCS conformance |
| **MNCS Harness** | Workspace meaning, model/tool routing, policy, approvals, agent loop, deployment-level result acceptance | Fabric transport/admission, Commons authority, MNCS normative status |
| **Forge** | Declared development/evidence workflows, provider orchestration, lineage, evidence gaps, evaluator-mode boundaries | Distributed fleet lifecycle, hidden promotion of evidence into conformance |
| **Fabric** | Worker identity/presence, exact-target admission, authenticated transport, bounded execution, retries, resource/capability observations, execution evidence | Semantic route selection, tool/model choice, calling-workflow result acceptance, MNCS conformance |
| **Worker / provider** | The bounded computation or observation it was asked to perform | Permission to broaden scope or promote its own result |
| **Commons** | Durable structured coordination, work records, observations, claims, replications, advisories, decisions, provenance-aware knowledge | Execution permission, automatic trust, consensus, conformance |
| **RAVEL / MNEL** | Strategy, experiments, causal interpretation, reusable governed learning | Redefining the status of evidence they consume |
| **Validators / Reference Studies** | Bounded validation or controlled empirical challenge within their declared protocol | Universal truth outside the supported claim/protocol |
| **MNCS** | Governing implementation-evidence / technical acceptance semantics | Operational ownership of every tool used to implement the standard; MNCDS process semantics |
| **MNCDS** | Independently versioned development-process semantics | Operational ownership of every tool used to implement the specification; MNCS evidence semantics |

## Why Control and MNCS Harness are separate

The reference operator stack uses two related but distinct operator surfaces.

**MNCS Control MCP** is the protected remote development boundary. It exposes an authorized workspace through a real sandbox and composes bounded adapters to MNCS services. It is primarily about *where a remote client may act and which development capabilities are exposed*.

**MNCS Harness** is reusable operator infrastructure for model-and-tool policy. It chooses or pins model routes, mediates tool requests, applies workspace/command policy, records model/tool metrics, and decides whether a deployment-level result is acceptable or should escalate. It is primarily about *how AI/model work is routed, governed, tool-enabled, approved, and accepted*. **Harness is not a normative MNCS requirement.**

Neither owns the persistent Fabric controller. In service mode both are Fabric consumers. Neither owns the persistent Commons service. They consume its public bounded interfaces according to their own permissions.

## Common workflows

### 1. Direct repository work

```text
client -> Control -> workspace files / Git / tests
```

Use this when the task is ordinary bounded development and does not require a local model or distributed worker. Control's sandbox and workspace policy are the principal execution boundary.

### 2. Model-assisted work

```text
client -> Control or MNCS Harness -> MNCS Harness -> model -> guarded tools -> verification
```

The model proposes actions. Harness policy and deterministic checks decide what can run and whether the result is accepted or escalated.

### 3. Exact-target distributed work

```text
client / Harness / Forge -> Fabric -> exact admitted worker -> execution evidence -> caller
```

The consumer chooses the intended target and declared work. Fabric rechecks the target, transports and executes the bounded workload, and records what happened. A successful Fabric execution is still not MNCS conformance.

### 4. Knowledge handoff

```text
client / Harness / Forge / investigator -> Commons -> later human or agent
```

Commons preserves a structured record with provenance and scope. Publication means the information is available, not accepted as true. Later replications, disputes, decisions, and supersession remain part of the record history.

### 5. Evidence-governed development

```text
request -> Forge -> providers / Fabric -> evidence -> validator / evaluator -> bounded result
```

Forge can coordinate declared checks and preserve lineage, but governing status comes only from the authority actually assigned to the validator/evaluator for that claim.

### 6. Learning from outcomes

```text
validated / scoped outcomes -> Commons and/or experiment records -> RAVEL / MNEL -> later strategy
```

Learning can change what the system investigates or tries next. It does not retroactively change FAIL, UNKNOWN, PASS, provenance, independence, or custody properties of the underlying evidence.

## Persistent-service ownership

The operator stack is intentionally moving away from short-lived clients secretly owning infrastructure lifecycles.

- **Fabric controller service owns Fabric state and worker presence.** Consumers connect to it; disconnecting a client does not imply a worker disappeared.
- **Commons service owns Commons persistence.** Consumers query or publish through bounded service interfaces rather than opening the store directly.
- **Control owns its own protected remote-control service state.** It does not copy Fabric worker registries or Commons storage state into its own authority domain.
- **MNCS Harness owns routing/policy state and model-facing behavior.** It consumes Fabric and Commons rather than becoming their service manager.

This split matters because persistence is not just an uptime feature. It determines which component is authoritative for identity, recovery, retries, history, and lifecycle.

## Reading failures correctly

A failure should be attributed to the layer that can actually establish it.

- **Control failure:** workspace, sandbox, tool, Git, process, tunnel, or adapter boundary failed.
- **Harness failure:** route, model availability, tool-policy loop, verification, or deployment acceptance failed.
- **Fabric failure:** target admission, transport, worker presence, bounded execution, retry/recovery, or Fabric-owned evidence failed.
- **Commons failure:** durable coordination/storage/query/sync contract failed.
- **Provider/verifier failure:** the requested bounded observation or check failed.
- **Validator result:** a supported claim evaluated to FAIL, UNKNOWN, or PASS under that validator's authority.

Do not repair one layer's failure by silently claiming success at another layer.

## Deployment visibility

Some operator implementations may be private, local-only, or specific to a reference deployment. Atlas documents their **family-level responsibility boundary** because that boundary matters to understanding the system, but it should not imply that every implementation repository is public or required for MNCS conformance.

MNCS Harness is reusable operator infrastructure published at https://github.com/epi13/mncs-harness. Its presence in the family map does not make it a normative MNCS requirement.

The public standards and project repositories remain the source of truth for their own contracts. Atlas is the map between them.
