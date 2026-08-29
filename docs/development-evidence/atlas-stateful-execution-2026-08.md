# Atlas stateful execution evidence — 2026-08-29

This record is bounded execution evidence for the Atlas orientation surface. It
is not a conformance result, a compiler-correctness proof, or a production
cutover decision.

## Reproducible inputs

- `mncs-language` producer: `712c99c12283978c72f4b6659c230ca5f2932c9e`
- `mncs-atlas` consumer before generated outputs: `f78e83f6198172e92a76d7262333325df4db1687`
- execution corpus schema: `0.3`
- declared full edge cases: 18
- generated stateful traces: 21 (the three declared chunk-boundary mutations
  expand into one trace per boundary)
- stateful transition sequence: `init → chunk* → finish`
- maximum chunk input: 64 bytes

The reproducible builder command is:

```bash
python scripts/build_mncs_wasm.py \
  --atlas-root "$PWD" \
  --language-root ../mncs-language
```

The clean rebuild reported reproducible provenance. The three generated WASM
byte streams were unchanged from the preceding build:

| artifact | bytes | SHA-256 |
| --- | ---: | --- |
| `atlas-json-scan.wasm` | 6,658 | `922d388fa7bade218d3f59b50f7680d0d7e3c9257c4570658e821a1303c5d3c0` |
| `atlas-json-projection.wasm` | 10,761 | `eec36d4e9d4155997e24fd1c308dae67f6b7f4d92d6cee2f5e2c90eb73524c35` |
| `atlas-model.wasm` | 153,696 | `6f2692220644bf6804c55ef246561fe7d180038e836ecdf323ea5212ed259a04` |

The generated manifest changed to record stateful corpus metadata and the
new producer lock; the artifact bytes did not change because the execution
and provenance changes are host/compiler-side.

## Backend smoke evidence

The two-step `empty-model-state-init-finish` corpus was run independently
with the optimized `mncs-cli` binary across:

- `mncs-portable-wasm-mvp`
- `mncs-research-bytecode`
- `mncs-llvm-ir`
- `mncs-c11`
- `mncs-cranelift`

Every backend returned both transitions, met the final status and intermediate
step expectations, and produced the same stateful transition signature:

```text
4b45a1eda3d87ed56dd83926634f75171db14ef23d5e92f66d5714626fec0174
```

The larger `complete-atlas` trace also completed on portable WASM, LLVM, and
C11 in the optimized differential smoke. Research bytecode and Cranelift
remained time-bounded at the 300-second smoke ceiling; those results remain
`UNKNOWN`, not `PASS`.

## Timing evidence

With `MNCS_TIMINGS=1`, the final optimized build/one-shot sample reported:

```text
parse                 235 ms
compiler-total       2625 ms
compiler-hir         1449 ms
compiler-ssa         2094 ms
compiler-backend     2286 ms
cli-compile          2707 ms
compare-body        71727 ms
compare-ssa        104265 ms
compare-total      104294 ms
```

The earlier captured Atlas debug sample reported `compiler-total=36570 ms`
and `cli-compile=37693 ms`. The profiles differ (debug versus optimized), so
the reduction must not be attributed solely to the source changes. The
stateful-session work specifically removes repeated artifact decode,
immutable SSA validation/block indexing, Cranelift JIT finalization, and
native executable compilation across transitions.

## Joern graph checks

The focused Rust profile was run against the preceding producer commit and
again after the final source edits:

```bash
joern-parse --language rust -o .joern-agent/stateful-baseline-final.cpg crates
joern --script scripts/joern/experiment-bootstrap-profile.sc \
  --param cpgFile=.joern-agent/stateful-baseline-final.cpg --nocolors

joern-parse --language rust -o .joern-agent/stateful-post-final.cpg crates
joern --script scripts/joern/experiment-bootstrap-profile.sc \
  --param cpgFile=.joern-agent/stateful-post-final.cpg --nocolors
```

The baseline/post focused results kept `execute_backend` at one method with
the same two callers, preserved the existing `execute_portable_wasm` and
`execute_research_bytecode` control boundaries, and retained the existing
`validate_function` and `lower_body` control shapes. The post graph exposes
the stateful boundary through `execute_backend_stateful → execute_stateful_case`
and adds the reusable `SsaExecutionSession` execution path. Joern emitted only
the known Rust frontend warnings about fallback ordering for `break`/`continue`.

The equivalent Atlas Python parse was attempted before and after the runner
edits. The installed Joern distribution does not contain
`/home/epi13/.local/share/joern/v4.0.583/joern-cli/py2cpg.sh`; both attempts
therefore failed with the same unsupported-tooling error. No Python graph
claim is made.
