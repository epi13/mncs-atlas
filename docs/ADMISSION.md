# Atlas Admission and Capability Brokerage

Atlas is the front door of the MNCS ecosystem. It grants **entry, context,
discovery, and access to capability requests**. It does not grant trust
merely by identity, and it must not duplicate the authoritative policy logic
owned by other MNCS components.

> A participant appearing in Atlas means MNCS knows about this participant.
> It must not automatically mean MNCS trusts this participant.

## The rule

```text
Human / Agent
     |
     v
   ATLAS  (admission, orientation, discovery, routing)
     |
     v
MNCS subsystem authorities  (decisions, validation, evidence, execution)
     |
     v
permitted effects
```

Atlas **queries, composes, and routes** authoritative results. A capability
decision always names the owning subsystem in `authority` / `decision_by`.
The only capabilities Atlas itself owns are `orientation.read` and
`ecosystem.inspect` (orientation data is its chartered role).

## Discovery documents

Agents discover the environment through two machine-readable documents:

- `site/atlas.json` — family map: components, relationships, entry points,
  maturity, authority classes, and an `admission` pointer
  (`document`/`version`/`authority`).
- `site/admission.json` — generated capability map: admission states,
  the capability catalog with owners and sensitivity, rights-scope bindings,
  and lifecycle gates. Canonical source is `admission/vocabulary.py`;
  regenerate with `python scripts/sync_admission.py` (CI enforces
  `--check`).

The full capability catalog lives beside the core map rather than inside
it: the experimental compiled atlas-model projection has a fixed input
envelope, and stuffing the whole catalog into `atlas.json` exceeds it (see
"Language pressure" below). The pointer keeps discovery one hop away while
the projection stays green.

## Participant lifecycle

```text
OUTSIDE -> KNOWN -> ADMITTED -> SCOPED -> CONFORMANT_FOR_CAPABILITY
```

- `OUTSIDE`: unknown to MNCS.
- `KNOWN`: identified (identity, type, provenance). Knowledge, not trust.
- `ADMITTED`: accepted orientation context (Atlas version, policy versions).
- `SCOPED`: bound to an explicit scope, repository context, and purpose.
- `CONFORMANT_FOR_CAPABILITY`: per-capability evidence satisfied. This is a
  per-capability record, never a global flag.

There is deliberately **no universal `trusted` boolean**. An agent may hold
`repo.read`, `repo.edit`, `tests.execute`, and `change.propose` while still
being unable to `change.merge`, `release.publish`, `validator.modify`, or
`policy.modify`. The `Session` model (`admission/model.py`) enforces legal
transitions and rejects skipped states.

## Capability model

Capabilities (`admission/vocabulary.py`) carry: owner subsystem, Atlas
component id, sensitivity (`open` < `scoped` < `protected` < `governance`),
scope kind, default posture (`grantable` / `conditional` / `denied`),
granting admission state, required evidence, and a conformant path.

Routing (`admission/router.py`) composes one adapter per owning subsystem:

| Adapter | Speaks for | Decides |
|---|---|---|
| `AdmissionPostureAdapter` | atlas | what admission state alone establishes (never conditional/governance grants) |
| `RightsAdapter` | rights-provenance | scope attachment (`may_*`), provenance completeness, independent confirmations |
| `LifecycleAdapter` | MNCDS | proposal is never promotion; merge needs confirmation+ |
| `ForgeAdapter` | forge | policy evaluation, self-validation refusal |
| `CommonsAdapter` | commons | independent-confirmation accounting (never manufactured) |
| `FabricAdapter` | fabric | execution targets, declared network use, placement bounds |
| `ActionsAdapter` | mncs-actions | declared action required for consequential effects |

Findings combine with the family lattice `FAIL > UNKNOWN > PASS`
(`INVALID` for malformed queries). Verdict `PASS` everywhere yields
`granted`; any `UNKNOWN` yields `conditional` with `missing` evidence; any
`FAIL` yields `denied`.

Live subsystem services can replace any bundled adapter behind the same
`AuthorityAdapter.evaluate` interface without changing the decision shape.

