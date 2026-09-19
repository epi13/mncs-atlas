"""Machine registry invariants, deterministic compilation, and query surface."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from registry.model import (
    ROOT,
    RegistryError,
    build_registry,
    canonical_bytes,
    load_registry,
    validate_manifest,
    validate_registry,
)


class RegistryTests(unittest.TestCase):
    def test_compiled_registry_is_valid_and_schema_conformant(self) -> None:
        registry = load_registry(ROOT / "registry/compiled.json")
        self.assertEqual(validate_registry(registry), [])
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional for the source checkout")
        schema = json.loads((ROOT / "schema/registry.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(registry, schema)

    def test_real_registry_has_family_scale_coverage(self) -> None:
        registry = load_registry()
        self.assertGreaterEqual(len(registry["projects"]), 40)
        self.assertGreaterEqual(len(registry["capabilities"]), 30)
        self.assertGreaterEqual(len(registry["decisions"]), 8)
        self.assertIn("mncs-numerics", {row["id"] for row in registry["projects"]})
        self.assertIn("mncs-doctor", {row["id"] for row in registry["projects"]})
        self.assertIn("mncs-control-mcp", {row["id"] for row in registry["projects"]})
        self.assertIn("mncs-control", {row["id"] for row in registry["projects"]})

    def test_build_is_deterministic(self) -> None:
        first = build_registry(output=None)
        second = build_registry(output=None)
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        self.assertEqual(first["registry_hash"], second["registry_hash"])
        self.assertEqual(first["registry_revision"], first["registry_hash"][:16])
        self.assertEqual([row["id"] for row in first["projects"]], sorted(row["id"] for row in first["projects"]))
        self.assertEqual([row["id"] for row in first["capabilities"]], sorted(row["id"] for row in first["capabilities"]))
        self.assertEqual([row["id"] for row in first["decisions"]], sorted(row["id"] for row in first["decisions"]))
        self.assertEqual(
            [(edge["from"], edge["kind"], edge["to"]) for edge in first["edges"]],
            sorted((edge["from"], edge["kind"], edge["to"]) for edge in first["edges"]),
        )

    def test_invalid_manifest_is_rejected(self) -> None:
        manifest = {
            "schema_version": "wrong",
            "repository": "Bad ID",
            "revision": 0,
            "contracts": {"provides": [], "consumes": [], "tests": []},
        }
        errors = validate_manifest(manifest, "fixture")
        self.assertTrue(any("schema_version" in error for error in errors))
        self.assertTrue(any("stable project id" in error for error in errors))
        self.assertTrue(any("positive integer" in error for error in errors))

    def test_duplicate_authority_and_unknown_reference_fail_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("config.json", "project-catalog.json", "capability-claims.json", "decisions.json", "manifest-snapshot.json"):
                source = ROOT / "registry" / name
                target = root / "registry" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            claims_path = root / "registry/capability-claims.json"
            claims = json.loads(claims_path.read_text(encoding="utf-8"))
            claims["capabilities"][0]["claims"].append({"project": "unknown-project", "role": "canonical-authority"})
            claims["capabilities"][0]["claims"].append({"project": "mncs-validator-rs", "role": "canonical-authority"})
            claims_path.write_text(json.dumps(claims), encoding="utf-8")
            with self.assertRaisesRegex(RegistryError, "unknown project"):
                build_registry(root=root, output=None)
            claims["capabilities"][0]["claims"].pop(0)
            claims_path.write_text(json.dumps(claims), encoding="utf-8")
            with self.assertRaisesRegex(RegistryError, "exactly one canonical authority"):
                build_registry(root=root, output=None)

    def test_registry_hash_detects_tampering(self) -> None:
        registry = load_registry()
        registry["projects"][0]["name"] = "tampered"
        self.assertIn("registry_hash", validate_registry(registry)[0])

    def test_context_capsule_is_compact_and_identifies_checkout(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "registry", "context", "../mncs-numerics", "--json"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        capsule = json.loads(result.stdout)
        self.assertEqual(capsule["schema_version"], "mncs-atlas.context-capsule/v1")
        self.assertEqual(capsule["project"]["id"], "mncs-numerics")
        self.assertEqual(capsule["identified_by"], "repository-manifest")
        self.assertIn("numeric-primitives", capsule["project"]["canonical_capabilities"])
        self.assertIn("language semantics", " ".join(capsule["project"]["do_not_reimplement"]))
        self.assertLess(len(result.stdout.split()), 260)

    def test_owner_and_decision_queries_are_machine_readable(self) -> None:
        owner = subprocess.run(
            [sys.executable, "-m", "registry", "owner", "source-migration"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(owner.stdout)["canonical_authority"], "mncs-doctor")
        decisions = subprocess.run(
            [sys.executable, "-m", "registry", "decisions", "numerics"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rows = json.loads(decisions.stdout)
        self.assertTrue(any(row["id"] == "NUMERICS-ARCH-0001" for row in rows))

    def test_alias_mapping_keeps_control_projects_distinct(self) -> None:
        registry = load_registry()
        local = next(row for row in registry["projects"] if row["id"] == "mncs-control")
        operator = next(row for row in registry["projects"] if row["id"] == "mncs-control-mcp")
        self.assertIn("mncs-language", local["dependencies"])
        self.assertNotEqual(local["repository"], operator["repository"])
        operator_manifest = operator["manifest"]
        self.assertIsNotNone(operator_manifest)
        self.assertTrue(any(item["id"].startswith("mncs-control-mcp.") for item in operator_manifest["provides"]))

    def test_workspace_manifest_overrides_pinned_snapshot(self) -> None:
        registry = build_registry(output=None, workspace_roots=[ROOT.parent / "mncs-harness"])
        harness = next(row for row in registry["projects"] if row["id"] == "mncs-harness")
        self.assertEqual(harness["manifest"]["origin"], "repository:.mncs/project.json")
        self.assertEqual(harness["manifest"]["revision"], 4)

    def test_generated_human_registry_view_is_derived(self) -> None:
        rendered = subprocess.run(
            [sys.executable, "scripts/render_registry_page.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("rendered site/registry.html", rendered.stdout)
        page = (ROOT / "site/registry.html").read_text(encoding="utf-8")
        registry = load_registry()
        self.assertIn(registry["registry_hash"], page)
        self.assertIn(f"{len(registry['projects'])}</strong> projects", page)

    def test_fresh_validation_detects_changed_inputs(self) -> None:
        current = subprocess.run(
            [sys.executable, "-m", "registry", "validate", "--fresh"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(current.stdout)["status"], "PASS")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compiled.json"
            path.write_bytes((ROOT / "registry/compiled.json").read_bytes())
            registry = json.loads(path.read_text(encoding="utf-8"))
            registry["projects"][0]["name"] = "stale"
            path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertTrue(validate_registry(registry))


if __name__ == "__main__":
    unittest.main()
