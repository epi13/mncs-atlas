# MNCS Family Architecture

MNCS is an open experimental standard for accepting generated or machine-optimized implementations through bounded evidence. MNCDS is an independently versioned development-process specification. The wider project family explores languages, development control, distributed execution, coordination, adaptive learning, operator tooling, and empirical study while keeping those roles distinct.

Atlas is non-normative. Harness, Control, Fabric, Forge, Commons, RAVEL, MNEL, validators, language research, reference studies, and Atlas itself are not mandatory for MNCS conformance.

## Authority before topology

The most important family relationship is not which service calls which service; it is which component is allowed to claim what.

```text
NORMATIVE / SPECIFICATION AUTHORITY

MNCS                                          MNCDS
normative implementation-evidence             independently versioned
standard: contracts, evidence                 development-process
semantics, status, conformance                specification
                 \                           /
                  +-----------+-------------+
                              |
                              v
              independent/offline validators
              bounded validation of supported
              normative records

OPERATOR / DEVELOPMENT / RESEARCH

Human / external agent
        |
        v
MNCS Control MCP
constrains where remote/operator actions may occur
        |
        +----> MNCS Harness
        |      routes, governs, approves, and accepts AI/model work
        |
        +----> MNCS Forge
                    |
                    |  development workflows, evidence, experiments, gaps
                    v
                MNCS Fabric
                    |
                    |  persistent distributed execution substrate
                    v
          workers / providers / models

                     Commons
       durable shared/institutional memory

agents/models ----> RAVEL / MNEL
     |                  |
     |                  +---- strategy, experiments, learning, governed memory
     |
     +---- candidate generation, plans, repairs, explanations

                 Reference Studies
       controlled experiments across the family
```

The drawing is conceptual. Not every path is a direct runtime dependency. For the concrete deployment/operator path, see [OPERATING_MODEL.md](OPERATING_MODEL.md).

## Core boundaries

### MNCS and MNCDS

MNCS and MNCDS are sibling specifications with separate repositories, versioning, and governance.

- The `machine-native-complexity-standard` repository owns the normative implementation-evidence standard and governing claim boundaries. MNCS describes technical acceptance/evidence semantics.
- The `machine-native-complexity-development-specification` repository owns the independently versioned development-process specification. MNCDS describes how implementations are created, evaluated, selected, released, monitored, regenerated, replaced, and retired.

MNCDS may bind to MNCS results through explicit versioned contracts. Neither specification silently owns or rewrites the other. Neither Forge nor another tool is required for conformance unless a future normative specification says otherwise.

The implemented family record flow now runs: Control/Harness/Language/Fabric/Forge produce native evidence identities, a Concept Experiment envelope coordinates them, an MNCDS development record validates the resulting development process (experimental `0.2-alpha.1` producer-binding surface), and Commons preserves the validated record as a `DevelopmentRecord` projection keyed by the record's exact identity and digest. Each layer references lower-layer identities; no layer rewrites another's semantics. See [family-record-spine.md](family-record-spine.md).

### Operator control surfaces

Operator-specific control surfaces sit between external clients and project infrastructure. They are operator infrastructure, not a new normative layer.

The reference operator stack uses two distinct roles:

- **MNCS Control MCP** gets a human or external agent in and constrains where remote/operator actions may occur. It exposes a protected development workspace, Git/process/project operations, and bounded MNCS service adapters through a sandboxed remote-control boundary.
- **MNCS Harness** decides how AI/model work is routed, governed, tool-enabled, approved, and accepted. It owns workspace meaning, model/tool routing, approvals, agent behavior, deployment-level result acceptance, and escalation. It is reusable operator infrastructure, not a personal lab. **Harness is not a normative MNCS requirement.**

Both can consume persistent Fabric and Commons services. Neither owns MNCS conformance, Fabric fleet lifecycle, or Commons truth.

### Forge

Forge is a non-normative control plane for declared development and evidence workflows. It determines and evaluates development workflows, evidence, experiments, and gaps. It records lineage, declared checks, provider capabilities, evidence gaps, selection/freeze state, and evaluator-mode boundaries. It delegates normative decisions to validators rather than becoming one.

