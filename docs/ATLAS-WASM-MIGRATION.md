# Experimental Atlas MNCS/WASM migration

This tranche starts the Atlas conversion as a real, separately loadable
vertical slice. It is an implementation experiment, not a claim that Atlas or
MNCS authority has moved into the browser runtime.

## What runs in MNCS-produced WASM

`site/experimental-atlas.html` loads two modules built from Atlas `.mncs`
adapters and the reusable `mncs.std.json_stream.v1` and
`mncs.std.json_projection.v1` modules:

1. fetch `site/atlas.json` as an `ArrayBuffer`;
2. stream its bytes in 64-byte views to a structural JSON state machine;
3. run raw-key/member projections for maturity and relationship observations;
4. render only scalar results through a small DOM host adapter.

Each module exports the typed `mncs_host_buffer(i32) -> i64` ABI plus
`mncs_host_buffer_reset()`. The host reserves one byte region from the module
allocator, decodes its packed `low32=offset/high32=capacity` descriptor, and
reuses that region for every chunk; reset recycles target-array allocations
after each consumer call. Projection selectors share one instantiated module;
they are no longer isolated by repeated instantiation. The adapter gates
projections and DOM output on a structural scan result of `1`.

Compiler-internal byte views derived from exact cell sequences use the aligned
address low bit as a stride marker; the host-buffer ABI always returns aligned
addresses and the marker is removed before host-visible reads.

The checked-in artifacts are built by `scripts/build_mncs_wasm.py`, which runs
the language experiment CLI, refuses corpus mismatches, and records artifact
hashes and unresolved status in `site/assets/atlas-wasm-manifest.json`.

## Boundaries that remain deliberate

The production `/` page remains the canonical static/progressive-enhancement
Atlas and still loads the existing `site/assets/app.js`. The experimental page
has its own visible fallback and is `noindex`. JavaScript owns browser APIs,
linear-memory writes, chunk scheduling, and DOM construction; JSON parsing,
structural validation, and schema-shaped counting are performed by MNCS/WASM.
Python remains responsible for site integrity, mirror generation, and the
Journal Maintainer. This page does not create conformance, maturity, or
publication authority.

The first metric is called “Maturity fields” because the intentionally shallow
raw-key projection observes 16 `maturity` keys in the current map: 15 project
fields plus one top-level documentation link. The five member counts are
`experimental=4`, `research=5`, `active-infrastructure=4`, `incubating=1`,
and `orientation=1`; relationship `from` count is 19.

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

Then open `http://localhost:8000/experimental-atlas.html`. A native Node host
smoke test also instantiates both `.wasm` files, uses their exported `memory`,
passes i64 low-offset/high-length descriptors from the host-buffer ABI, and
reproduces the observations above without parsing JSON in JavaScript.

## Language pressure and next tranche

The experiment exposed and generalized several missing pieces in
`mncs-language`: a complete bounded JSON scanner, a streaming structural JSON
envelope, raw schema projections, byte-view layout, named browser memory
exports, byte-width WASM loads, packed byte-view marshaling, and the first
stable typed host-buffer/allocator contract. It still needs UTF-8/text APIs,
structured render commands, event/fetch capabilities, and independent browser
runtime validation before a default-site migration is credible.

See the companion language evidence record:
`mncs-language/docs/development-evidence/atlas-json-wasm-vertical-slice-2026-08.md`.
