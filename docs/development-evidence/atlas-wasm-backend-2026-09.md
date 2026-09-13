# Atlas WASM backend evidence — 2026-09

Atlas's stateful JSON model was the consumer workload for two independent
`mncs-language` backend pressures. The canonical machine records live in
[Commons' pressure exchange](https://github.com/epi13/MNCS-Commons/tree/main/pressures);
this page keeps the explanation close to the consumer and its tests.

## Pressure 1: nested cell address normalization

Commons record:
[`MNCS-LANG-4F3798658F55`](https://github.com/epi13/MNCS-Commons/blob/main/pressures/records/MNCS-LANG-4F3798658F55.json)

At language revision `a0255f8`, recursive cell flattening used an `i64`
scratch local directly as the address for a WASM `i32.load`. The Atlas model
could not instantiate because the generated module was invalid at the memory
instruction boundary.

The generic fix landed in `mncs-language` commit `f527b49`: recursive lowering
now explicitly wraps an `i64` scratch address to `i32` before a memory load.
The focused regression is
`nested_flatten_wraps_i64_scratch_addresses_before_memory_access`.

## Pressure 2: packed bounded view lifetime

Commons record:
[`MNCS-LANG-4219A56741DB`](https://github.com/epi13/MNCS-Commons/blob/main/pressures/records/MNCS-LANG-4219A56741DB.json)

After the first fix, the full Atlas render plan exposed a separate region
lifetime failure at language revision `f527b49`. Packed bounded byte views are
`i64` descriptors and do not allocate, but the region planner treated them as
heap-backed views and suppressed reclamation. Repeated chunks then exhausted
the 32 MiB arena.

The generic fix landed in `mncs-language` commit `f9d790b`: packed bounded
views are classified as nonallocating words, so safe loop-region reclamation
continues. The focused regression is
`packed_bounded_views_are_preserved_as_nonallocating_words`.

## Current proof

Both pressures are resolved in Commons after current PASS verification from
`mncs-language` and `mncs-atlas`:

- `mncs-language`: `cargo test -p mncs-codegen` passed, including both focused
  regressions.
- `mncs-atlas`: `python -m unittest tests.test_experimental_wasm -q` passed,
  including independent WASM instantiation and the complete model render
  plan.

No Atlas-side workaround was promoted as a language resolution. The source
and artifact history remain linked through Atlas `main` `04804ca` and language
`main` `e39f370`.
