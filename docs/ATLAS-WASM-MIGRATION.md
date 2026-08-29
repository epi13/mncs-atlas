# Atlas MNCS/WASM conversion record

This record describes the current production-path conversion of Atlas to a
bounded MNCS/WASM model. Atlas remains non-normative orientation infrastructure:
successful execution does not decide conformance, maturity, authority, or
publication status.

## Current runtime

The canonical `/` page now invokes the shared `site/assets/atlas-wasm.js`
runtime through `site/assets/app.js`. The pre-rendered HTML remains the first
paint and the fail-closed fallback. The diagnostics page at
`/experimental-atlas.html` uses the same runtime and artifacts while exposing
the transport and ABI boundary for inspection.

The production path:

1. fetches `site/atlas.json` as bytes;
2. streams 64-byte views through `atlas-json-scan.wasm`;
3. streams the same bytes through the bounded typed `atlas-model.wasm`;
4. validates a fixed `RenderPlan`; and
5. applies numeric render operations through safe DOM construction.

JavaScript owns browser capabilities: fetch, linear-memory writes, bounded
chunk scheduling, memory/view checks, HTTP(S) link validation, text decoding,
DOM construction, and fallback presentation. MNCS owns JSON structure, schema
meaning, bounded model state, derived counts, validity/completeness, and render
intent. The reusable host contract is documented in
[MNCS browser host boundary](MNCS-BROWSER-HOST.md).

`atlas-json-projection.wasm` is retained as a raw projection witness and
diagnostic fixture. It is not part of the production page's semantic path and
is not silently treated as a second Atlas model.

## ABI and bounded budgets

`site/assets/atlas-wasm-manifest.json` is the generated ABI and provenance
record. It declares the pinned language revision, source/corpus hashes,
compiler identities, artifact hashes, and the current uncertainty status.

The typed model currently declares:

- 65,536 maximum input bytes and 512 WASM memory pages;
- 32 projects, 8 operator components, 64 relationships, 5 maturity levels;
- 64 render nodes;
- `mncs_host_buffer(i32) -> i64`, packed as low-32-bit offset and high-32-bit
  capacity, with an explicit reset function for scalar consumers;
- borrowed `TextView` spans into the original input; and
- `atlas_model_init`, `atlas_model_chunk`, `atlas_model_finish`, and
  `atlas_render` for stateful model execution.

The host rejects invalid descriptors, memory escapes, unsupported render
operations/targets, invalid UTF-8, invalid Unicode surrogate sequences, and
non-HTTP(S) repository links. Any failure leaves the static Atlas surface
visible and reports the reason in the runtime status area.

## Build and reproducibility

The builder is `scripts/build_mncs_wasm.py`. It reads
`mncs/mncs-language.lock.json`, refuses a producer checkout at another Git
revision, builds each artifact into a temporary staging directory, validates
the complete set and manifest, then publishes both `site/assets/` and the
legacy root mirror as a rollback-safe set. `scripts/sync_pages_root.py` keeps
the mirror byte-identical.

From sibling checkouts:

```bash
python scripts/build_mncs_wasm.py \
  --atlas-root "$PWD" \
  --language-root ../mncs-language
python scripts/sync_pages_root.py --check
python scripts/check_site.py
```

CI repeats the build from the locked language revision and fails if the
checked-in artifact bytes differ or the regenerated manifest fails its
internal hash/provenance checks. The manifest records the exact source commit
used to produce the checked-in bytes, so its self-referential commit metadata
is not byte-compared after regeneration. A build made from dirty producer
inputs is marked `uncertain`; a clean, matching rebuild is the reproducible
path. The generated manifest is evidence, not a conformance certification.

## Evidence and remaining UNKNOWNs

The following checks are automated and currently pass when run against the
checked-in artifacts:

- WASM magic, internal SHA-256, byte counts, and manifest consistency;
- corpus expectations for scan, projection, model, and Unicode cursor cases;
- independent Node instantiation and full Atlas render-plan cardinality;
- root/Pages mirror parity and static fallback presence;
- bounded publication rollback tests; and
- Joern control-flow/call/reachability snapshots before and after edits.

The following remain explicitly `UNKNOWN`:

- full-model equivalence across portable WASM, research bytecode, LLVM IR,
  C11, and Cranelift for the stateful streamed interface;
- malformed/truncated full-Atlas differential execution on every backend;
- independent conformance or formal cutover review; and
- a claim that the compiler's exact cost or the generated artifact is
  production-grade beyond this bounded research envelope.

Run the bounded cross-backend attempt with:

```bash
python scripts/run_atlas_model_differential.py \
  --atlas-root "$PWD" \
  --language-root ../mncs-language \
  --binary ../mncs-language/target/debug/mncs
```

The report separates empirical bounded probe agreement from the unresolved
full-stream cases. It must not be read as a conformance result.
