# Experimental Atlas MNCS/WASM migration

This tranche advances Atlas from byte-stream projections to a typed MNCS
application model and a structured render boundary. It remains an experiment,
not a claim that Atlas or MNCS authority has moved into the browser runtime.

## What runs in MNCS-produced WASM

`site/experimental-atlas.html` loads a structural scanner and the typed model
module built from `mncs/atlas-model.mncs` plus the reusable
`mncs.std.json_cursor.v1` and `mncs.std.text_view.v1` modules:

1. fetch `site/atlas.json` as an `ArrayBuffer`;
2. stream the bytes in 64-byte views to the structural JSON gate;
3. feed the same bytes to a bounded `AtlasModel` containing up to 15 typed
   `Project` records and relationship/maturity counts;
4. obtain a fixed `RenderPlan` of clear-target, append-card, and summary
   commands;
5. interpret those commands through safe browser DOM construction.

The model represents text as borrowed `TextView` spans into the original
Atlas bytes (`start`, `length`, `encoded`, `utf8_valid`). It does not create a
JSON DOM or require an unbounded string/map runtime. The typed model uses the
canonical composite-cell ABI: 8-byte aligned slots, low-32-bit cell
references, and nested cells for records and exact sequences.

Each composite module exports `memory`,
`mncs_host_buffer(i32) -> i64`, and `mncs_host_buffer_reset()`. The host
reserves one byte region from the module allocator, decodes its packed
`low32=offset/high32=capacity` descriptor, and reuses it for each chunk. The
model deliberately does not reset after each chunk because immutable state
cells and borrowed spans must survive until the instance is dropped. Its
portable-WASM arena is a bounded 512-page (32 MiB) budget and the adapter
rejects input above 24 KiB.

`atlas-wasm-manifest.json` is the machine-readable ABI record. It keeps
artifact status `UNKNOWN`: build-time WASM magic, SHA-256, and corpus checks
pass, but independent equivalence, browser QA, and formal cutover review are
not certification claims.

## Structured render boundary

The MNCS render plan uses numeric operations and targets so the host does not
need to understand JSON keys or reconstruct Atlas records. Text crosses only
as decoded `TextView` spans. The host validates external repository links to
HTTP(S), uses `createElement`/`append`/`textContent`, and never uses
`JSON.parse`, `Response.json()`, or `innerHTML` on the experimental path.
Static legend data supplies display labels and CSS classes for maturity codes;
the model still owns classification and counts.

The surface now renders the same Atlas concerns as the canonical guide's
project/status sections: a project map, descriptive maturity/status cards,
relationship count, consumer-contract guidance, and explicit authority
boundaries. The production `site/assets/app.js` remains untouched as the
canonical fallback/progressive-enhancement path; it still owns production
page enhancements until a later cutover tranche.

## Compiler and standard-library pressure

The typed model exposed two reusable language issues, now covered by tests:

- local records can appear inside bounded record fields such as
  `[Project; 15]`; the elaborator seeds local declarations into its
  provisional record namespace before resolving fields;
- WASM lowering now distinguishes an eight-byte canonical slot from its
  low-32-bit cell-reference payload, preventing invalid WASM for nested
  record/sequence fields.

The JSON cursor adds a bounded root/completion check, saturated handling for
unknown keys longer than its 16-byte matcher window, and basic UTF-8 lead /
continuation validation. Its differential corpus covers complete input,
incomplete roots, long unknown keys, and malformed UTF-8 across the five
executable backends.

## Reproduce

From the parent `mncs-atlas` and sibling `mncs-language` checkouts:

```bash
python scripts/build_mncs_wasm.py
python scripts/sync_pages_root.py
python scripts/sync_pages_root.py --check
python scripts/check_site.py
python scripts/check_journal.py
python -m unittest discover -s tests -t . -v
python3 -m http.server 8000 --directory site
```

Then open `http://localhost:8000/experimental-atlas.html`. The independent
Node smoke path should report 20,413 input bytes, 319 chunks, 15 projects,
19 relationships, 33 render nodes, and a valid/complete plan.

## Cutover blockers

The production `/` path remains static/progressive enhancement. A default-site
switch is not credible until the project has a generic text/DOM/event host
contract, strict Unicode scalar validation, independent runtime equivalence
beyond the Node smoke path, malformed/truncated full-Atlas differential
corpora, responsive browser QA, and an explicit formal cutover review.

See the companion language evidence record:
`mncs-language/docs/development-evidence/atlas-json-wasm-vertical-slice-2026-08.md`.
