import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExperimentalWasmTests(unittest.TestCase):
    def test_experimental_page_has_static_fallback_and_explicit_boundary(self):
        page = (ROOT / "site/experimental-atlas.html").read_text(encoding="utf-8")
        self.assertIn('id="atlas-wasm-fallback"', page)
        self.assertIn('data-authority="orientation-only"', page)
        self.assertIn('src="assets/atlas-wasm.js"', page)
        self.assertNotIn('assets/app.js', page)

    def test_host_adapter_uses_bytes_and_real_wasm_exports(self):
        adapter = (ROOT / "site/assets/atlas-wasm.js").read_text(encoding="utf-8")
        for required in (
            "arrayBuffer",
            "WebAssembly.instantiate",
            "exports.memory",
            "exports.mncs_host_buffer",
            "exports.mncs_host_buffer_reset",
            "mncs_host_buffer",
            "atlas_scan_chunk",
            "atlas_project_chunk",
            "BigInt(length)",
            "scanResult !== 1",
        ):
            self.assertIn(required, adapter)
        self.assertNotIn("900000", adapter)
        self.assertNotIn("JSON.parse", adapter)
        self.assertNotIn("response.json(", adapter)
        self.assertEqual(adapter.count("WebAssembly.instantiate(moduleBytes, {})"), 1)
        self.assertLess(
            adapter.index("if (scanResult !== 1)"),
            adapter.index("const projections = await projectAtlas"),
        )

    def test_materialized_modules_are_wasm_binaries(self):
        for name in ("atlas-json-scan.wasm", "atlas-json-projection.wasm"):
            artifact = ROOT / "site/assets" / name
            self.assertTrue(artifact.is_file(), name)
            self.assertTrue(artifact.read_bytes().startswith(b"\x00asm"), name)

    def test_manifest_records_typed_host_buffer_contract(self):
        manifest = json.loads(
            (ROOT / "site/assets/atlas-wasm-manifest.json").read_text(encoding="utf-8")
        )
        abi = manifest["host_buffer_abi"]
        self.assertEqual(abi["function"], "mncs_host_buffer")
        self.assertEqual(abi["reset_function"], "mncs_host_buffer_reset")
        self.assertEqual(abi["version"], "mncs.host-buffer.v1")


if __name__ == "__main__":
    unittest.main()
