# MNCS Family Architecture

MNCS is an open experimental standard for accepting generated or machine-optimized implementations through bounded evidence. MNCDS is a separate development-process specification. The wider project family explores languages, development control, distributed execution, coordination, adaptive learning, and empirical study while keeping those roles distinct.

## Authority before topology

The most important family relationship is not which service calls which service; it is which component is allowed to claim what.

```text
MNCS
technical authority, contracts, evidence semantics, status, conformance
  |
  +--> MNCDS
  |    development process, candidate lifecycle, evidence flow, governance
  |
  +--> independent/offline validators
       bounded validation of supported normative records

Beneath that authority:

agents/models ----> RAVEL / MNEL ----> Forge ----> providers/verifiers
     |                  |                |
     |                  |                +---- bounded development/evidence workflows
     |                  +---- strategy, experiments, learning, governed memory
     |
     +---- candidate generation, plans, repairs, explanations

                     Fabric
        persistent exact-target execution and evidence substrate
                    /      \
             controllers   workers

                     Commons
       structured coordination and knowledge exchange

                 Reference Studies
       controlled experiments across the family
```

The drawing is conceptual. Not every path is a direct runtime dependency.

## Core boundaries

### MNCS and MNCDS

The `machine-native-complexity-standard` repository owns the standards work and governing claim boundaries. MNCS describes technical acceptance/evidence semantics. MNCDS separately describes development-process structure. Neither Forge nor another tool is required for conformance unless a future normative specification says otherwise.

### Forge

Forge is a non-normative control plane for declared development and evidence workflows. It records lineage, declared checks, provider capabilities, evidence gaps, selection/freeze state, and evaluator-mode boundaries. It delegates normative decisions to validators rather than becoming one.

### Fabric

Fabric is an operator-controlled persistent execution and evidence substrate. It owns exact-target admission, authenticated transport, bounded execution, retries/identity, capability/resource observation, and execution records. It does not choose semantic routes, tools, models, or whether a result is acceptable to the calling workflow.

### Local harnesses and control surfaces

Deployment-specific harnesses own model routing, workspace meaning, tool choice, permissions, approvals, and result acceptance. In persistent service mode they consume Fabric rather than owning Fabric's lifecycle. Operator control surfaces may expose these capabilities to remote clients without changing the underlying authority split.

### Commons

Commons is a coordination plane. It stores structured observations, claims, work requests, replications, advisories, and decisions with provenance and evidence. Publication is not acceptance; new information remains untrusted by default.

### RAVEL

RAVEL is an adaptive reasoning and evidence-orchestration layer. It chooses what to investigate next, records validated experience, and learns reusable strategies while preserving the governing status of the evidence it consumes. RAVEL memory is advisory.

### MNEL

Machine-Native Experimental Learning uses investigators, bounded interventions, deterministic tools/verifiers, causal attribution, and verified-experience distillation to explore learning from governed machine-readable experience. Investigators may propose knowledge; they may not declare it true.

### MNCS Language

The language project explores a general-purpose, verification-native language in which contracts, effects, capabilities, assumptions, evidence, failure semantics, resource bounds, and machine intent can be part of program meaning instead of reconstructed later.

### Reference Studies

Reference Studies supplies controlled empirical work: existing case studies, historical research studies, and reference reimplementation studies. It is where proposed benefits and costs are tested rather than assumed.

## Common end-to-end pattern

A representative workflow can look like:

```text
human / agent request
        |
        v
local harness or Forge decides a bounded action
        |
        v
Fabric executes on an exact admitted target
        |
        v
provider / compiler / verifier emits observations
        |
        v
Forge or evaluator records evidence and status
        |
        +--> Commons publishes reusable scoped knowledge
        |
        +--> RAVEL / MNEL use governed outcomes for later strategy or experiments
        |
        +--> Reference Studies compare behavior under a frozen protocol
        v
MNCS / MNCDS validators evaluate only the claims they are authorized to evaluate
```

A successful step does not automatically promote the next layer. Execution success is not verifier success; verifier success is not independent evaluation; development evidence is not protected custody; and a learned strategy is not a normative rule.

## Design rule for cross-project changes

When a feature spans repositories, define the authority boundary first, then the transport/interface. Prefer versioned public records and adapters over importing sibling internals. Preserve identity, provenance, scope, freshness, and explicit unsupported/unknown states at each boundary.
