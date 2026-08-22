# Atlas Journal Maintainer — Implementation

This describes the **implemented** Journal Maintainer, not the original contract proposal. The contract remains [JOURNAL_MAINTAINER.md](JOURNAL_MAINTAINER.md). Where they disagree, treat this file as the map of current code and the contract as the authority boundary.

## What exists

A stdlib-only Python package, `journal_maintainer/`, plus thin scripts and CI invocation surfaces.

```text
python -m journal_maintainer run --dry-run
python -m journal_maintainer run --prepare
python -m journal_maintainer run --publish
python -m journal_maintainer checkpoint
python -m journal_maintainer check-paths
python -m journal_maintainer validate
python scripts/journal_maintainer.py …   # same CLI
python scripts/check_journal.py
python scripts/check_journal.py paths
```

GitHub Actions:

- `.github/workflows/ci.yml` — site checks, journal checks, unit tests, path allow-list on `journal/maintainer/*` PRs
- `.github/workflows/journal-maintainer.yml` — weekly + `workflow_dispatch` invocation of the **same** CLI
- `.github/workflows/pages.yml` — still deploys `site/` after integrity checks

MNCS Control MCP is the preferred interactive execution arm: it already provides the workspace, Git, `gh`, and `python -m journal_maintainer` via `terminal_exec`. Control does not own journal semantics.

## Architecture

```text
invocation (Control / Actions / human CLI)
        │
        ▼
checkpoint ← published journal HTML (no database)
        │
        ▼
evidence adapters (repo → experiments → Commons → previous journal → hints)
        │
        ▼
editorial synthesis (separate from collection)
        │
        ▼
HTML render matching site/journal conventions
        │
        ▼
canonical write + python scripts/sync_pages_root.py
        │
        ▼
validate_site + validate_journal + path allow-list
        │
        ▼
git worktree from origin/main → journal/maintainer/<interval> → PR + provenance
        │
        ▼
guarded auto-merge only if the gate passes
```

The maintainer is a **bounded Atlas capability**. It preserves and synthesizes developmental history. It does not become an authority layer.

## Core types

Implemented in `journal_maintainer/models.py`:

| Concept | Type |
| --- | --- |
| journal run | `JournalRun` |
| covered development interval | `CoveredInterval` |
| previous successful publication | `PreviousPublication` |
| evidence source | `EvidenceSourceResult` |
| evidence item | `EvidenceItem` |
| evidence provenance | `EvidenceProvenance` |
| topic cluster | `TopicCluster` |
| confidence / unresolved evidence | `Confidence`, `unresolved` flags, `omitted_uncertain` |
| draft entry | `DraftEntry` |
| rendered journal entry | `RenderedEntry` |
| publication eligibility | `PublicationEligibility` |
| automatic-merge eligibility | `AutoMergeEligibility` |
| no-op run | `RunOutcome.NO_OP` / `ALREADY_PUBLISHED` |
| failure state | `FailureState` |

## Checkpoints and idempotency

There is no opaque database.

1. Parse `site/journal/*.html` (filename `YYYY-MM-DD-<slug>.html`, journal number, optional `mncs:covered-*` meta tags).
2. The latest successful publication is the checkpoint.
3. The uncovered interval starts **after** that entry's covered end, or the next UTC day after a human marker that has no covered-period metadata.
4. A retry of the same interval reuses branch `journal/maintainer/<start>-<end>`.
5. If an entry already carries that covered-period key, the run is `already-published` and publishes nothing.

The opening human entry (`001`, 2026-08-20) is a valid checkpoint even though it predates the maintainer.

## Evidence sources

Preferred order is implemented, not just documented:

1. **Owning repositories** — GitHub merged/open PRs, commits, issues, releases, RFC/docs/architecture path classification. Broad collect, editorial filter. Tokens: `GITHUB_TOKEN` / `GH_TOKEN`.
2. **Experiments** — only a caller-supplied public snapshot (`--experiments-file` / `MNCS_EXPERIMENT_SNAPSHOT`). No scrape of Control/Fabric/Forge internals.
3. **Commons** — public Agent Exchange HTTP (`MNCS_COMMONS_URL`, `GET /.well-known/mncs-commons` then `POST /exchange/v0alpha1/query`). Never opens the Commons store. Unavailable is a recorded gap.
4. **Previous journal entries** — continuity, unresolved questions, de-duplication of already-told stories.
5. **Conversation hints** — `--hints-file` only. Low confidence. Never the sole source of a technical claim.

Family repositories are read from `site/atlas.json` plus public operator repos listed in `config.EXTRA_PUBLIC_REPOSITORIES` (`epi13/mncs-control-mcp`). All ingested text is untrusted data (`sanitize.py`).

`--evidence-file` records representative evidence for tests and offline dry-runs.

## Editorial pipeline

Collection and synthesis are separate modules.

The heuristic synthesizer:

