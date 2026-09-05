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

## Executable admission in MNCS

The composition mechanism above is executable MNCS, not just Python:
`mncs/admission.mncs` implements admission states, the 17-capability table,
verdict composition over owner-produced findings, structured denials, bypass
classification, and orientation summaries as pure scalar functions
(`i64`/`bool` in, `i64` out). The Python package remains the rich boundary:
it owns strings, owner adapters, and evidence sets, and translates across
the boundary through the thin glue in `admission/mncs_glue.py`. Authority
stays distributed exactly as before; only the mechanism is machine-native.

`mncs/admission-corpus.json` is the executable contract: every case carries
`expected` values derived from the Python model through the glue
(`mncs/gen_admission_corpus.py`; CI enforces `--check`), so
`mncs experiment run` verifies the MNCS module against owner-defined
semantics instead of against itself. `tests/test_admission_mncs_parity.py`
pins the derivation (corpus matches a fresh derivation; every capability,
owner, evidence string, and path step projects into the ABI).

Scalar ABI boundary rules (host obligations, not MNCS semantics):

- Identity interning: participant/attester strings become nonzero `i64`
  through a host string table (`StringTable`); `0` means unset. Only
  equality is ever observed (self-attestation exclusion), so any injective
  mapping preserves semantics.
- Unknown capability: the host rejects names outside the vocabulary before
  they reach the module. The module's malformed-decision path (reason 16)
  is defense in depth, never the primary gate.
- Attestation bound: four attester slots plus a count. Hosts pass at most
  four; further confirmations only strengthen a grant already established.
- Evidence projection: set-like evidence becomes missing-bits; entries with
  no bit (`admission-state` rungs, lifecycle rungs, independent-forge prose)
  travel as the first-blocking reason code, and
  `independent_confirmations>=2` travels as the need-confirmations flag.
- Reason code: the FIRST blocking finding in canonical adapter order
  (posture, rights, lifecycle, forge, commons, fabric, actions). The Python
  decision joins all finding prose; the scalar decision names the first
  bar so the denial can teach exactly one next step.
- Actor correlation: bypass findings carry no actor (no room in the packed
  layout and none needed for classification). The host joins findings back
  to events by call order, mirroring `scan()`'s `event_index`.

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
2. **Conditional authority is now executable (resolved this pass).**
   The router's composition semantics migrated to MNCS first, as
   predicted: `mncs/admission.mncs` implements admission states, the
   17-capability table, verdict composition (`FAIL > UNKNOWN > PASS`
   over the real `mncs.core.status` lattice), structured denials, bypass
   classification, and orientation as pure scalar functions. Conditional
   authority is encoded as evidence bits plus a need-confirmations flag
   plus a first-blocking reason code; open-ended evidence sets are
   bounded at the ABI (4 attester slots, 8 evidence bits) with documented
   host rules (see "Executable admission in MNCS" above). Evidence:
   44-case model-derived corpus (`mncs/admission-corpus.json`), 9/9
   session and 11/11 denial/bypass cases met on research bytecode and
   portable WASM, and 44/44 met V8-direct on the 31,921-byte
   portable-WASM artifact the runner materialized deterministically
   across runs (SHA-256 `a45e2315…`). The Python package remains the rich boundary (strings,
   owner adapters); `mncs/admission-model.mncs` remains the shape
   contract pinned by `MncsShapeParityTests`. Live owner findings still
   arrive as host-provided scalars by design — Atlas composes authority
   findings, it does not counterfeit them.
3. **Runner observation cost for composed decisions.** A composed
   capability decision is dominated by its evidence-set union, spelled
   as 48 arithmetic bit-tests (6 nested 8-bit ORs; one such OR measured
   at 390 interpreter steps in isolation). Measured on research
   bytecode: ~80-step cases return in seconds, a 566-step case took
   194 s end to end (~60 s compile), a single composed query did not
   finish in 900 s, 23 queries did not finish in 3,300 s on either
   backend, and the 17-query orientation did not finish in 2,700 s on
   either backend — while the same WASM bytes execute all 44 cases in
   seconds under V8-direct. Per-step cost grows super-linearly with trace length, so
   composed decisions are currently verifiable through the runner only
   in small slices, with full-corpus parity attested V8-direct on
   byte-identical artifacts instead. If the runner gains cheaper
   observation (or the language gains multi-bit operations so evidence
   sets stop being spelled one bit-test at a time), the full corpus
   should move back to runner-gated on both backends;
   `scripts/build_mncs_wasm.py` admission support waits on exactly
   that.
