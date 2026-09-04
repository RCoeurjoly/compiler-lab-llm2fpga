"""Bounded composition/provenance tests for the exact serial-GEMV route."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/pipeline/run_exact_serial_gemv_frontier.py"
VERIFIER = ROOT / "scripts/pipeline/verify_exact_serial_gemv_frontier.py"
PORTABLE = ROOT / "scripts/pipeline/verify_exact_serial_gemv_portable_torch.py"
HISTORICAL_EXPORT = Path("/nix/store/zcqzv2vgdyn800zz89r87zjm1rp7r1j5-tiny-stories-1m-kev-gpt-exact-serial-gemv-successor-pytorch-exported")
HISTORICAL_TORCH = Path("/nix/store/4r2i60a5alclxhwzcj1664aw8b4nla3h-tiny-stories-1m-kev-gpt-exact-serial-gemv-successor-torch.mlir")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"missing module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ExactSerialGemvFrontierTest(unittest.TestCase):
    def test_portable_torch_receipt_binds_content_not_store_paths(self) -> None:
        portable = _load(PORTABLE, "exact_serial_gemv_portable")
        if not HISTORICAL_EXPORT.is_dir() or not HISTORICAL_TORCH.is_file():
            self.skipTest("historical exact Torch artifacts unavailable")
        receipt = portable.build(ROOT, HISTORICAL_EXPORT, HISTORICAL_TORCH)
        self.assertNotIn("/nix/store/", json.dumps(receipt, sort_keys=True))
        portable.verify(receipt, ROOT, HISTORICAL_EXPORT, HISTORICAL_TORCH)
        receipt["input"]["exported_program"]["sha256"] = "0" * 64
        receipt["receipt_sha256"] = portable.canonical({
            key: item for key, item in receipt.items() if key != "receipt_sha256"
        })
        with self.assertRaisesRegex(ValueError, "input binding mismatch"):
            portable.verify(receipt, ROOT, HISTORICAL_EXPORT, HISTORICAL_TORCH)

    def test_predecessor_identity_rejects_wrong_commit_or_tree(self) -> None:
        runner = _load(RUNNER, "exact_serial_gemv_runner_predecessor")
        with tempfile.TemporaryDirectory(prefix="exact-serial-gemv-predecessor-") as raw:
            root = Path(raw)
            with self.assertRaisesRegex(runner.FrontierError, "commit/tree mismatch"):
                runner.predecessor_identity(role="task2", root=root, commit="0" * 40,
                                            tree=runner.TASK2_TREE)
            with self.assertRaisesRegex(runner.FrontierError, "commit/tree mismatch"):
                runner.predecessor_identity(role="task3", root=root, commit=runner.TASK3_COMMIT,
                                            tree="0" * 40)

    def test_forced_calyx_failure_stops_later_stages_and_binds_caps(self) -> None:
        runner = _load(RUNNER, "exact_serial_gemv_runner")
        verifier = _load(VERIFIER, "exact_serial_gemv_verifier")
        with tempfile.TemporaryDirectory(prefix="exact-serial-gemv-frontier-") as raw:
            root = Path(raw)
            exports = root / "export.json"
            torch = root / "torch.json"
            calyx = root / "calyx.json"
            exports.write_text('{"stage":"export"}\n', encoding="utf-8")
            torch.write_text('{"stage":"legalize"}\n', encoding="utf-8")
            calyx.write_text('{"stage":"calyx"}\n', encoding="utf-8")
            receipt = runner.run_stages(
                root=root,
                stages=(
                    runner.Stage("export", exports, lambda: None),
                    runner.Stage("legalize", torch, lambda: None),
                    runner.Stage("calyx", calyx, lambda: (_ for _ in ()).throw(
                        runner.FrontierError("forced Calyx failure")
                    )),
                    runner.Stage("sv", None, lambda: None),
                    runner.Stage("synthesis", None, lambda: None),
                ),
            )
            self.assertEqual(receipt["result"]["status"], "failure")
            self.assertEqual(receipt["result"]["stage"], "calyx")
            self.assertEqual(receipt["stages"]["sv"], {})
            self.assertEqual(receipt["stages"]["synthesis"], {})
            self.assertTrue(all(
                stage["timeout_seconds"] <= 1800
                for stage in receipt["stages"].values() if stage
            ))
            verifier.verify_receipt(receipt, root)

    def test_verifier_rejects_success_sv_outside_compiler_closure(self) -> None:
        runner = _load(RUNNER, "exact_serial_gemv_runner_closure")
        verifier = _load(VERIFIER, "exact_serial_gemv_verifier_closure")
        with tempfile.TemporaryDirectory(prefix="exact-serial-gemv-closure-") as raw:
            root = Path(raw)
            calyx = root / "calyx.json"
            sv = root / "not-compiler-owned.sv"
            calyx.write_text('{"stage":"calyx"}\n', encoding="utf-8")
            sv.write_text("module foreign; endmodule\n", encoding="utf-8")
            receipt = runner.run_stages(
                root=root,
                stages=(
                    runner.Stage("export", None, lambda: None),
                    runner.Stage("legalize", None, lambda: None),
                    runner.Stage("calyx", calyx, lambda: None),
                    runner.Stage("sv", sv, lambda: None),
                    runner.Stage("synthesis", None, lambda: None),
                ),
                compiler_closure=(),
            )
            self.assertEqual(receipt["result"]["status"], "success")
            with self.assertRaisesRegex(ValueError, "outside compiler closure"):
                verifier.verify_receipt(receipt, root)


if __name__ == "__main__":
    unittest.main()
