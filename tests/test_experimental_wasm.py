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
            "atlas_scan_chunk",
            "atlas_project_chunk",
            "BigInt(length)",
            "DATA_OFFSET = 900000",
        ):
            self.assertIn(required, adapter)
        self.assertNotIn("JSON.parse", adapter)
        self.assertNotIn("response.json(", adapter)

    def test_materialized_modules_are_wasm_binaries(self):
        for name in ("atlas-json-scan.wasm", "atlas-json-projection.wasm"):
            artifact = ROOT / "site/assets" / name
            self.assertTrue(artifact.is_file(), name)
            self.assertTrue(artifact.read_bytes().startswith(b"\x00asm"), name)


if __name__ == "__main__":
    unittest.main()
