"""Contract tests for the pinned Torch-MLIR exact serial-GEMV legalizer."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "reproducers"
    / "tinystories-1m-exact-serial-gemv"
    / "raw-boundary.mlir"
)
SOURCE = ROOT / "tools/torch-mlir-passes/LegalizeExactSerialGemv.cpp"
BOUNDARY = ROOT / "TinyStories/serial_gemv_boundary.py"
CMAKE = ROOT / "tools/torch-mlir-passes/CMakeLists.txt"
PACKAGE = ROOT / "nix/torch-mlir-passes.nix"
COMPILE_PYTORCH = ROOT / "scripts/compile-pytorch.py"
PIPELINE = ROOT / "nix/pipeline.nix"
PASS_PIPELINE = "builtin.module(llm2fpga-legalize-exact-serial-gemv)"
FIXED_BACKEND_PIPELINE = (
    "builtin.module(llm2fpga-legalize-exact-serial-gemv,"
    "func.func(torch-match-quantized-custom-ops),"
    "torchdynamo-export-to-torch-backend-pipeline{ extra-library=})"
)


@dataclass(frozen=True)
class CompilerRun:
    returncode: int
    stdout: str
    stderr: str
    output_created: bool
    output_text: str


def _torch_mlir_opt() -> Path:
    configured = os.environ.get("TORCH_MLIR_OPT")
    tool = Path(configured) if configured else Path(shutil.which("torch-mlir-opt") or "")
    if not tool.is_file():
        raise AssertionError("test must run inside the pinned Nix environment")
    return tool


def _plugin() -> Path:
    configured = os.environ.get("LLM2FPGA_EXACT_SERIAL_GEMV_PASS_PLUGIN")
    if configured:
        plugin = Path(configured)
    else:
        completed = subprocess.run(
            [
                "nix",
                "build",
                "--no-link",
                "--print-out-paths",
                ".#llm2fpgaExactSerialGemvTorchMlirPasses",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        plugin = Path(completed.stdout.strip()) / "lib/LLM2FPGATorchMLIRPasses.so"
    if not plugin.is_file():
        raise AssertionError(f"exact serial-GEMV pass plugin is missing: {plugin}")
    return plugin


def _run_module(text: str, pipeline: str = PASS_PIPELINE) -> CompilerRun:
    with tempfile.TemporaryDirectory(prefix="exact-serial-gemv-legalizer-") as temporary:
        source = Path(temporary) / "input.mlir"
        output = Path(temporary) / "output.mlir"
        source.write_text(text, encoding="utf-8")
        completed = subprocess.run(
            [
                str(_torch_mlir_opt()),
                "--allow-unregistered-dialect",
                f"--load-pass-plugin={_plugin()}",
                f"--pass-pipeline={pipeline}",
                str(source),
                "-o",
                str(output),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        output_created = output.is_file()
        return CompilerRun(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            output_created=output_created,
            output_text=output.read_text(encoding="utf-8") if output_created else "",
        )


def _module(
    *,
    operator: str = "torch.llm2fpga.serial_gemv",
    input_type: str = "!torch.vtensor<[1,64],si64>",
    weight_type: str = "!torch.vtensor<[64,64],si64>",
    result_type: str = "!torch.vtensor<[1,64],si64>",
) -> str:
    return f"""module {{
  func.func @main(%input: {input_type}, %weights: {weight_type}) -> {result_type} {{
    %0 = torch.operator \"{operator}\"(%input, %weights) : ({input_type}, {weight_type}) -> {result_type}
    return %0 : {result_type}
  }}
}}
"""


class ExactSerialGemvLegalizerTest(unittest.TestCase):
    def assert_contract_rejected(self, text: str) -> None:
        result = _run_module(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact_serial_gemv_contract", result.stderr)
        self.assertFalse(result.output_created, "rejected input unexpectedly created output")
        self.assertEqual(result.stdout, "")

    def test_package_is_a_separate_torch_mlir_abi_plugin(self) -> None:
        for path in (SOURCE, CMAKE, PACKAGE):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"required plugin source is missing: {path}")

        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        package = PACKAGE.read_text(encoding="utf-8")
        self.assertIn("llm2fpgaExactSerialGemvTorchMlirPasses", flake)
        self.assertIn("mlir = mlirForTorchMlir", flake)
        self.assertIn("llvmPackages = torchMlirLlvmPackages", flake)
        self.assertIn("torchMlir", package)
        self.assertIn("TORCH_MLIR_INCLUDE_DIR", package)

        def shared_library(binary: Path, name: str) -> str:
            completed = subprocess.run(
                ["ldd", str(binary)], check=True, capture_output=True, text=True
            )
            line = next(
                (line.strip() for line in completed.stdout.splitlines() if name in line),
                "",
            )
            self.assertTrue(line, f"{binary} does not use the shared {name} registry")
            return line.split("=>", maxsplit=1)[1].split("(", maxsplit=1)[0].strip()

        for library in ("libLLVM.so", "libMLIR.so"):
            with self.subTest(library=library):
                self.assertEqual(
                    shared_library(_plugin(), library),
                    shared_library(_torch_mlir_opt(), library),
                )

    def test_registered_exact_stage_uses_raw_import_then_fixed_backend(self) -> None:
        compiler = COMPILE_PYTORCH.read_text(encoding="utf-8")
        pipeline = PIPELINE.read_text(encoding="utf-8")
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn('parser.add_argument("--torch-mlir-opt"', compiler)
        self.assertIn('parser.add_argument("--pass-plugin"', compiler)
        self.assertIn('parser.add_argument("--custom-op-library"', compiler)
        self.assertIn('"raw" if args.pass_plugin is not None', compiler)
        self.assertIn("llm2fpga-legalize-exact-serial-gemv", compiler)
        self.assertIn("torchdynamo-export-to-torch-backend-pipeline", compiler)
        self.assertIn("--allow-unregistered-dialect", compiler)
        self.assertLess(
            compiler.index("llm2fpga-legalize-exact-serial-gemv"),
            compiler.index("torchdynamo-export-to-torch-backend-pipeline"),
        )

        self.assertIn("exactSerialGemvModelNames ? [ ]", pipeline)
        self.assertIn("--torch-mlir-opt ${torchMlirOpt}", pipeline)
        self.assertIn("--pass-plugin ${torchMlirPasses}", pipeline)
        self.assertIn("--custom-op-library ${../TinyStories/serial_gemv_boundary.py}", pipeline)
        self.assertIn('"tiny-stories-1m-kev-gpt-exact"', flake)
        self.assertIn("llm2fpgaExactSerialGemvTorchMlirPasses", flake)

    def test_raw_boundary_becomes_exact_builtin_tensor_descriptor(self) -> None:
        result = _run_module(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.output_created)
        self.assertNotIn("torch.operator", result.output_text)
        self.assertEqual(result.output_text.count('"llm2fpga.serial_gemv"'), 1)
        self.assertIn("rows = 1 : i64", result.output_text)
        self.assertIn("outputs = 64 : i64", result.output_text)
        self.assertIn("inputs = 64 : i64", result.output_text)
        self.assertIn('mac_order = "ascending_i64_wrap"', result.output_text)
        self.assertIn("tensor<1x64xi64>", result.output_text)
        self.assertIn("tensor<64x64xi64>", result.output_text)

    def test_legalizer_runs_before_the_fixed_backend_pipeline(self) -> None:
        result = _run_module(FIXTURE.read_text(encoding="utf-8"), FIXED_BACKEND_PIPELINE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("torch.operator", result.output_text)
        self.assertEqual(result.output_text.count('"llm2fpga.serial_gemv"'), 1)

    def test_raw_import_route_compiles_a_saved_exported_program(self) -> None:
        import torch

        from TinyStories.serial_gemv_boundary import serial_gemv

        class TinyGemv(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.register_buffer(
                    "weights",
                    torch.tensor(
                        [[1, 2, 3, 4], [-1, -2, -3, -4], [4, 3, 2, 1]],
                        dtype=torch.int64,
                    ),
                )

            def forward(self, value: torch.Tensor) -> torch.Tensor:
                return serial_gemv(value, self.weights)

        with tempfile.TemporaryDirectory(prefix="exact-serial-gemv-export-") as temporary:
            export_dir = Path(temporary) / "exported"
            export_dir.mkdir()
            exported = torch.export.export(
                TinyGemv(), (torch.tensor([[1, 2, 3, 4]], dtype=torch.int64),)
            )
            torch.export.save(exported, export_dir / "exported.pt2")
            output = Path(temporary) / "legalized.mlir"
            torch_mlir_root = _torch_mlir_opt().parents[1]
            torch_mlir_site = next(torch_mlir_root.glob("lib/python*/site-packages"))
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                [
                    str(torch_mlir_site),
                    str(torch_mlir_site / "torch_mlir"),
                    environment.get("PYTHONPATH", ""),
                ]
            )
            completed = subprocess.run(
                [
                    shutil.which("python") or sys.executable,
                    str(COMPILE_PYTORCH),
                    "--exported-program-dir",
                    str(export_dir),
                    "--out",
                    str(output),
                    "--torch-mlir-opt",
                    str(_torch_mlir_opt()),
                    "--pass-plugin",
                    str(_plugin()),
                    "--custom-op-library",
                    str(BOUNDARY),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            legalized = output.read_text(encoding="utf-8")
            self.assertNotIn("torch.operator", legalized)
            self.assertEqual(legalized.count('"llm2fpga.serial_gemv"'), 1)
            self.assertIn("rows = 1 : i64", legalized)
            self.assertIn("outputs = 3 : i64", legalized)
            self.assertIn("inputs = 4 : i64", legalized)

    def test_unknown_custom_operator_is_rejected(self) -> None:
        self.assert_contract_rejected(_module(operator="torch.example.unknown"))

    def test_dynamic_dimension_is_rejected(self) -> None:
        self.assert_contract_rejected(
            _module(
                input_type="!torch.vtensor<[?,64],si64>",
                result_type="!torch.vtensor<[?,64],si64>",
            )
        )

    def test_non_si64_is_rejected(self) -> None:
        self.assert_contract_rejected(
            _module(
                input_type="!torch.vtensor<[1,64],si32>",
                weight_type="!torch.vtensor<[64,64],si32>",
                result_type="!torch.vtensor<[1,64],si32>",
            )
        )

    def test_unknown_shape_is_rejected(self) -> None:
        self.assert_contract_rejected(
            _module(
                input_type="!torch.vtensor<*,si64>",
                result_type="!torch.vtensor<*,si64>",
            )
        )

    def test_inconsistent_result_shape_is_rejected(self) -> None:
        self.assert_contract_rejected(
            _module(result_type="!torch.vtensor<[2,64],si64>")
        )


if __name__ == "__main__":
    unittest.main()
