# MNCS Family Registry

Atlas now has two related machine surfaces:

- `site/atlas.json` remains the small, non-normative human-orientation map.
- `registry/compiled.json` is the deterministic family architecture graph.

The compiled registry is built from three Atlas-owned, family-level inputs and
compact repository manifests:

```text
repository .mncs/project.json files
        + pinned snapshots of the MNCS family-manifest contract
        + Atlas ownership claims and decision index
                         |
                         v
               registry/compiled.json
                         |
                 local Atlas queries
```

The repository-manifest input is the existing
`mncs-family.repository-manifest/v0alpha1` contract owned by the MNCS standard.
Atlas does not change its semantics. Projects may adopt the same document at
`.mncs/project.json`; until then Atlas can consume a pinned snapshot from the
standard checkout. A local manifest wins over the snapshot for that project,
and the compiled output records whether the source was local or pinned.

## Querying

Run from the Atlas checkout:

```bash
python -m registry context .
python -m registry project mncs-ingest
python -m registry owner source-migration
python -m registry capability parsing
python -m registry find "schema validation"
python -m registry related mncs-compiler
python -m registry decisions AST
python -m registry status numeric-primitives
python -m registry validate
python -m registry validate --fresh
```

`context` is the intended agent preflight surface. It identifies the current
repository by `.mncs/project.json` first and by a registered checkout name as a
fallback. Its default text output is deliberately compact; `--json` returns
the versioned `mncs-atlas.context-capsule/v1` object.

## Ownership semantics

Capability claims distinguish `canonical-authority`,
`primary-implementation`, `secondary-implementation`, `consumer`,
`experimental-implementation`, and `integration-layer`. A capability can be
shared, but an `exclusive` capability must have exactly one canonical
authority. A claim is an Atlas architectural declaration backed by an
inspectable source reference; it is not a conformance or promotion decision.

The graph also carries `depends_on`, `provides`, `consumes`, `canonical_for`,
`implements`, `experiments_with`, `governs`, `applies_to`, `owned_by`, and
`supersedes` edges. Contract edges are normalized through explicit aliases so
the historical central manifest names `mncs-control` and `mncs-forge` do not
collapse the actual `mncs-control` dynamics repository into the
`mncs-control-mcp` operator project.

## Build, sync, and caching

```bash
python -m registry build
python -m registry validate
python -m registry sync --standard-root ../machine-native-complexity-standard
python -m registry build --workspace-root ../mncs-harness
```

`registry/compiled.json` contains no clock-generated fields. Its registry hash
is SHA-256 over the canonical normalized content; the first 16 hex digits are
the compact registry revision. Source digests make stale local rebuilds
detectable. `validate --fresh` compares the checked-in artifact with a rebuild
of the current Atlas inputs and returns `STALE` with both revisions when the
cache needs regeneration. Agents use the checked-in artifact for normal
lookups and do not need network access. `sync` is the explicit refresh
operation for the pinned standard-manifest snapshot.

Workspace discovery is opt-in to preserve reproducibility: a build with
`--workspace-root` deliberately incorporates local manifests, while the
default build uses the pinned snapshot plus Atlas's own local manifest.

The eight current adoption pilots in the workspace use this opt-in check:

```bash
python -m registry build --output /tmp/mncs-family-local.json \
  --workspace-root ../mncs-numerics --workspace-root ../mncs-ingest \
  --workspace-root ../mncs-store --workspace-root ../mncs-index \
  --workspace-root ../mncs-compiler --workspace-root ../mncs-harness \
  --workspace-root ../mncs-language-service --workspace-root ../RAVEL
```

## Boundaries

Atlas owns the architecture graph and context projection. Commons owns
unresolved family pressure and its append-only evidence/lifecycle exchange;
Atlas records only stable architecture relationships and links to pressure
records when a campaign exposes them. Doctor owns migration, repair, and
conformance work for an individual repository. Forge, Harness, Fabric, and
the language/compiler repositories retain their own execution, assurance,
routing, and semantic authorities.

MNCS Harness now implements this preflight contract in its routed `ask`,
interactive `chat`, and detached `submit` paths (see the
[`mncs-harness` implementation](https://github.com/epi13/mncs-harness/blob/main/src/mncs_harness/atlas_context.py)).
It discovers a nearby checkout or an explicit `MNCS_ATLAS_ROOT`, invokes the
existing Atlas CLI, and injects a bounded text capsule without maintaining a
second registry parser. Missing or stale local Atlas data fails open for
ordinary Harness routing. Forge integration remains intentionally deferred
until its launch/evaluation lifecycle can consume the same contract without
coupling Atlas to Forge internals.

The intended entry-point query is:

```text
mncs-atlas context <workspace>
```

once at agent entry, inject the text capsule into the task preflight, and use
the JSON commands only for targeted follow-up. The caller should preserve
`UNKNOWN` when the registry is stale, missing, or cannot identify a project.

## Current `mncs-lang` boundary

Atlas's executable MNCS sources and WASM lock are now on Source Profile 0.16,
the current producer revision declared by `mncs/mncs-language.lock.json`.
The bounded MNCS/WASM model owns the typed JSON cursor, source-profile
semantics, and render-plan projection used by the human site. The registry
compiler remains a small Python build/query tool because it needs unbounded
repository traversal, host filesystem access, dynamic JSON maps, SHA-256, and
CLI/process I/O that the current bounded profile intentionally does not claim.
It does not reimplement sibling project semantics: catalog and capability
claims are normalized records, while each repository keeps its own contracts
and implementation authority.

## Pressure records from the Atlas workload

The two concrete backend pressures exposed while bringing Atlas to profile
`0.16` are now recorded in Commons and linked to their human-readable
investigation:

| Pressure | Status | Implementation |
| --- | --- | --- |
| [`MNCS-LANG-4F3798658F55`](https://github.com/epi13/MNCS-Commons/blob/main/pressures/records/MNCS-LANG-4F3798658F55.json) — nested cell address normalization | resolved | `mncs-language` `f527b49` |
| [`MNCS-LANG-4219A56741DB`](https://github.com/epi13/MNCS-Commons/blob/main/pressures/records/MNCS-LANG-4219A56741DB.json) — packed bounded view lifetime | resolved | `mncs-language` `f9d790b` |
| [`MNCS-LANG-59894A2D6A3D`](https://github.com/epi13/MNCS-Commons/blob/main/pressures/records/MNCS-LANG-59894A2D6A3D.json) — source-level function/export contract resolution | resolved | `mncs-harness` `512af42` |

Commons preserves the pre-fix reproductions, current verification from both
the language owner and Atlas, and the lifecycle events. See the local
[Atlas backend evidence](development-evidence/atlas-wasm-backend-2026-09.md)
for the consumer-facing explanation. The Harness artifact-contract pressure
is documented in its
[`language-pressure.md`](https://github.com/epi13/mncs-harness/blob/main/docs/language-pressure.md)
ledger. Remaining language limitations around
unbounded filesystem discovery, dynamic maps, hashing, and process I/O stay
documented as deferred pressures until they receive their own reproducible
records.
