# Scene graph consumer interface

Atlas consumes visual structure; it never derives it from pixels. Perception
lives in the MNCS language workspace (`mncs.core.vision.v1` observes,
`mncs.core.image.v1` renders); Atlas receives persistent scene graphs and
frame deltas and queries them through `mncs_atlas.scene_graph`.

## Data flow

```text
screen/frame
  -> MNCS renderer (semantic description -> pixels)
  -> MNCS visual observer (pixels -> scene graph)
  -> persistent MNCS scene graph + frame delta
  -> Atlas / agent (schema + query module, this repo)
```

## Exchange schema

`schema/scene-graph.schema.json` (`mncs-atlas.scene-graph/1`) is the
machine-native agent context: nodes with stable ids, kinds
(rectangle/line/blob), bounds, confidence, plus a delta with appeared /
disappeared / moved / changed / unchanged counts and a focus record
(old/new top-left of the first moved or changed node). English prose is
never canonical; human renderings are debug-only.

## Query module

`mncs/scene_graph.mncs` (`mncs_atlas.scene_graph`, scalar i64 ABI) answers
what agents ask about an observed scene: identity match, area, overlap,
viewport containment, confidence bands, focus displacement, and delta
classification (`delta_is_move`, `delta_is_quiet`). Its executable contract
is `mncs/scene-corpus.json`, derived from the owner model in `scene/`:

```text
python3 mncs/gen_scene_corpus.py --check   # CI: fail on drift
python3 mncs/gen_scene_corpus.py           # regenerate
MNCS_LIBRARY_PATH=<mncs-language>/library mncs experiment run \
  mncs/scene_graph.mncs --backend mncs-portable-wasm-mvp \
  --corpus mncs/scene-corpus.json --output-dir <dir>
```

## Observed demo

`tests/fixtures/scene-demo.json` is a real renderer -> observer -> delta
run, not a hand-written example: frame A renders an outlined rectangle at
(1,1,6,5); frame B moves it one pixel right; the observer returns a
rectangle candidate with stable id 0 in both frames; the delta reports
`moved: 1` with focus `(0,0) -> (1,0)`.

## Representation sizes (measured, 8x8 demo)

| Representation | Bytes |
| --- | --- |
| Raw frame pixels (binary, one frame) | 64 |
| Scene nodes JSON (one node) | 108 |
| Frame delta JSON | 191 |

At 8x8 the JSON structural forms are larger than raw pixels: JSON is
verbose and one node carries identity, kind, bounds, and confidence. The
structural value is not byte compression at this scale — it is identity
(stable ids across frames), kinds with confidence, and change semantics:
an unchanged frame's delta is a few counts, so retransmission scales with
changes, not pixels. Binary encodings would shrink the JSON forms further;
that optimization is recorded as future work, not claimed here.