- drops dependency bumps, formatting, typos, and other noise unless they carry high developmental signal
- clusters remaining items into a small number of themes (journal/orientation, family spine, authority/evidence, language, Fabric, Commons, operator stack, learning, rights, studies)
- writes narrative sections rather than commit lists
- keeps failures, abandoned work, and unresolved questions
- omits topics already established by the previous entry when they have not materially moved
- refuses to invent Commons or experiment inspection
- sets `ambiguity=True` when owning-repository evidence is missing or material topics stay UNKNOWN with too little support

It is **not** a large language model. Scheduled GitHub Actions use this heuristic. An editor (including a Control-driven model session) may pass `--draft-file` JSON and `--synthesizer editor-draft`.

## Publication surface

Routine runs may write:

- `site/journal/<date>-<slug>.html`
- `site/journal/index.html`
- `site/sitemap.xml` (journal discovery URLs)
- generated root mirrors produced by `python scripts/sync_pages_root.py`

They may **not** write docs, CI, schemas, `atlas.json`, or sibling repositories. `journal_maintainer/paths.py` is the computer-checked allow-list.

Machine-maintained entries include:

- `mncs:journal-number`, `mncs:covered-start`, `mncs:covered-end`, `mncs:maintainer`, `mncs:non-normative`
- an unobtrusive disclosure (`journal-disclosure`)
- author `Atlas Journal Maintainer` (not a false human attribution)
- an inert `<script type="application/json" id="journal-maintainer-provenance">` block inside the article file (non-normative; no secrets)

The contract was updated to include sitemap discovery files and in-article provenance, which stay inside the authorized journal HTML / discovery surface.

## Invocation

### Dry-run (no mutation)

```bash
python -m journal_maintainer run --dry-run --output-dir /tmp/atlas-journal-dry-run
```

Optional recorded evidence:

```bash
python -m journal_maintainer run --dry-run --evidence-file tests/fixtures/example-evidence.json --output-dir /tmp/atlas-journal-dry-run
```

### Local prepare (writes the current checkout)

```bash
python -m journal_maintainer run --prepare
python scripts/sync_pages_root.py --check
python scripts/check_site.py
python scripts/check_journal.py
```

Use `--prepare` only on a throwaway or already-journal branch. Do not mix implementation files into a routine journal PR.

### Real publication run

```bash
python -m journal_maintainer run --publish
```

This leaves the current checkout alone. It:

1. synthesizes against the current Atlas tree
2. creates a git worktree from `origin/main` (or reuses `origin/journal/maintainer/<interval>`)
3. writes only authorized files
4. validates
5. commits, pushes, opens or updates the PR
6. enables GitHub auto-merge only when the gate says yes

### Control

From MNCS Control, run the same commands with `terminal_exec` in the `mncs-atlas` project, `network=true` when GitHub or Commons must be contacted. Do not add a second editorial implementation inside Control.

## Auto-merge gate

Mechanical conditions (see `gitops.evaluate_auto_merge`):

- originated from this maintainer
- only authorized paths changed
- Atlas validation passed
- no material evidence ambiguity
- no merge conflict (`mergeable_state` not `dirty`/`blocked`)
- no requested-changes review / human hold
- repository `allow_auto_merge` is true

The automation never force-merges and never bypasses required GitHub checks. If Settings → General → Pull Requests → **Allow auto-merge** is off, the PR stays open and the run notes the remaining repository configuration.

CI independently re-checks the path allow-list on `journal/maintainer/*` branches.

## Failure and no-op

| Situation | Behavior |
| --- | --- |
| GitHub family evidence unavailable | fail closed, no article |
| Commons unavailable | continue if repository evidence is enough; record the gap |
| Experiment snapshot missing | do not imply experiments were inspected |
| Validation failure | do not merge |
| Unexpected paths | refuse auto-merge / fail publish |
| Merge conflict | leave PR open |
| Material ambiguity | `AMBIGUOUS`, no auto-merge |
| No meaningful development | `NO_OP`, success, no article |
| Interval already published | `ALREADY_PUBLISHED`, success, no duplicate |

No-op bookkeeping is the GitHub Actions job summary / CLI JSON. It is not a fake quiet-week article and not a repo database.

## Tests

```bash
python -m unittest discover -s tests -t . -v
python scripts/sync_pages_root.py --check
python scripts/check_site.py
python scripts/check_journal.py
```

Tests use fixtures and temporary Atlas trees. They do not mutate production repositories.

## Remaining deferred work

- Live Commons consultation depends on an operator-configured public node URL.
- Live experiment consultation depends on a public export; Control `experiment_list` is not imported as a private API.
- Heuristic synthesis can be replaced per-run with an editor draft; there is no bundled LLM client, by design.
- Repository auto-merge and branch protection remain GitHub settings, not something the maintainer can honestly enable from code alone.
- Stronger Rights & Provenance / Commons-backed publication identities are Phase 4 of the contract.