## Denials teach

Every denial (`admission/denials.py`, `ACTION_DENIED`) names the request,
the reason, the owning authority, missing evidence, and the conformant
path. Example:

```text
ACTION_DENIED
requested: direct protected-state mutation
reason: capability not granted (actions.conformant, provenance.complete,
         tests.passed and 2 independent confirmations missing)
authority: rights-provenance (decided with mncds, mncs-actions, commons)
conformant_path: change.propose -> validate -> provide evidence -> promotion
```

## Separation of duties (structural)

Governance capabilities (`validator.modify`, `policy.modify`,
`capability.grant`) require two independent confirmations **distinct from
both the requestor and the proposer**. Self-attestation never counts. A
change cannot validate itself (`validating_change_id == change_id` is
refused for validator/policy/merge decisions). `capability.grant` is never
granted by admission state at all; it routes to rights-provenance for an
explicit scoped grant.

## Bypass observation

`admission/bypass.py` scans operation events for bypass patterns (direct
protected mutation, self-validation, provenance stripping, fabricated
evidence digests, undeclared cross-repo mutation, undeclared network use,
unauthorized worker dispatch, CI/conformance disabling, promotion outside
lifecycle). Findings are observations with conformant routes, not
enforcement verdicts; many bypasses are development pressure, so each
finding says how to comply.

## Orientation (one state, two views)

`admission/orientation.py` answers, as data, `where_am_i`,
`what_exists`, `what_is_my_goal`, `what_can_i_read`, `what_can_i_do`,
`what_can_i_not_do`, `why_is_it_denied`,
`what_conformant_path_exists`, `what_evidence_is_required`, and
`who_has_authority`. `human_orientation` renders the same state as prose;
the two views cannot drift because they share the computation. Reading the
map grants no authority: orientation is re-evaluated per query and denied
capabilities stay denied no matter how well the participant understands
them.

## Authority ownership map

```text
concept                  authoritative repo / subsystem
family orientation       mncs-atlas (descriptive only)
participant context      mncs-atlas (session record, not a trust verdict)
capability vocabulary    mncs-atlas (orientation data; owners decide)
rights / promotion       mncs-rights-provenance (may_* scopes)
action conformance       mncs-actions (declared intent -> effect)
lifecycle state          MNCDS (proposal..release; forge projects it)
policy / security        forge (evaluations, separation of duties)
execution / placement    fabric (targets, capability observation)
evidence / confirmation  commons (traces, lifecycle projection)
promotion / governance   MNCS + MNCDS (normative boundary)
```

## Language pressure

Proven gaps discovered by this work (evidence, not complaints):

1. **Fixed-envelope compiled projection.** The experimental `atlas-model`
   WASM projection (built from `mncs/atlas-model.mncs` with the locked
   language revision) traps with `memory access out of bounds` once the
   scanned document carries roughly ~730 or more additional string bytes
   under keys outside its fixed world-schema — regardless of key names,
   nesting depth, chunking, or document position. Repro: feed any
   `site/atlas.json` plus ~800 bytes of extra string content through
   `atlas_model_init/chunk/render` (see `tests/test_experimental_wasm.py`).
   The structural scanner (`atlas-json-scan`) handles the same bytes fine,
   and every model-level index is guarded, which points below the model
   source at backend bounds handling at scale. Response in this pass: the
   capability catalog moved to `site/admission.json` behind a pointer, and
   `mncs/admission-model.mncs` expresses the admission shapes for future
   model coverage. A model that can project admission explicitly (bounded
   capability arrays, pointer-aware discovery) is the next language/model
   pass.
2. **Conditional authority is not yet expressible.** MNCS 0.10 expresses
   the admission *shapes* (records, bounded arrays, byte-coded states) but
   has no clean encoding for conditional grants with expiry, dynamic
   authority dispatch, or open-ended evidence sets. The Python admission
   package therefore remains the evaluation runtime; `mncs/admission-model.mncs`
   is the shape contract, with a parity test (`MncsShapeParityTests`)
   pinning record names. When the language gains these concepts, the
   router's composition semantics should migrate to MNCS first.
