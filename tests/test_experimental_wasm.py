import json
from pathlib import Path
import subprocess
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
            "atlas_model_init",
            "atlas_model_chunk",
            "atlas_model_finish",
            "atlas_render",
            "maturityCounts",
            "textContent",
            "BigInt(length)",
            "scanResult !== 1",
        ):
            self.assertIn(required, adapter)
        self.assertNotIn("900000", adapter)
        self.assertNotIn("JSON.parse", adapter)
        self.assertNotIn("response.json(", adapter)
        self.assertNotIn("innerHTML", adapter)
        self.assertNotIn("atlas_project_chunk", adapter)
        self.assertLess(
            adapter.index("if (scanResult !== 1)"),
            adapter.index("const typedModel = modelAtlas"),
        )

    def test_materialized_modules_are_wasm_binaries(self):
        for name in ("atlas-json-scan.wasm", "atlas-json-projection.wasm", "atlas-model.wasm"):
            artifact = ROOT / "site/assets" / name
            self.assertTrue(artifact.is_file(), name)
            self.assertTrue(artifact.read_bytes().startswith(b"\x00asm"), name)

    def test_experimental_page_exposes_real_atlas_surface(self):
        page = (ROOT / "site/experimental-atlas.html").read_text(encoding="utf-8")
        for required in (
            'id="atlas-wasm-project-grid"',
            'id="atlas-wasm-status-grid"',
            'id="atlas-wasm-metrics"',
            'id="atlas-maturity-legend"',
            "Consumer contract",
            "Relationship surface",
        ):
            self.assertIn(required, page)

    def test_model_artifact_instantiates_in_independent_node_runtime(self):
        script = r"""
import { readFile } from "node:fs/promises";
const bytes = await readFile(process.argv[2]);
const { instance } = await WebAssembly.instantiate(bytes, {});
const input = new TextEncoder().encode('{"projects":[{"maturity":"experimental"}]}');
const packed = instance.exports.mncs_host_buffer(input.length);
const offset = Number(packed & 0xffffffffn);
new Uint8Array(instance.exports.memory.buffer).set(input, offset);
const result = instance.exports.atlas_model_probe((BigInt(input.length) << 32n) | BigInt(offset));
if (result !== 1001n) process.exit(1);
console.log("node-wasm-ok");
"""
        completed = subprocess.run(
            ["node", "--input-type=module", "-", str(ROOT / "site/assets/atlas-model.wasm")],
            input=script,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("node-wasm-ok", completed.stdout)

    def test_manifest_records_typed_host_buffer_contract(self):
        manifest = json.loads(
            (ROOT / "site/assets/atlas-wasm-manifest.json").read_text(encoding="utf-8")
        )
        abi = manifest["host_buffer_abi"]
        self.assertEqual(abi["function"], "mncs_host_buffer")
        self.assertEqual(abi["reset_function"], "mncs_host_buffer_reset")
        self.assertEqual(abi["version"], "mncs.host-buffer.v1")
        self.assertEqual(manifest["typed_model_abi"]["render_function"], "atlas_render")
        self.assertEqual(manifest["typed_model_abi"]["arena_pages"], 512)
        self.assertEqual(manifest["validation"]["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
