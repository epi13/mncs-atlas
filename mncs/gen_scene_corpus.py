#!/usr/bin/env python3
"""Generate the executable MNCS scene-graph corpus with model-derived expectations.

The corpus (``mncs/scene-corpus.json``) is the executable contract for
``mncs/scene_graph.mncs``: every case carries ``expected`` values derived
from the owner model (:mod:`scene.model`) through (:mod:`scene.mncs_glue`),
so ``mncs experiment run`` verifies the MNCS module against owner-defined
semantics instead of against itself.

Regenerate after any model, glue, or scenario change::

    python3 mncs/gen_scene_corpus.py --check   # CI: fail on drift
    python3 mncs/gen_scene_corpus.py           # rewrite the corpus
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scene import mncs_glue as glue
from scene import model

CORPUS_PATH = ROOT / "mncs" / "scene-corpus.json"
MODULE = "mncs_atlas.scene_graph"
I64 = {"bits": 64, "signed": True}


def arg(value: int) -> dict:
    return {"integer": {"value": value, "type": dict(I64)}}


def case(case_id: str, function: str, arguments: list[int], expected: int,
         step_budget: int = 16384) -> dict:
    return {
        "id": case_id,
        "request": {
            "schema_version": "0.1",
            "target": {"module": MODULE, "function": function},
            "arguments": [arg(value) for value in arguments],
            "step_budget": step_budget,
        },
        "expected": [arg(expected)],
        "expected_status": "returned",
    }


def bool_case(case_id: str, function: str, arguments: list[int], expected: bool) -> dict:
    return {
        "id": case_id,
        "request": {
            "schema_version": "0.1",
            "target": {"module": MODULE, "function": function},
            "arguments": [arg(value) for value in arguments],
            "step_budget": 16384,
        },
        "expected": [{"boolean": {"value": expected}}],
        "expected_status": "returned",
    }


def build_cases() -> list[dict]:
    cases: list[dict] = []
    # Geometry over the real observed demo bounds (rect at (0,0,7,6)).
    cases.append(case("area-demo", "rect_area", [7, 6], model.rect_area(7, 6)))
    cases.append(case("area-zero", "rect_area", [0, 6], model.rect_area(0, 6)))
    cases.append(bool_case("match-same", "node_matches", [0, 0], model.node_matches(0, 0)))
    cases.append(bool_case("match-other", "node_matches", [0, 1], model.node_matches(0, 1)))
    cases.append(bool_case(
        "overlap-demo", "rects_overlap", [0, 0, 7, 6, 1, 0, 7, 6],
        model.rects_overlap(0, 0, 7, 6, 1, 0, 7, 6)))
    cases.append(bool_case(
        "overlap-disjoint", "rects_overlap", [0, 0, 2, 2, 5, 5, 2, 2],
        model.rects_overlap(0, 0, 2, 2, 5, 5, 2, 2)))
    cases.append(bool_case(
        "overlap-touching", "rects_overlap", [0, 0, 2, 2, 2, 0, 2, 2],
        model.rects_overlap(0, 0, 2, 2, 2, 0, 2, 2)))
    cases.append(bool_case(
        "overlap-zero-area", "rects_overlap", [0, 0, 0, 6, 0, 0, 7, 6],
        model.rects_overlap(0, 0, 0, 6, 0, 0, 7, 6)))
    cases.append(bool_case(
        "viewport-demo", "viewport_contains", [0, 0, 8, 8, 0, 0, 7, 6],
        model.viewport_contains(0, 0, 8, 8, 0, 0, 7, 6)))
    cases.append(bool_case(
        "viewport-outside", "viewport_contains", [0, 0, 4, 4, 0, 0, 7, 6],
        model.viewport_contains(0, 0, 4, 4, 0, 0, 7, 6)))
    for confidence, label in ((100, "certain"), (60, "firm"), (20, "low"), (0, "zero")):
        cases.append(case(f"band-{label}", "confidence_band", [confidence],
                          model.confidence_band(confidence)))
    # The real observed delta: moved=1 with focus (0,0)->(1,0).
    demo_delta = model.SceneDelta(appeared=0, disappeared=0, moved=1, changed=0,
                                  unchanged=0, has_focus=True, focus_id=0,
                                  focus_old_left=0, focus_old_top=0,
                                  focus_new_left=1, focus_new_top=0)
    cases.append(bool_case("delta-demo-is-move", "delta_is_move",
                           glue.move_args(demo_delta), model.delta_is_move(demo_delta)))
    cases.append(bool_case("delta-demo-not-quiet", "delta_is_quiet",
                           glue.move_args(demo_delta), model.delta_is_quiet(demo_delta)))
    quiet = model.SceneDelta(appeared=0, disappeared=0, moved=0, changed=0, unchanged=3)
    cases.append(bool_case("delta-quiet", "delta_is_quiet",
                           glue.move_args(quiet), model.delta_is_quiet(quiet)))
    cases.append(bool_case("delta-quiet-not-move", "delta_is_move",
                           glue.move_args(quiet), model.delta_is_move(quiet)))
    cases.append(bool_case("focus-demo-moved", "focus_moved",
                           glue.focus_args(0, 0, 1, 0), model.focus_moved(0, 0, 1, 0)))
    cases.append(bool_case("focus-same", "focus_moved",
                           glue.focus_args(2, 3, 2, 3), model.focus_moved(2, 3, 2, 3)))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    corpus = {"schema_version": "0.1", "name": "scene-abi-v1", "cases": build_cases()}
    if args.check:
        current = json.loads(CORPUS_PATH.read_text())
        if current != corpus:
            print("scene corpus drift: regenerate with mncs/gen_scene_corpus.py", file=sys.stderr)
            return 1
        return 0
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
