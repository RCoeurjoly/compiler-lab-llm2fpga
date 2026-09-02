"""Contract tests for the exact exported serial-GEMV compiler boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import ast
import unittest
from pathlib import Path

import torch
from torch._subclasses.fake_tensor import FakeTensorMode

from TinyStories.model_adapter_exact_package import serial_gemv_accumulate
from TinyStories.serial_gemv_boundary import ascending_i64_wrapping_mac, serial_gemv


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts/pipeline/probe_exact_serial_gemv_export.py"
ADAPTER = ROOT / "TinyStories/model_adapter_exact_package.py"


def _codes(rows: int, columns: int) -> torch.Tensor:
    return (torch.arange(rows * columns, dtype=torch.int64).reshape(rows, columns) % 255) - 127


def _activations(rows: int, columns: int) -> torch.Tensor:
    return (torch.arange(rows * columns, dtype=torch.int64).reshape(rows, columns) % 97) - 48


class _SerialGemvModule(torch.nn.Module):
    def forward(self, scaled_input_q24: torch.Tensor, weight_codes: torch.Tensor) -> torch.Tensor:
        return serial_gemv(scaled_input_q24, weight_codes)


def _load_probe():
    spec = importlib.util.spec_from_file_location("exact_serial_gemv_probe", PROBE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExactSerialGemvExportTest(unittest.TestCase):
    def assert_shape_contract(self, rows: int, outputs: int, inputs: int) -> None:
        result = serial_gemv(_activations(rows, inputs), _codes(outputs, inputs))
        self.assertEqual(result.dtype, torch.int64)
        self.assertEqual(tuple(result.shape), (rows, outputs))

    def test_64x64_contract(self) -> None:
        self.assert_shape_contract(1, 64, 64)

    def test_256x64_contract(self) -> None:
        self.assert_shape_contract(1, 256, 64)

    def test_64x256_contract(self) -> None:
        self.assert_shape_contract(1, 64, 256)

    def test_50257x64_contract_exports_without_materializing_lm_head(self) -> None:
        with FakeTensorMode():
            scaled_input = torch.empty((1, 64), dtype=torch.int64)
            weights = torch.empty((50_257, 64), dtype=torch.int64)
            result = serial_gemv(scaled_input, weights)
            self.assertEqual(result.dtype, torch.int64)
            self.assertEqual(tuple(result.shape), (1, 50_257))
            exported = torch.export.export(
                _SerialGemvModule(), (scaled_input, weights), strict=False
            )
        operators = [
            node.target for node in exported.graph_module.graph.nodes
            if node.op == "call_function"
        ]
        self.assertEqual(operators, [torch.ops.llm2fpga.serial_gemv.default])

    def test_rejects_non_i64_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "signed int64"):
            serial_gemv(torch.ones((1, 64), dtype=torch.int32), _codes(64, 64))
        with self.assertRaisesRegex(ValueError, "signed int64"):
            serial_gemv(_activations(1, 64), _codes(64, 64).to(torch.int32))

    def test_rejects_non_matrix_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "rank-2"):
            serial_gemv(torch.ones(64, dtype=torch.int64), _codes(64, 64))
        with self.assertRaisesRegex(ValueError, "rank-2"):
            serial_gemv(_activations(1, 64), _codes(64, 64).unsqueeze(0))

    def test_boundary_is_eager_serial_loop(self) -> None:
        scaled_input = _activations(3, 64)
        weights = _codes(64, 64)
        self.assertTrue(torch.equal(
            ascending_i64_wrapping_mac(scaled_input, weights),
            serial_gemv_accumulate(scaled_input, weights),
        ))
        self.assertTrue(torch.equal(
            serial_gemv(scaled_input, weights),
            serial_gemv_accumulate(scaled_input, weights),
        ))

    def test_export_has_exactly_one_named_operator(self) -> None:
        scaled_input = _activations(1, 64)
        weights = _codes(64, 64)
        exported = torch.export.export(_SerialGemvModule(), (scaled_input, weights), strict=False)
        operators = [
            node.target for node in exported.graph_module.graph.nodes
            if node.op == "call_function"
        ]
        self.assertEqual(operators.count(torch.ops.llm2fpga.serial_gemv.default), 1)
        self.assertEqual(len(operators), 1)

    def test_adapter_executable_paths_have_no_direct_serial_helper_call(self) -> None:
        tree = ast.parse(ADAPTER.read_text(encoding="utf-8"), filename=str(ADAPTER))
        direct_calls = [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "serial_gemv_accumulate"
        ]
        self.assertEqual(direct_calls, [])

    def test_probe_receipt_binds_eager_export_and_frozen_boundary(self) -> None:
        probe = _load_probe()
        receipt = probe.build_receipt()
        self.assertEqual(receipt["operator"], "llm2fpga.serial_gemv.default")
        self.assertEqual(receipt["operator_count"], 1)
        self.assertEqual(receipt["eager_output_sha256"], receipt["export_output_sha256"])
        self.assertEqual(receipt["frozen_boundary_sha256"], {
            "adapter": hashlib.sha256(
                (ROOT / "TinyStories/model_adapter_exact_package.py").read_bytes()
            ).hexdigest(),
            "boundary": hashlib.sha256(
                (ROOT / "TinyStories/serial_gemv_boundary.py").read_bytes()
            ).hexdigest(),
        })
        self.assertEqual(receipt["receipt_sha256"], probe.canonical_sha256({
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }))

    def test_successor_receipt_binds_changed_adapter_to_frozen_generation_artifact(self) -> None:
        probe = _load_probe()
        receipt = probe.build_successor_receipt()
        self.assertEqual(receipt["status"], "post_boundary_generation_matched")
        self.assertEqual(receipt["successor"]["adapter_sha256"], hashlib.sha256(
            ADAPTER.read_bytes()
        ).hexdigest())
        self.assertEqual(receipt["verification"]["frozen_generation_artifact"], "matched")
        self.assertTrue(receipt["verification"]["all_adapter_gemvs_cross_boundary"])
        self.assertEqual(receipt["verification"]["successor_prompt_logits"], "matched")
        self.assertEqual(receipt["verification"]["successor_tokens"], "matched")
        self.assertEqual(receipt["verification"]["successor_exported_operator_count"], 49)
        self.assertEqual(receipt["receipt_sha256"], probe.canonical_sha256({
            key: value for key, value in receipt.items() if key != "receipt_sha256"
        }))


if __name__ == "__main__":
    unittest.main()