### Fabric

Fabric is an operator-controlled persistent execution and evidence substrate. It gets work executed through the persistent distributed execution substrate: worker identity and presence, exact-target admission, authenticated transport, bounded execution, retry identity/recovery, capability/resource observation, and execution records. It does not choose semantic routes, tools, models, or whether a result is acceptable to the calling workflow.

The persistent Fabric controller owns its service state and fleet lifecycle. Consumers such as Control, MNCS Harness, or Forge connect through the public consumer boundary rather than loading a private worker registry or trust material.

### Commons

Commons is a persistent coordination and knowledge plane. It provides durable shared/institutional memory: structured observations, claims, work requests, replications, advisories, decisions, and durable work history with provenance and evidence. Publication is not acceptance; new information remains untrusted by default.

The persistent Commons service owns its storage and lifecycle. Consumers use bounded service interfaces rather than treating the store itself as shared application state.

### RAVEL

RAVEL is an adaptive reasoning and evidence-orchestration layer. It chooses what to investigate next, records validated experience, and learns reusable strategies while preserving the governing status of the evidence it consumes. RAVEL memory is advisory.

### MNEL

Machine-Native Experimental Learning uses investigators, bounded interventions, deterministic tools/verifiers, causal attribution, and verified-experience distillation to explore learning from governed machine-readable experience. Investigators may propose knowledge; they may not declare it true.

### MNCS Language

The language project explores a general-purpose, verification-native language in which contracts, effects, capabilities, assumptions, evidence, failure semantics, resource bounds, and machine intent can be part of program meaning instead of reconstructed later.

### Reference Studies

Reference Studies supplies controlled empirical work: existing case studies, historical research studies, and reference reimplementation studies. It is where proposed benefits and costs are tested rather than assumed.

## Two diagrams are necessary

MNCS needs both an **authority diagram** and an **operator diagram**.

The authority diagram answers questions such as:

- who can issue a conformance result?
- what does a Fabric PASS actually mean?
- can a Commons record become trusted merely by being published?
- can a learned RAVEL strategy alter the status of old evidence?

The operator diagram answers different questions:

- how does a remote client reach an authorized workspace?
- where is model/tool policy applied?
- which service persists worker identity and detached execution?
- which service persists shared knowledge and durable work?
- where should a failure be attributed?

Collapsing those diagrams creates exactly the ambiguity Atlas is meant to prevent.

## Common end-to-end pattern

A representative workflow can look like:

```text
human / external agent request
        |
        v
MNCS Control MCP constrains where remote/operator actions may occur
        |
        +----> MNCS Harness routes, governs, approves, and accepts AI/model work
        |
        +----> MNCS Forge determines/evaluates development workflows and evidence
                    |
                    v
                MNCS Fabric executes on an exact admitted target
                    |
                    v
          workers / providers / models emit observations
        |
        v
calling workflow records evidence, lineage, and status
        |
        +--> Commons remembers durable shared/institutional knowledge or work state
        |
        +--> RAVEL / MNEL use governed outcomes for later strategy or experiments
        |
        +--> Reference Studies compare behavior under a frozen protocol
        v
MNCS or MNCDS validators evaluate only the claims they are authorized to evaluate
```

A successful step does not automatically promote the next layer. Execution success is not verifier success; verifier success is not independent evaluation; development evidence is not protected custody; publication is not acceptance; and a learned strategy is not a normative rule.

## Persistent-service ownership

A long-lived system must make lifecycle ownership explicit.

- Fabric owns persistent fleet/session/execution state.
- Commons owns persistent coordination/knowledge state.
- Control owns its protected remote-control service state.
- MNCS Harness owns routing, policy, model-loop, and deployment acceptance state.
- Forge owns its declared workflow/evidence-control state.

A consumer disconnecting must not silently rewrite the lifecycle of a service it does not own.

## Design rule for cross-project changes

When a feature spans repositories, define the authority boundary first, then the lifecycle owner, then the transport/interface. Prefer versioned public records and adapters over importing sibling internals. Preserve identity, provenance, scope, freshness, and explicit unsupported/unknown states at each boundary.
