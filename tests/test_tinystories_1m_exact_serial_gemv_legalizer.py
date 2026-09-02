"""Contract tests for the pinned Torch-MLIR exact serial-GEMV legalizer."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
import platform
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
MODELS = ROOT / "nix/models.nix"
SUCCESSOR_ADAPTER = ROOT / "TinyStories/model_adapter_exact_serial_gemv_successor.py"
SUCCESSOR_VERIFIER = ROOT / "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py"
SUCCESSOR_STAGE_RECEIPT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-serial-gemv-torch.json"
)
TASK1_SUCCESSOR_RECEIPT = (
    ROOT / "artifacts/comparison/tinystories-1m-exact-serial-gemv-successor.json"
)
SUCCESSOR_MODEL = "tiny-stories-1m-kev-gpt-exact-serial-gemv-successor"
HISTORICAL_MODEL_BLOCK_SHA256 = (
    "f51745f3ab9e15d2377c89853dc7403f472fecc1c4c56a992d470a46a122b62d"
)
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
        self.assertIn(f'"{SUCCESSOR_MODEL}"', flake)
        self.assertIn("llm2fpgaExactSerialGemvTorchMlirPasses", flake)

    def test_registered_successor_is_distinct_and_preserves_historical_model_bytes(self) -> None:
        models = MODELS.read_text(encoding="utf-8")
        historical_start = models.index(
            '  "tiny-stories-1m-kev-gpt-exact" = registerModel {'
        )
        historical_end = models.index(
            '  "tinystories-w8a8" = registerModel {', historical_start
        )
        historical_block = models[historical_start:historical_end]
        self.assertEqual(
            hashlib.sha256(historical_block.encode()).hexdigest(),
            HISTORICAL_MODEL_BLOCK_SHA256,
        )

        system = {
            "x86_64": "x86_64-linux",
            "aarch64": "aarch64-linux",
        }.get(platform.machine())
        self.assertIsNotNone(system, f"unsupported test architecture: {platform.machine()}")
        evaluated = subprocess.run(
            [
                "nix",
                "eval",
                "--raw",
                f".#packages.{system}.{SUCCESSOR_MODEL}-pytorch-exported.name",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        self.assertEqual(evaluated.returncode, 0, evaluated.stdout + evaluated.stderr)
        self.assertEqual(evaluated.stdout, f"{SUCCESSOR_MODEL}-pytorch-exported")
        self.assertTrue(SUCCESSOR_ADAPTER.is_file())

    def test_successor_authority_binds_task1_receipt_and_rejects_mutation(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "exact_serial_gemv_successor_verifier", SUCCESSOR_VERIFIER
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        verifier = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(verifier)

        authority = verifier.verify_successor_authority(ROOT)
        self.assertEqual(
            authority["task1_successor_receipt"]["file_sha256"],
            "d6c71ad94ccb0e00c2edb0dfbc3a2004d9e21bf1a30984b9df57570c04415dee",
        )
        self.assertEqual(
            authority["task1_successor_receipt"]["receipt_sha256"],
            "ec9985628911a28374d9b304e7896e61d1dc9635612e74311d6667eef470f7db",
        )
        self.assertEqual(authority["changed_sources"]["exact_adapter"]["sha256"],
                         "5f2dfa10c54134e44a31f89608b562aea33ef39deacfcd62eadac1f0fda94892")
        self.assertEqual(authority["changed_sources"]["serial_gemv_boundary"]["sha256"],
                         "a3e0c9f5ccd56fcd530174e2e15747008344b8e32384e508611c793008037b14")

        with tempfile.TemporaryDirectory(prefix="mutated-successor-authority-") as temporary:
            mutation_root = Path(temporary)
            receipt_path = mutation_root / TASK1_SUCCESSOR_RECEIPT.relative_to(ROOT)
            receipt_path.parent.mkdir(parents=True)
            receipt = json.loads(TASK1_SUCCESSOR_RECEIPT.read_text(encoding="utf-8"))
            receipt["verification"]["successor_exported_operator_count"] = 48
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            for source in (
                ROOT / "TinyStories/model_adapter_exact_package.py",
                ROOT / "TinyStories/serial_gemv_boundary.py",
                ROOT / "artifacts/reference/tinystories-1m-exact-generation.json",
            ):
                destination = mutation_root / source.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            with self.assertRaisesRegex(ValueError, "Task 1 successor receipt"):
                verifier.verify_successor_authority(mutation_root)

    def test_committed_successor_stage_receipt_verifies_post_legalizer_result(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "exact_serial_gemv_successor_verifier", SUCCESSOR_VERIFIER
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader if spec else None)
        verifier = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(verifier)
        receipt = json.loads(SUCCESSOR_STAGE_RECEIPT.read_text(encoding="utf-8"))
        result = verifier.validate_artifact(receipt, ROOT)
        self.assertEqual(result["model"], SUCCESSOR_MODEL)
        self.assertEqual(result["timeout_seconds"], 1800)
        self.assertEqual(result["legalizer"]["status"], "completed")
        self.assertNotEqual(result["result"]["frontier"], "identity_frontier")

        with tempfile.TemporaryDirectory(prefix="mutated-successor-torch-") as temporary:
            mutation = json.loads(json.dumps(receipt))
            output = Path(mutation["result"]["output"]["path"])
            mutated_output = Path(temporary) / "torch.mlir"
            mutated_output.write_text(
                output.read_text(encoding="utf-8").replace(
                    '"llm2fpga.serial_gemv"', '"llm2fpga.corrupted_gemv"', 1
                ),
                encoding="utf-8",
            )
            mutation["result"]["output"] = {
                "path": str(mutated_output),
                "bytes": mutated_output.stat().st_size,
                "sha256": hashlib.sha256(mutated_output.read_bytes()).hexdigest(),
            }
            mutation["receipt_sha256"] = verifier.canonical_sha256({
                key: value for key, value in mutation.items()
                if key != "receipt_sha256"
            })
            with self.assertRaisesRegex(ValueError, "Torch artifact legalization census"):
                verifier.validate_artifact(mutation, ROOT)

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

    def test_builtin_torch_operator_is_preserved_for_the_fixed_backend(self) -> None:
        source = _module(operator="torch.aten.bitwise_right_shift.Tensor_Scalar")
        result = _run_module(source)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            result.output_text.count(
                'torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"'
            ),
            1,
        )
        self.assertNotIn("exact_serial_gemv_contract", result.stderr)

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
