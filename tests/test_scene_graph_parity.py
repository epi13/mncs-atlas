"""Parity between the scene owner model and the MNCS scalar ABI.

The executable contract is ``mncs/scene-corpus.json``: every case carries
``expected`` values derived from the owner model through
:mod:`scene.mncs_glue`, so ``mncs experiment run`` checks the MNCS module
against owner-defined semantics. These tests pin the derivation itself, the
glue coverage, and the exchanged scene schema (validated against a real
observed demo, not a hand-written example).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mncs"))

import gen_scene_corpus as gen
from scene import mncs_glue as glue
from scene import model


class CorpusDerivationTest(unittest.TestCase):
    def test_checked_in_corpus_matches_fresh_derivation(self) -> None:
        corpus = json.loads((ROOT / "mncs" / "scene-corpus.json").read_text())
        fresh = {"schema_version": "0.1", "name": "scene-abi-v1",
                 "cases": gen.build_cases()}
        self.assertEqual(corpus, fresh)

    def test_every_case_has_an_expectation(self) -> None:
        corpus = json.loads((ROOT / "mncs" / "scene-corpus.json").read_text())
        self.assertTrue(corpus["cases"], "corpus must not be empty")
        for item in corpus["cases"]:
            self.assertEqual(item["expected_status"], "returned", item["id"])
            self.assertEqual(len(item["expected"]), 1, item["id"])
            value = item["expected"][0]
            if "integer" in value:
                self.assertEqual(value["integer"]["type"], {"bits": 64, "signed": True})
                self.assertIsInstance(value["integer"]["value"], int)
            else:
                self.assertIn("boolean", value, item["id"])
                self.assertIsInstance(value["boolean"]["value"], bool)


class GlueCoverageTest(unittest.TestCase):
    def test_query_functions_all_have_cases(self) -> None:
        corpus = json.loads((ROOT / "mncs" / "scene-corpus.json").read_text())
        covered = {item["request"]["target"]["function"] for item in corpus["cases"]}
        for function in ("rect_area", "node_matches", "rects_overlap",
                         "viewport_contains", "confidence_band", "focus_moved",
                         "delta_is_move", "delta_is_quiet"):
            self.assertIn(function, covered, function)

    def test_move_args_projection(self) -> None:
        delta = model.SceneDelta(appeared=1, disappeared=2, moved=3, changed=4, unchanged=5)
        self.assertEqual(glue.move_args(delta), [1, 2, 3, 4, 5])
        self.assertEqual(glue.focus_args(0, 0, 1, 0), [0, 0, 1, 0])
        self.assertEqual(glue.bool_bit(True), 1)
        self.assertEqual(glue.bool_bit(False), 0)

    def test_model_matches_demo_fixture(self) -> None:
        demo = json.loads((ROOT / "tests" / "fixtures" / "scene-demo.json").read_text())
        delta = demo["delta"]
        observed = model.SceneDelta(
            appeared=delta["appeared"], disappeared=delta["disappeared"],
            moved=delta["moved"], changed=delta["changed"], unchanged=delta["unchanged"],
            has_focus=delta["has_focus"], focus_id=delta["focus_id"],
            focus_old_left=delta["focus_old_left"], focus_old_top=delta["focus_old_top"],
            focus_new_left=delta["focus_new_left"], focus_new_top=delta["focus_new_top"])
        self.assertTrue(model.delta_is_move(observed))
        self.assertFalse(model.delta_is_quiet(observed))
        self.assertTrue(model.focus_moved(observed.focus_old_left, observed.focus_old_top,
                                          observed.focus_new_left, observed.focus_new_top))
        node = demo["nodes"][0]
        self.assertTrue(model.viewport_contains(0, 0, 8, 8, node["left"], node["top"],
                                                node["width"], node["height"]))
        self.assertEqual(model.confidence_band(node["confidence"]), 2)


class SceneSchemaTest(unittest.TestCase):
    def test_demo_fixture_validates_against_schema(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema not installed")
        schema = json.loads((ROOT / "schema" / "scene-graph.schema.json").read_text())
        demo = json.loads((ROOT / "tests" / "fixtures" / "scene-demo.json").read_text())
        jsonschema.validate(demo, schema)

    def test_demo_fixture_shape_without_validator(self) -> None:
        demo = json.loads((ROOT / "tests" / "fixtures" / "scene-demo.json").read_text())
        self.assertEqual(demo["schema_version"], "mncs-atlas.scene-graph/1")
        self.assertEqual(len(demo["nodes"]), 1)
        node = demo["nodes"][0]
        self.assertEqual(node["kind"], "rectangle")
        self.assertEqual(node["id"], 0)
        self.assertEqual(demo["delta"]["moved"], 1)
        self.assertTrue(demo["delta"]["has_focus"])
        self.assertIn("provenance", demo)
        self.assertIn("sizes", demo)


if __name__ == "__main__":
    unittest.main()
