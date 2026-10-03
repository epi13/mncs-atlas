"""Focused tests for the deterministic Atlas projector and dashboard.

Layers: pure rules, discovery availability, projection determinism and
ordering, validation/sanitization boundary, no-change identity, dashboard
static fallback, and controller safety without publishing anything.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from projector import PROJECTION_SCHEMA
from projector import discover as discover_module
from projector import project as project_module
from projector import render as render_module
from projector import rules, validate as validate_module


def load_bundle(**kwargs):
    return discover_module.discover(atlas_root=ROOT, **kwargs)


class RulesTests(unittest.TestCase):
    def test_unknown_lifecycle_is_explicit(self) -> None:
        self.assertEqual(rules.normalize_lifecycle("active")["lifecycle"], "active")
        unknown = rules.normalize_lifecycle("flying")
        self.assertEqual(unknown["lifecycle"], "unknown")
        self.assertIn("flying", unknown["reason"])
        self.assertEqual(rules.normalize_lifecycle(None)["lifecycle"], "unknown")

    def test_no_evidence_is_never_pass(self) -> None:
        self.assertEqual(rules.verification_state(None)["state"], "UNKNOWN")
        self.assertEqual(rules.verification_state({})["state"], "UNKNOWN")
        declared = rules.verification_state({"surface": "x", "runner": "y"})
        self.assertEqual(declared["state"], "UNKNOWN")
        self.assertIn("without result", declared["reason"])
        self.assertEqual(rules.verification_state({"verdict": "PASS"})["state"], "PASS")
        self.assertEqual(rules.verification_state({"status": "FAIL"})["state"], "FAIL")

    def test_implementation_needs_declared_evidence(self) -> None:
        self.assertEqual(rules.classify_implementation(None)["state"], "unknown")
        self.assertEqual(rules.classify_implementation({})["state"], "unknown")
        known = rules.classify_implementation("bridge-adapter")
        self.assertEqual(known["state"], "bridge-adapter")

    def test_freshness_combinations(self) -> None:
        self.assertEqual(rules.freshness_state([])["status"], "unavailable")
        self.assertEqual(rules.freshness_state(["present", "present"])["status"], "complete")
        self.assertEqual(rules.freshness_state(["missing"])["status"], "unavailable")
        self.assertEqual(
            rules.freshness_state(["present", "missing"])["status"], "partial"
        )
        for statuses in ([], ["present"], ["missing"], ["present", "invalid"]):
            self.assertNotIn(rules.freshness_state(statuses)["status"],
                             ("current", "stale"))


class DiscoveryTests(unittest.TestCase):
    def test_missing_roots_become_unknown_sources(self) -> None:
        bundle = load_bundle(
            workspace_root=ROOT / "tests" / "fixtures",
            commons_root=ROOT / "tests" / "fixtures" / "no-commons",
            store_root=ROOT / "tests" / "fixtures" / "no-store",
        )
        by_id = {source.id: source for source in bundle.sources}
        self.assertEqual(by_id["commons-participation"].status, "missing")
        self.assertEqual(by_id["store-verification"].status, "missing")
        self.assertEqual(by_id["atlas-catalog"].status, "present")
        payload = project_module.project(bundle)
        self.assertEqual(payload["freshness"]["status"], "partial")
        self.assertEqual(validate_module.validate(payload), [])


class ProjectionTests(unittest.TestCase):
    def test_deterministic_same_inputs(self) -> None:
        first = project_module.project(load_bundle())
        second = project_module.project(load_bundle())
        self.assertEqual(first["semantic_hash"], second["semantic_hash"])
        self.assertEqual(first, second)

    def test_stable_ordering(self) -> None:
        payload = project_module.project(load_bundle())
        ids = [entry["id"] for entry in payload["ecosystem"]["projects"]]
        self.assertEqual(ids, sorted(ids))
        pressure_ids = [item["id"] for item in payload["pressures"]["listed"]]
        self.assertEqual(pressure_ids, sorted(str(item) for item in pressure_ids))

    def test_semantic_hash_verifies(self) -> None:
        payload = project_module.project(load_bundle())
        self.assertTrue(render_module.verify_semantic_hash(payload))
        tampered = dict(payload)
        tampered["freshness"] = {"status": "complete", "reason": "forged"}
        self.assertFalse(render_module.verify_semantic_hash(tampered))

    def test_no_change_detection_ignores_timestamps(self) -> None:
        payload = project_module.project(load_bundle())
        self.assertTrue(render_module.semantic_changed(None, payload["semantic_hash"]))
        self.assertFalse(
            render_module.semantic_changed(
                {"semantic_hash": payload["semantic_hash"]}, payload["semantic_hash"]
            )
        )
        self.assertTrue(
            render_module.semantic_changed({"semantic_hash": "sha256:other"}, payload["semantic_hash"])
        )

    def test_projection_covers_mnel_transition_and_models(self) -> None:
        payload = project_module.project(load_bundle())
        by_id = {entry["id"]: entry for entry in payload["ecosystem"]["projects"]}
        self.assertEqual(by_id["mnel"]["lifecycle"], "retired")
        self.assertIn("mncs-models", by_id)
        self.assertEqual(by_id["mncs-models"]["lifecycle"], "experimental")


class BoundaryTests(unittest.TestCase):
    def test_validate_rejects_missing_and_duplicates(self) -> None:
        payload = project_module.project(load_bundle())
        broken = {key: value for key, value in payload.items() if key != "sources"}
        self.assertTrue(any("sources" in error for error in validate_module.validate(broken)))
        duplicated = json.loads(json.dumps(payload))
        duplicated["ecosystem"]["projects"].append(
            dict(duplicated["ecosystem"]["projects"][0])
        )
        self.assertTrue(
            any("duplicate" in error for error in validate_module.validate(duplicated))
        )

    def test_sanitize_drops_unknown_top_level(self) -> None:
        payload = project_module.project(load_bundle())
        payload["private_notes"] = "must not publish"
        clean = validate_module.sanitize(payload)
        self.assertNotIn("private_notes", clean)
        self.assertEqual(clean["semantic_hash"], payload["semantic_hash"])

    def test_sanitize_rejects_unsanitizable_values(self) -> None:
        with self.assertRaises(ValueError):
            validate_module.sanitize({"sources": [object()]})


class DashboardTests(unittest.TestCase):
    def test_dashboard_page_has_markers_and_fallback(self) -> None:
        page = (ROOT / "site" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn(render_module.NOSCRIPT_BEGIN, page)
        self.assertIn(render_module.NOSCRIPT_END, page)
        self.assertIn("<noscript>", page)
        self.assertIn("mncs-atlas", page)
        self.assertTrue((ROOT / "site" / "assets" / "dashboard.js").is_file())

    def test_noscript_refresh_is_idempotent(self) -> None:
        import tempfile

        payload = project_module.project(load_bundle())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dashboard.html"
            target.write_text(
                (ROOT / "site" / "dashboard.html").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            # First render converges the copy; the second must report no change
            # and leave bytes untouched. The committed tree is never written.
            render_module.refresh_noscript(target, payload)
            before = target.read_bytes()
            self.assertFalse(render_module.refresh_noscript(target, payload))
            self.assertEqual(target.read_bytes(), before)

    def test_committed_dashboard_json_validates(self) -> None:
        path = ROOT / "site" / "dashboard.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_module.validate(data["projection"]), [])
        self.assertTrue(render_module.verify_envelope(data))


def load_controller():
    spec = importlib.util.spec_from_file_location(
        "atlas_refresh", ROOT / "scripts" / "atlas_refresh.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ControllerTests(unittest.TestCase):
    def test_generated_allowlist(self) -> None:
        controller = load_controller()
        original = controller.git_porcelain
        try:
            controller.git_porcelain = lambda: [" M site/dashboard.json", " M README.md"]
            offenders = controller.dirty_outside_generated()
            self.assertEqual(offenders, [" M README.md"])
            controller.git_porcelain = lambda: [" M site/dashboard.json"]
            self.assertEqual(controller.dirty_outside_generated(), [])
        finally:
            controller.git_porcelain = original

    def test_schedule_units_present_and_templated(self) -> None:
        service = (ROOT / "systemd" / "user" / "mncs-atlas-refresh.service").read_text(
            encoding="utf-8"
        )
        timer = (ROOT / "systemd" / "user" / "mncs-atlas-refresh.timer").read_text(
            encoding="utf-8"
        )
        self.assertIn("@ATLAS_ROOT@", service)
        self.assertIn("OnCalendar=Mon *-*-* 07:13:00", timer)
        self.assertIn("mncs-atlas-refresh.service", timer)

    def test_controller_check_is_dry_run(self) -> None:
        before = {
            path: Path(ROOT / path).read_bytes()
            for path in ("site/dashboard.json", "site/dashboard.html")
        }
        controller = load_controller()
        self.assertEqual(controller.cmd_check(), 0)
        for path, content in before.items():
            self.assertEqual(Path(ROOT / path).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
