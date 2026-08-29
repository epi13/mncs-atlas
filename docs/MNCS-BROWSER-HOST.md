# MNCS browser host boundary

This is the reusable boundary for a browser host consuming a bounded MNCS/WASM
artifact. It is an implementation contract, not a normative MNCS specification.

## Ownership

The MNCS module owns:

- JSON token/structure validation and bounded nesting;
- schema-shaped model state and derived counts;
- validity and completeness decisions;
- borrowed text descriptors and render-plan operation/target codes; and
- explicit failure behavior when a bound or invariant is exceeded.

The browser host owns:

- fetching bytes and choosing a bounded chunk schedule;
- reserving and validating a host buffer in linear memory;
- keeping the module instance alive while state cells and borrowed spans are used;
- checking packed descriptors, integer widths, offsets, lengths, capacities, and
  render-node bounds;
- decoding UTF-8 and JSON escapes with fatal invalid-sequence handling;
- sanitizing external links to HTTP(S);
- mapping approved numeric operations to DOM construction; and
- preserving a visible static fallback whenever activation fails.

Neither side may silently transfer authority. A render plan is intent, not
permission to perform an arbitrary DOM operation, and a successful module run
is not a conformance or publication decision.

## Current wire contract

The Atlas implementation uses the following bounded transport:

| Item | Contract |
| --- | --- |
| Host buffer | `mncs_host_buffer(i32 capacity) -> i64` |
| Packed buffer result | low 32 bits = offset; high 32 bits = allocated capacity |
| Reset | `mncs_host_buffer_reset()` is valid only after the consumer no longer retains borrowed data |
| Byte descriptor | low 32 bits = offset; high 32 bits = byte length |
| Stream | `atlas_model_init`, repeated `atlas_model_chunk`, then `atlas_model_finish` |
| Plan | `atlas_render(state)` returns an arena cell containing bounded nodes |
| Text | `encoded`, `length`, `start`, `utf8_valid`; bytes are borrowed from the original input |
| Failure | reject closed-world ABI violations and expose static fallback |

The authoritative offsets, capacities, node stride, and memory budget are
generated in `site/assets/atlas-wasm-manifest.json`; hosts must not infer them
from a JavaScript object model or from JSON keys.

## Host safety rules

Hosts must validate the WASM magic and artifact provenance before deployment,
check every returned address against the current memory buffer, use little-endian
reads with explicit width, reject unknown operations and target combinations,
and use `textContent`/DOM node APIs rather than HTML injection. Text decoding
must reject malformed UTF-8 and lone or incorrectly paired UTF-16 surrogate
escapes. A failed check must not partially replace the static surface.

The host is intentionally framework-neutral. A different browser application
can reuse the transport, descriptor, validation, and fallback portions while
providing its own approved operation-to-view mapping. MNCS code must not import
DOM, browser, framework, URL, or event-loop concepts.

