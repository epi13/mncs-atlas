# Atlas Journal Maintainer — Implementation

This document describes the implementation of the adopted contract in
[`JOURNAL_MAINTAINER.md`](JOURNAL_MAINTAINER.md). It is a bounded editorial and
publication pipeline, not a general orchestration service.

## Ownership and flow

```text
evidence-producing MNCS family projects
        │ public bounded interfaces
        ▼
Atlas collector → normalized EvidenceBundle (hash + provenance)
        │
        ├─ capable scheduled model/editor → structured draft
        └─ deterministic triage/heuristic → preview or manual fallback
        ▼
evidence-ID/uncertainty validation → Atlas HTML renderer
        ▼
PR producer (PR-only) → independent Atlas CI → independent finalizer
        ▼
GitHub promotion, only when the exact head is CLEAN and guarded
```

Atlas owns journal semantics and the publication surface. MNCS Control is a
bounded workspace/Git/tooling arm. Harness may route and govern model work;
Fabric supplies execution evidence; Forge supplies bounded evaluation; Commons
supplies public coordination records. None becomes the journal's semantic
owner or an authority layer.

## Invocation and rollout modes

```bash
python -m journal_maintainer run --dry-run --mode dry-run
python -m journal_maintainer run --dry-run --draft-file draft.json --synthesizer editor-draft --mode editor-preview
python -m journal_maintainer run --publish --mode pr-only
python -m journal_maintainer finalize --pr-number 123
```

The scheduled workflow is PR-only. `guarded-auto` is a deployment mode, not a
claim made by tests; it requires `MNCS_JOURNAL_APP_TOKEN`, a narrowly scoped
GitHub App installation, branch protection with required Atlas checks, and the
repository's Allow auto-merge setting. If the token or any state is missing,
the finalizer refuses promotion.

### Editor handoff with live collection

Live collection stamps retrieval time into evidence, so bundle identity changes
on every fresh collection. The supported editor workflow is therefore:

1. Pass one (collection): `run --dry-run --output-dir DIR` writes
   `evidence-bundle.json` plus an `editor-brief.json` triage summary.
2. The capable editor writes `draft.json` bound to that exact `eb-…` id.
3. Pass two (validation/publication): replay the recorded bundle for stable
   identity —
   `run --publish --evidence-file DIR/evidence-bundle.json --draft-file draft.json --synthesizer editor-draft --now <pass-one-interval-end>`.
   The recorded bundle is accepted directly by `--evidence-file`, so interval,
   source statuses, and evidence IDs are byte-stable between passes.

### GitHub token discovery

Token priority: explicit argument → `MNCS_JOURNAL_APP_TOKEN` /
`MNCS_JOURNAL_GITHUB_APP_TOKEN` (App identity) → `GITHUB_TOKEN` / `GH_TOKEN`
→ an authenticated local `gh` CLI (`gh auth token`). Only App tokens satisfy
guarded-promotion provenance; operator credentials are recorded as
`github_token_source: gh-cli|env|explicit` and never masquerade as the App.

The App must be configured by an operator with only the repository permissions
needed to read checks, create/update the maintainer PR, push its branch, and
request auto-merge. Prefer repository secrets `MNCS_JOURNAL_APP_ID` and
`MNCS_JOURNAL_APP_PRIVATE_KEY`; the workflow mints a short-lived installation
token scoped to `epi13/mncs-atlas`. A pre-minted `MNCS_JOURNAL_APP_TOKEN` is
accepted as a documented fallback but must be rotated before expiry. No
credential is stored in the repository. The workflow uses `GITHUB_TOKEN` only
for ordinary checkout fallback in dry-run mode; an unattended publish requires
the App token.

## EvidenceBundle/editor protocol

Collection is deterministic and bounded. `build_evidence_bundle()` emits a
stable `eb-…` identity derived from the interval, prior publication, source
statuses, and evidence records. The bundle records:

- exact source identities and repository ownership;
- item IDs, URLs/locators, timestamps, file/document excerpts when a high-signal
  PR changes architecture/RFC/specification/documentation text;
- temporal coverage and delayed-run interval;
- `AVAILABLE`, `PARTIAL`, `EMPTY`, `UNAVAILABLE`, `MALFORMED`, and `UNKNOWN`
  source states, including per-repository GitHub completeness;
