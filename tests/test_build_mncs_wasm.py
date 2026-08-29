import hashlib
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_mncs_wasm.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_mncs_wasm", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load WASM builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AtomicWasmBuildTests(unittest.TestCase):
    def test_later_artifact_failure_does_not_touch_published_set(self):
        builder = load_builder()
        wasm = b"\x00asm\x01\x00\x00\x00"
        result = {
            "status": "PASS",
            "cases": [{"case_id": "fixture", "expectation_met": True}],
            "artifact": {
                "artifact_kind": "wasm_module",
                "bytes_hex": wasm.hex(),
                "bytes_sha256": hashlib.sha256(wasm).hexdigest(),
                "exports": [],
            },
            "compiler_study": {"compiler_identity": "fixture-compiler"},
        }

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            live = root / "site" / "assets"
            staged = root / "staged" / "assets"
            live.mkdir(parents=True)
            staged.mkdir(parents=True)
            old = {
                f"{name}.wasm": f"old-{name}".encode("ascii")
                for name, _, _ in builder.ARTIFACTS
            }
            old[builder.MANIFEST_NAME] = b"old-manifest"
            for name, contents in old.items():
                (live / name).write_bytes(contents)

            with self.assertRaisesRegex(RuntimeError, "later artifact"):
                for name, _, _ in builder.ARTIFACTS:
                    if name == "atlas-json-projection":
                        raise RuntimeError("later artifact build failed")
                    builder.materialize_artifact(name, result, staged)

            self.assertEqual(
                {name: (live / name).read_bytes() for name in old},
                old,
            )

    def test_publication_copies_complete_set_to_each_destination(self):
        builder = load_builder()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / "staged"
            first = root / "site" / "assets"
            second = root / "mirror" / "assets"
            staged.mkdir(parents=True)
            for name, _, _ in builder.ARTIFACTS:
                (staged / f"{name}.wasm").write_bytes(b"\x00asm\x01\x00\x00\x00" + name.encode())
            (staged / builder.MANIFEST_NAME).write_text("{}\n", encoding="utf-8")

            builder.publish_artifact_set(staged, [first, second])

            for name, _, _ in builder.ARTIFACTS:
                self.assertEqual(
                    (first / f"{name}.wasm").read_bytes(),
                    (second / f"{name}.wasm").read_bytes(),
                )
            self.assertEqual(
                (first / builder.MANIFEST_NAME).read_bytes(),
                (second / builder.MANIFEST_NAME).read_bytes(),
            )

    def test_publication_rolls_back_after_partial_replacement_failure(self):
        builder = load_builder()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / "staged"
            live = root / "site" / "assets"
            staged.mkdir(parents=True)
            live.mkdir(parents=True)
            names = [f"{name}.wasm" for name, _, _ in builder.ARTIFACTS]
            names.append(builder.MANIFEST_NAME)
            old = {name: f"old-{name}".encode("ascii") for name in names}
            for name, contents in old.items():
                (live / name).write_bytes(contents)
            for name, _, _ in builder.ARTIFACTS:
                (staged / f"{name}.wasm").write_bytes(b"\x00asm\x01\x00\x00\x00" + name.encode())
            (staged / builder.MANIFEST_NAME).write_text("new\n", encoding="utf-8")

            original_replace = Path.replace
            failed = False

            def fail_on_model(source, target):
                nonlocal failed
                if (
                    not failed
                    and Path(target).parent == live
                    and Path(target).name == "atlas-model.wasm"
                ):
                    failed = True
                    raise OSError("simulated replacement failure")
                return original_replace(source, target)

            with patch.object(Path, "replace", fail_on_model):
                with self.assertRaisesRegex(OSError, "simulated replacement failure"):
                    builder.publish_artifact_set(staged, [live])

            self.assertEqual(
                {name: (live / name).read_bytes() for name in names},
                old,
            )


if __name__ == "__main__":
    unittest.main()
