import json
import importlib.util
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AtlasWasmTests(unittest.TestCase):
    def test_stateful_differential_generator_covers_full_fixture(self):
        script = ROOT / "scripts/run_atlas_model_differential.py"
        spec = importlib.util.spec_from_file_location("atlas_differential", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = json.loads(
            (ROOT / "tests/fixtures/atlas-model-differential-corpus.json").read_text(
                encoding="utf-8"
            )
        )
        corpus = module.make_corpus(fixture, ROOT)
        self.assertEqual(corpus["schema_version"], "0.3")
        self.assertEqual(len(corpus["cases"]), len(fixture["bounded_probe"]["cases"]))
        stateful_ids = {case["id"] for case in corpus["stateful_cases"]}
        self.assertIn("complete-atlas", stateful_ids)
        self.assertIn("lone-surrogate", stateful_ids)
        self.assertTrue(all(case["steps"][0]["id"] == "init" for case in corpus["stateful_cases"]))
        self.assertTrue(all(case["steps"][-1]["id"] == "finish" for case in corpus["stateful_cases"]))

    def test_production_page_invokes_shared_runtime_with_static_surface(self):
        page = (ROOT / "site/index.html").read_text(encoding="utf-8")
        self.assertIn('<script type="module" src="assets/app.js"></script>', page)
        for required in (
            'id="atlas-runtime-status"',
            'id="atlas-runtime-project-grid"',
            'id="atlas-runtime-status-grid"',
            'id="atlas-runtime-maturity"',
            'id="atlas-runtime-contract"',
            'id="atlas-runtime-institutional"',
        ):
            self.assertIn(required, page)
        self.assertIn("Open MNCS/WASM diagnostics", page)

    def test_diagnostics_page_retains_explicit_orientation_fallback(self):
        page = (ROOT / "site/experimental-atlas.html").read_text(encoding="utf-8")
        for required in (
            'id="atlas-wasm-fallback"',
            'id="atlas-wasm-project-grid"',
            'id="atlas-wasm-status-grid"',
            'id="atlas-wasm-maturity-model"',
            'id="atlas-wasm-consumer-contract"',
            'id="atlas-wasm-institutional-layer"',
            'data-authority="orientation-only"',
            'src="assets/atlas-wasm.js"',
        ):
            self.assertIn(required, page)
        self.assertNotIn('assets/app.js', page)

    def test_application_semantics_are_not_in_the_thin_hosts(self):
        host = (ROOT / "site/assets/atlas-wasm.js").read_text(encoding="utf-8")
        app = (ROOT / "site/assets/app.js").read_text(encoding="utf-8")
        for forbidden in ("JSON.parse", "response.json(", "innerHTML"):
            self.assertNotIn(forbidden, host)
        for forbidden in (
            "JSON.parse",
            "response.json(",
            "innerHTML",
            "enhanceFromAtlas",
            "renderConsumerContract",
            "renderInstitutionalLayer",
            "maturityClass",
        ):
            self.assertNotIn(forbidden, app)
        for required in (
            "WebAssembly.instantiate",
            "exports.memory",
            "exports.mncs_host_buffer",
            "exports.mncs_host_buffer_reset",
            "atlas_scan_chunk",
            "atlas_model_init",
            "atlas_model_chunk",
            "atlas_model_finish",
            "atlas_render",
            "valueTextAux",
            "MNCS typed Atlas model is invalid or incomplete",
            "Static HTML fallback active",
        ):
            self.assertIn(required, host)

    def test_materialized_modules_are_wasm_binaries(self):
        for name in ("atlas-json-scan.wasm", "atlas-json-projection.wasm", "atlas-model.wasm"):
            artifact = ROOT / "site/assets" / name
            self.assertTrue(artifact.is_file(), name)
            self.assertTrue(artifact.read_bytes().startswith(b"\x00asm"), name)

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

    def test_full_atlas_render_plan_has_real_cardinality_and_typed_semantics(self):
        script = r"""
import { readFile } from "node:fs/promises";
const wasm = await readFile(process.argv[2]);
const atlas = await readFile(process.argv[3]);
const { instance } = await WebAssembly.instantiate(wasm, {});
const e = instance.exports;
const memory = e.memory;
const descriptor = (offset, length) => (BigInt(length) << 32n) | BigInt(offset);
const packed = e.mncs_host_buffer(64);
const offset = Number(packed & 0xffffffffn);
let state = e.atlas_model_init();
for (let index = 0; index < atlas.length; index += 64) {
  const chunk = atlas.subarray(index, index + 64);
  new Uint8Array(memory.buffer).set(chunk, offset);
  state = e.atlas_model_chunk(state, descriptor(offset, chunk.length));
}
const plan = e.atlas_render(state);
const view = new DataView(memory.buffer);
const u32 = (address) => view.getUint32(address, true);
const u64 = (address) => Number(view.getBigUint64(address, true));
if (u32(plan) !== 1 || u64(plan + 16) !== 36 || u64(plan + 32) !== 15 || u64(plan + 40) !== 19) process.exit(2);
const nodes = u32(plan + 24);
const operations = [];
for (let index = 0; index < u64(plan + 16); index += 1) {
  const node = u32(nodes + index * 8);
  operations.push(u32(node));
}
const counts = (code) => operations.filter((value) => value === code).length;
if (counts(1) !== 15 || counts(3) !== 1 || counts(4) !== 5 || counts(5) !== 1 || counts(6) !== 6 || counts(7) !== 5 || counts(8) !== 1) process.exit(3);
const first = u32(nodes + 3 * 8);
if (u64(first + 56) !== 4 || u64(first + 64) !== 1) process.exit(4);
const text = (pointer) => {
  const length = u64(pointer + 8);
  const start = u64(pointer + 16);
  return new TextDecoder().decode(atlas.subarray(start, start + length));
};
if (text(u32(first + 8)) !== "MNCS" || text(u32(first + 72)) !== "experimental") process.exit(5);
console.log("full-atlas-plan-ok");
"""
        completed = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-",
                str(ROOT / "site/assets/atlas-model.wasm"),
                str(ROOT / "site/atlas.json"),
            ],
            input=script,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("full-atlas-plan-ok", completed.stdout)

    def test_manifest_records_production_abi_and_bounded_capacities(self):
        manifest = json.loads(
            (ROOT / "site/assets/atlas-wasm-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["kind"], "mncs-atlas-wasm")
        self.assertEqual(manifest["schema_version"], "0.2")
        lock = json.loads(
            (ROOT / "mncs/mncs-language.lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["build"]["language_revision_lock"], lock["revision"])
        self.assertEqual(manifest["provenance"]["mncs_language"]["commit"], lock["revision"])
        self.assertIn("compiler_identity", manifest["artifacts"]["atlas-model"]["compiler"])
        self.assertEqual(
            manifest["artifacts"]["atlas-model"]["source"]["repository"], "mncs-atlas"
        )
        self.assertEqual(manifest["typed_model_abi"]["module"], "mncs_atlas.model")
        self.assertEqual(manifest["typed_model_abi"]["render_function"], "atlas_render")
        self.assertEqual(manifest["typed_model_abi"]["max_input_bytes"], 65536)
        self.assertEqual(manifest["typed_model_abi"]["capacities"]["projects"], 32)
        self.assertEqual(manifest["typed_model_abi"]["capacities"]["relationships"], 64)
        self.assertEqual(
            manifest["typed_model_abi"]["render_plan"]["node_layout"]["stride_bytes"], 88
        )
        self.assertTrue(manifest["artifacts"]["atlas-model"]["stateful_cases"])
        self.assertEqual(manifest["validation"]["status"], "UNKNOWN")

    def test_full_model_differential_fixture_declares_required_edge_cases(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/atlas-model-differential-corpus.json").read_text(
                encoding="utf-8"
            )
        )
        case_ids = {case["id"] for case in fixture["full_input"]["cases"]}
        self.assertTrue(
            {
                "complete-atlas",
                "truncated-atlas",
                "truncated-at-chunk-boundaries",
                "malformed-json-structure",
                "malformed-utf8-atlas",
                "escaped-unicode",
                "surrogate-pair",
                "lone-surrogate",
                "long-unknown-key",
                "missing-required-sections",
                "malformed-project-record",
                "malformed-relationship",
                "capacity-boundary",
                "one-over-capacity",
                "reordered-object-members",
                "unknown-fields",
                "incomplete-root",
                "empty-collections",
            }.issubset(case_ids)
        )
        self.assertEqual(fixture["full_input"]["chunk_bytes"], 64)
        self.assertIn(65536, fixture["full_input"]["chunk_boundaries"])
        self.assertEqual(fixture["status"], "UNKNOWN")

    def test_root_pages_mirror_is_current(self):
        for relative in (
            "index.html",
            "experimental-atlas.html",
            "assets/app.js",
            "assets/atlas-wasm.js",
            "assets/atlas-model.wasm",
            "assets/atlas-wasm-manifest.json",
        ):
            self.assertEqual(
                (ROOT / "site" / relative).read_bytes(),
                (ROOT / relative).read_bytes(),
                relative,
            )


if __name__ == "__main__":
    unittest.main()
