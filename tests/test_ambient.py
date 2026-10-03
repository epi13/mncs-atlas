"""Ambient semantic renderers: model-fed Atlas projections without rescans.

Covers the repo-owned renderer entries (dashboard, noscript, registry,
registry page), bundle assembly from observed values, wildcard member
tolerance, journal parity, determinism, and the availability-only
freshness vocabulary.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from projector import ambient as ambient_module
from projector import project as project_module
from projector import render as render_module
from projector import validate as validate_module
from registry.model import build_registry, read_json


def dashboard_model(values, statuses=None):
    statuses = statuses or {}
    sources = [{"slot": slot, "status": statuses.get(slot, "present"),
                "identity": "sha256:test-" + slot,
                "reason": "readable"}
               for slot in values]
    return {"schema_version": "mncs.semantic-state/1",
            "identity": "sha256:test-model",
            "values": dict(values), "sources": sources,
            "renderer_entry": {"module": "projector/ambient.py",
                               "callable": "render_dashboard"}}


def minimal_values():
    catalog = {"schema_version": "mncs-atlas.project-catalog/v1",
               "description": "test", "projects": []}
    return {"catalog": catalog, "compiled": {}, "manifests": [],
            "participation": {}, "architecture": {}, "edges": {},
            "deltas": {}, "verification": {}, "native_status": {},
            "pressures": [], "store_verification": {},
            "store_native_status": {}, "journal": []}


class BundleTests(unittest.TestCase):
    def test_bundle_assembles_every_declared_source(self) -> None:
        bundle = ambient_module.bundle_from_model(dashboard_model(minimal_values()))
        ids = [source.id for source in bundle.sources]
        self.assertEqual(ids, ["atlas-catalog", "atlas-compiled",
                               "workspace-manifests", "commons-participation",
                               "commons-architecture", "commons-edges",
                               "commons-deltas", "commons-verification",
                               "commons-native-status", "commons-pressures",
                               "store-verification", "store-native-status",
                               "journal-head"])

    def test_wildcard_rows_become_reported_manifest_entries(self) -> None:
        values = minimal_values()
        values["manifests"] = [
            {"repository": "mncs-b", "status": "present",
             "reason": "observed",
             "value": {"repository": "mncs-b", "revision": 3}},
            {"repository": "mncs-a", "status": "missing",
             "reason": "file not present", "value": None},
            {"repository": "mncs-c", "status": "invalid",
             "reason": "unparseable subject", "value": None}]
        bundle = ambient_module.bundle_from_model(dashboard_model(values))
        manifests = bundle.by_id("workspace-manifests")
        assert manifests is not None
        self.assertEqual(manifests.status, "present")
        self.assertEqual(len(manifests.payload), 3)
        by_checkout = {row["checkout"]: row for row in manifests.payload}
        self.assertEqual(by_checkout["mncs-b"]["manifest"]["revision"], 3)
        self.assertIsNone(by_checkout["mncs-a"]["manifest"])
        self.assertEqual(by_checkout["mncs-c"]["status"], "invalid")

    def test_missing_expansion_is_explicit_never_silent(self) -> None:
        values = minimal_values()
        values["manifests"] = None
        bundle = ambient_module.bundle_from_model(
            dashboard_model(values, {"manifests": "missing"}))
        manifests = bundle.by_id("workspace-manifests")
        assert manifests is not None
        self.assertEqual(manifests.status, "missing")
        self.assertIsNone(manifests.payload)

    def test_journal_names_match_discovery_semantics(self) -> None:
        values = minimal_values()
        values["journal"] = [{"file": "je-002.json", "record": {}},
                             {"file": "je-001.json", "record": {}}]
        bundle = ambient_module.bundle_from_model(dashboard_model(values))
        head = bundle.by_id("journal-head")
        assert head is not None
        self.assertEqual(head.status, "present")
        self.assertEqual(head.payload, {"count": 2, "latest": "je-002.json"})
        self.assertEqual(head.reason, "2 events")

    def test_empty_journal_matches_discovery_semantics(self) -> None:
        bundle = ambient_module.bundle_from_model(dashboard_model(minimal_values()))
        head = bundle.by_id("journal-head")
        assert head is not None
        self.assertEqual(head.status, "missing")
        self.assertEqual(head.reason, "no journal events published")

    def test_journal_ignores_non_event_json_records(self) -> None:
        values = minimal_values()
        values["journal"] = [{"file": "index.json", "record": {}},
                             {"file": "je-002.json", "record": {}},
                             {"file": "notes.json", "record": {}},
                             {"file": "je-001.json", "record": {}}]
        bundle = ambient_module.bundle_from_model(dashboard_model(values))
        head = bundle.by_id("journal-head")
        assert head is not None
        self.assertEqual(head.status, "present")
        self.assertEqual(head.payload, {"count": 2, "latest": "je-002.json"})
        self.assertEqual(head.reason, "2 events")


class DashboardRenderTests(unittest.TestCase):
    def test_full_world_renders_with_complete_availability(self) -> None:
        values = minimal_values()
        values["journal"] = [{"file": "je-001.json", "record": {}}]
        content = ambient_module.render_dashboard(dashboard_model(values))
        data = json.loads(content)
        self.assertNotIn("generated_at", json.dumps(data["envelope"]))
        self.assertEqual(data["envelope"]["source_epoch"], "sha256:test-model")
        self.assertIn("manifests", data["envelope"]["observed_sources"])
        payload = data["projection"]
        self.assertEqual(payload["freshness"]["status"], "complete")
        self.assertTrue(render_module.verify_envelope(data))
        self.assertEqual(validate_module.validate(payload), [])

    def test_empty_world_renders_with_unavailable_freshness(self) -> None:
        values = {slot: None for slot in minimal_values()}
        statuses = dict.fromkeys(values, "missing")
        content = ambient_module.render_dashboard(dashboard_model(values, statuses))
        payload = json.loads(content)["projection"]
        self.assertEqual(payload["freshness"]["status"], "unavailable")
        self.assertEqual(validate_module.validate(payload), [])

    def test_partial_availability_never_claims_currency(self) -> None:
        values = minimal_values()
        values["verification"] = None
        content = ambient_module.render_dashboard(
            dashboard_model(values, {"verification": "missing"}))
        payload = json.loads(content)["projection"]
        self.assertEqual(payload["freshness"]["status"], "partial")
        self.assertNotIn(payload["freshness"]["status"], ("current", "stale"))

    def test_render_is_deterministic(self) -> None:
        model = dashboard_model(minimal_values())
        self.assertEqual(ambient_module.render_dashboard(model),
                         ambient_module.render_dashboard(model))

    def test_noscript_region_has_table_and_fallback_tags(self) -> None:
        region = ambient_module.render_noscript(dashboard_model(minimal_values()))
        self.assertTrue(region.startswith("\n<noscript>\n"))
        self.assertTrue(region.endswith("\n</noscript>\n"))
        self.assertIn("<table>", region)
        self.assertIn("full data in dashboard.json", region)


class RegistryRenderTests(unittest.TestCase):
    def _registry_values(self):
        directory = ROOT / "registry"
        return {
            "catalog": read_json(directory / "project-catalog.json"),
            "claims": read_json(directory / "capability-claims.json"),
            "decisions": read_json(directory / "decisions.json"),
            "snapshot": read_json(directory / "manifest-snapshot.json"),
            "config": read_json(directory / "config.json"),
            "own_manifest": read_json(ROOT / ".mncs" / "project.json"),
        }

    def test_render_matches_injected_cli_build_exactly(self) -> None:
        values = self._registry_values()
        model = {"schema_version": "mncs.semantic-state/1",
                 "identity": "sha256:test-registry", "values": values,
                 "sources": [], "renderer_entry": {
                     "module": "projector/ambient.py",
                     "callable": "render_registry"}}
        expected = build_registry(
            root=ROOT, output=None,
            live_manifests=[(values["own_manifest"],
                             "repository:.mncs/project.json")],
            inputs={key: values[key] for key in
                    ("catalog", "claims", "decisions", "snapshot", "config")})
        self.assertEqual(json.loads(ambient_module.render_registry(model)), expected)

    def test_render_matches_cli_serialization_byte_for_byte(self) -> None:
        values = self._registry_values()
        model = {"schema_version": "mncs.semantic-state/1",
                 "identity": "sha256:test-registry-bytes", "values": values,
                 "sources": [], "renderer_entry": {
                     "module": "projector/ambient.py",
                     "callable": "render_registry"}}
        expected = build_registry(
            root=ROOT, output=None,
            live_manifests=[(values["own_manifest"],
                             "repository:.mncs/project.json")],
            inputs={key: values[key] for key in
                    ("catalog", "claims", "decisions", "snapshot", "config")})
        self.assertEqual(ambient_module.render_registry(model),
                         json.dumps(expected, ensure_ascii=False, indent=2) + "\n")

    def test_registry_page_renders_compiled_graph(self) -> None:
        compiled = json.loads((ROOT / "registry" / "compiled.json").read_text())
        model = {"schema_version": "mncs.semantic-state/1",
                 "identity": "sha256:test-page",
                 "values": {"compiled": compiled}, "sources": []}
        page = ambient_module.render_registry_page(model)
        self.assertIn("<!doctype html>", page)
        self.assertIn("Family Registry", page)
        self.assertIn(compiled["registry_hash"], page)

    def test_registry_page_rejects_absent_compilation(self) -> None:
        model = {"schema_version": "mncs.semantic-state/1",
                 "identity": "sha256:test-page",
                 "values": {"compiled": None}, "sources": []}
        with self.assertRaises(ValueError):
            ambient_module.render_registry_page(model)


if __name__ == "__main__":
    unittest.main()
