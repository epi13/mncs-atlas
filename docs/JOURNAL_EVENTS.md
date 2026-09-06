# MNCS Journal canonical events

**Status:** implemented, executed, validated.
**Authority:** Atlas implementation policy (this log constrains Atlas history;
it does not govern other projects).
**Schema:** `schema/journal-event.schema.json`
(`mncs.journal.event.v1`).
**Log:** `site/journal-events/` (canonical), mirrored to `journal-events/`
by `scripts/sync_pages_root.py`.
**Policy:** `mncs.family.journal.v1` in mncs-language
(`docs/journal-event-core.md` there).
**Mechanism:** `journal_maintainer/journal_events.py`.
**Tests:** `tests/test_journal_events.py`.

## What the Journal now represents

Four distinct things that used to blur together:

```text
claim / proposal
  !=
attestation
  !=
canonical Journal event
  !=
human-readable rendering
```

- A **claim** is any agent or human saying "X happened". Candidates live in
  `site/journal-events/proposals/` and are untrusted data. Anyone may
  propose through `journal_events.propose`; proposals never affect history.
- An **attestation** is a validator's statement about evidence (a CI result,
  a conformance run, a signed artifact check). Validators attest; their
  verdicts are inputs, never conclusions.
- A **canonical event** is a structured record admitted only after
  mechanical verification plus live policy verdicts from
  `mncs.family.journal.v1` executed through the MNCS toolchain. Canonical
  events live as `site/journal-events/je-*.json` under a hash chain with
  `HEAD` as the tip commitment.
- A **rendering** is a deterministic projection (`render_projection`,
  `python -m journal_maintainer render-events`) of canonical events into
  human-readable HTML. Prose is generated from events, never the reverse.

## Where canonical truth lives

`site/journal-events/je-<id>.json`, linked by `previous_event_digest`,
committed at `HEAD`. Each event binds its normalized content, provenance,
evidence references, validator verdicts, the MNCS evaluation record, and
the previous digest; Ed25519 issuer signatures follow the Atlas issuance
convention. Recomputing any digest, signature, or link detects silent
rewrites (`python -m journal_maintainer verify-events`).

## Who can propose, what admits

- Ordinary agents and humans: `propose` (write a candidate) and `query`
  (read history and candidates). No key, no toolchain, no authority.
- Canonical admission (`journal_events.admit`) additionally requires the
  issuer key and a live `PolicyEvaluator`. The production evaluator
  (`MncsCliEvaluator`) executes `gate_admit`, `admission_decision`,
  `trust_transition`, and `may_render_public` from
  `mncs.family.journal.v1` per admission and records the verdicts in the
  event. Without a running evaluator, admission holds (UNKNOWN) — it never
  admits on cached, assumed, or reimplemented verdicts.
- There is deliberately no CLI path to admission: canonical writes happen
  through reviewed implementation changes, never through the weekly
  routine maintainer (whose write scope in `journal_maintainer/paths.py`
  excludes the event tree) and never through model output alone.

## Admission refusals (reason codes)

`1` validator rejects · `2` evidence refused (malformed, stale, digest
mismatch, wrong HEAD) · `3` semantic duplicate · `4` model-only claim
without validator attestation · `5` unresolved (held, may be re-proposed
with better evidence). A malicious or mistaken agent that reaches Atlas
code can do no more than file a proposal; every path to canonical history
evaluates real evidence through MNCS policy.

## Tamper-evidence

`verify_chain` recomputes every event id, digest, and signature, walks the
`previous_event_digest` links (never filename order), and reports rewrites,
reorders, deletions, forks, orphans, HEAD drift, forged signatures, and
evaluation discipline violations. Trust-root discipline: the only record
allowed without an MNCS evaluation is the genesis baseline, which must
stay `legacy_unattested`; evaluated events may never claim quarantine
standing.

## Micro-model boundaries

Model roles (`classifier`, `summarizer`, `narrator`, `duplicate-detector`,
`redactor`) produce observable hints carried on proposals under
`interpretation`. Hints are signed for tamper-evidence but never rendered
as history and never admitted: `model_may_admit` is constantly false in
MNCS, pinned by tests on every backend. The legitimate flows are narrow: a
duplicate hint may become the `duplicate_known` input of a later case, and
a sensitivity hint routes an event to redaction review — but each still
passes through the evidence gate and admission verdict before anything is
admitted or rendered.

## Rendering and redaction

`render_projection` regenerates `index.html` plus per-event pages
deterministically; rendering twice is byte-identical (tested), and CI can
enforce `render-events --check`. Events whose render guard is false
(security detail without completed redaction review) render as withheld
placeholders: subject, narrative, and evidence locators stay out of the
public view until review. The prose Development Journal
(`site/journal/*.html`) is unchanged and remains editorial, non-normative
history; new canonical events project into `site/journal-events/`.

## RFC integration

`rfc.advanced` / `rfc.completed` events must cite the RFC-defined
acceptance evidence (ledger entries, criterion results, implementation
revisions) as evidence items with validator attestations. A prose post or
bare assertion cannot satisfy the gate: without evidence the tally is
UNKNOWN (held), and `transition_allowed`-style upgrades without a PASS
gate are refused by the same MNCS logic that guards the RFC ledger. Atlas
answers "what is the state of RFC N" from the event chain plus the owning
ledger, never from narrative alone.

## Commons integration

New events enter at `observed` and promote to `locally_proven` on local
evidence. `independently_confirmed` and `commons_promoted` require the
corresponding trust events with confirmations recorded under
`commons_confirmations` (Commons record ids and locators). One CI run is
`locally_proven`, never ecosystem truth — the trust machine has no
shortcut from local proof to Commons promotion.

## Legacy entries

The pre-canonical Development Journal HTML is preserved untouched. Its
content hash is recorded once in the genesis baseline event, marked
`legacy_unattested`, with no reconstructed provenance and no MNCS
evaluation. The genesis record is honest about the boundary: everything
before it is preserved context, not attested history.

## How a human verifies an entry

1. `python -m journal_maintainer verify-events` (chain, digests,
   signatures, evaluation discipline).
2. Open `site/journal-events/je-<id>.json`: check `evidence` digests
   against the cited bytes, `validators` against the cited runs, and
   `mncs_evaluation` for the module, backend, and verdicts.
3. `python -m journal_maintainer render-events --check` (projection
   reproduces the committed pages).
4. Re-run the cited MNCS corpus cases with the locked toolchain to replay
   the policy verdicts.

## Current limits (honest gaps)

- Admission keys are operator-managed; this campaign's ceremony key is
  published in `site/journal-events/KEYS.json` with its private component
  destroyed after the genesis admissions, so further admissions need a new
  ceremony. Rotation is a manual implementation change, not yet a protocol.
- `independently_confirmed` and `commons_promoted` standings have machine
  slots but no live confirmations yet; no event claims them.
- Distributed (Fabric) replay of the evaluator verdicts is designed, not
  yet executed: verdicts record backend and result digest so a worker can
  reproduce them, but no worker run is on record.
- The prose Development Journal is not yet generated from events; the two
  surfaces coexist with the canonical log as the history of record for
  new machine-verifiable progress.