- prior-journal continuity and unresolved questions;
- experiment/Commons evidence when a public adapter is configured, and explicit
  gaps when it is not;
- untrusted-data provenance suitable for audit.

The model/editor returns JSON with `evidence_bundle_id`, an `editor` object
(`identity`, `type`, optional `run_id`), readable `title`/`lede`/`sections`,
and optional `used_item_ids`, unresolved questions, omissions, and gaps. Atlas
validates that a real draft exists, the bundle identity matches, and the
disclosure is non-normative. A heuristic run is always recorded as
`synthesizer=heuristic`; it cannot be relabeled `editor-draft` by a CLI flag.
Evidence and repository text are data, never instructions.

## Checkpoints and idempotency

The latest successful journal HTML publication is the durable checkpoint. A
delayed run covers the interval since that publication, not a blind seven-day
window. Pagination is bounded but sufficient for delayed/active repositories.
The interval key is reused for retries. An existing retry branch is trusted
only when its ancestry is based on the current trusted `origin/main`; a branch
name or maintainer label alone is not provenance. Workflow concurrency groups
prevent overlapping scheduled runs from racing one interval.

## Routine mutation and complete diff gate

Routine publication may add one dated canonical article, its generated root
mirror, update the journal index and sitemap, and update only generated mirrors
required by those changes. `paths.diff_paths()` and `check_diff()` inspect an
explicit trusted `base...head` range, including committed changes, deletions,
renames, and reused-branch history. `verify_append_only()` rejects modification
or deletion of any old article and requires exactly one new canonical article
plus its mirror. The same gate runs in CI and before publication; a clean
working tree is never treated as proof of a clean PR.

Historical corrections/migrations require a separate implementation PR and
are never eligible for routine auto-merge.

## Evidence retrieval and status

GitHub adapters paginate bounded PR/issue/commit/release windows and inspect
bounded changed-file patches for high-signal documentation. Each owning repo
tracks endpoint completeness explicitly. A total owning-repository outage is
`UNAVAILABLE` and fails closed; mixed endpoint/repository retrieval is
`PARTIAL` and remains uncertain; an intact no-record interval is `EMPTY`.
Commons and experiments remain public/configured adapters only; the MNCS
Control journal-context bundle (`--journal-context-file`) is the supported
bounded local surface for durable experiment state, local-only Git work,
Fabric/Forge references, redacted Control activity, and local notes, mapped to
the explicit `operator-context` source class with its own completeness status.
Atlas does not open sibling stores or import Control/Fabric/Forge internals.

## PR creation versus promotion

The producer creates/updates a PR and records the current covered interval,
source classes, evidence gaps, bundle identity, editor path, and current head
SHA. It does not treat local validation as independent CI. The finalizer fetches
the current PR again and verifies:

- exact head SHA and complete base→head diff;
- maintainer App/repository/branch provenance (labels are supplemental);
- `mergeable_state == CLEAN` (UNKNOWN is ineligible);
- no `CHANGES_REQUESTED` review and no explicit human-hold label;
- current repository auto-merge policy;
- every check run/status for that exact head completed successfully.

A changed head invalidates the prior decision. The finalizer updates the PR's
machine-readable provenance with the actual gate result before it can request
GitHub auto-merge. Required checks and GitHub branch protection remain
independent mechanical authority; model/heuristic output never substitutes for
them.

## Validation and tests

```bash
python scripts/sync_pages_root.py --check
python scripts/check_site.py
python scripts/check_journal.py
python -m unittest discover -s tests -t . -v
```

Tests include temporary-repository base→head diffs for clean-checkout PRs,
forged/reused maintainer branches, old-entry modification/deletion, accepted
routine mutations, unknown mergeability, pending/missing checks, requested
changes/holds, changed heads, editor-draft provenance, source outage/partial
states, delayed pagination, and finalizer provenance. Site and mirror checks
remain independent of the journal package tests.

## Explicit deferred configuration

Operators still need to install/configure the GitHub App, enable required Atlas
checks and Allow auto-merge, and provide a public experiment export if live
experiment evidence is desired. Until then, production mode is `pr-only` or
editor-preview and all promotion decisions remain fail-closed.
