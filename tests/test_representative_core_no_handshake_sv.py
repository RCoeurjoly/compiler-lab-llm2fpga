import unittest
import importlib.util
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TINYSTORIES_DIR = REPO_ROOT / "TinyStories"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RepresentativeCoreNoHandshakeSvTest(unittest.TestCase):
    def test_fixed_layernorm_representative_core_variant_is_explicit(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
        adapter = (
            REPO_ROOT
            / "TinyStories"
            / "model_adapter_representative_core_pt2e_static_quant.py"
        ).read_text(encoding="utf-8")

        self.assertIn("fixed-point-layernorm-bridge", models)
        self.assertIn("quadratic-gelu-hardware-approximation", models)
        self.assertIn("TINYSTORIES_REPRESENTATIVE_CORE_FIXED_POINT_LAYERNORM", models)
        self.assertIn("TINYSTORIES_REPRESENTATIVE_CORE_QUADRATIC_GELU", models)
        self.assertIn("FixedPointLayerNormBridge", adapter)
        self.assertIn("QuadraticGeluHardwareApproximation", adapter)
        self.assertIn("replace_dropout_with_identity", adapter)
        self.assertIn("torch.nn.Identity()", adapter)
        self.assertIn("torch.ones(", adapter)
        self.assertNotIn("attn_scores = torch.matmul", adapter)
        self.assertNotIn("return torch.matmul(attn_weights, value)", adapter)
        self.assertIn("expects one query token", adapter)

    def test_integer_representative_core_variant_has_integer_boundary(self) -> None:
        if importlib.util.find_spec("torch") is None:
            self.skipTest("PyTorch is required for representative core behavior")

        adapter = load_module(
            "tinystories_representative_core_integer_adapter",
            TINYSTORIES_DIR / "model_adapter_representative_core_w4a8_integer.py",
        )

        model = adapter.build_model(None)
        example_inputs = adapter.example_inputs()
        actual = model(*example_inputs)

        self.assertEqual(model.training, False)
        self.assertEqual(len(example_inputs), 1)
        self.assertEqual(tuple(example_inputs[0].shape), (1, 1))
        self.assertEqual(str(example_inputs[0].dtype), "torch.int64")
        self.assertEqual(tuple(actual.shape), (1, 1, 2))
        self.assertEqual(str(actual.dtype), "torch.int8")

    def test_integer_representative_core_variant_is_explicitly_registered(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
        adapter = (
            TINYSTORIES_DIR / "model_adapter_representative_core_w4a8_integer.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"tinystories-representative-core-w4a8-integer"', models)
        self.assertIn("model_adapter_representative_core_w4a8_integer.py", models)
        self.assertIn('quantization = "w4a8-explicit-integer-core"', models)
        self.assertIn("slangPerFileExternModules = false", models)
        self.assertIn("torch.int8", adapter)
        self.assertIn("torch.int32", adapter)
        self.assertIn("torch.bitwise_right_shift", adapter)
        self.assertIn("def export_program", adapter)
        self.assertNotIn("prepare_pt2e", adapter)
        self.assertNotIn("convert_pt2e", adapter)
        self.assertNotIn("torch.float32", adapter)

    def test_hardware_core_models_use_single_shot_slang_ingestion(self) -> None:
        models = (REPO_ROOT / "nix" / "models.nix").read_text(encoding="utf-8")

        for model in (
            "pattern-linear-w4a8-core",
            "pattern-embedding-w4a8-core",
            "pattern-layernorm-w4a8-core",
            "tinystories-representative-core-w4a8-integer",
        ):
            match = re.search(
                rf'"{re.escape(model)}" = registerModel \{{.*?^  \}};',
                models,
                re.MULTILINE | re.DOTALL,
            )
            self.assertIsNotNone(match, model)
            block = match.group(0)

            self.assertIn("allowHwExterns = false", block)
            self.assertIn("slangPerFileExternModules = false", block)

    def test_integer_representative_core_resource_baseline_is_calyx_estimate(self) -> None:
        baseline = (REPO_ROOT / "docs" / "current-baseline.md").read_text(
            encoding="utf-8"
        )
        integer_slice = baseline[
            baseline.index("## Explicit-Integer Representative-Core Slice") : baseline.index(
                "## Explicit-Integer SV Equivalence Baseline"
            )
        ]
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")

        self.assertIn("Explicit-Integer Representative-Core Slice", integer_slice)
        self.assertIn("Native Calyx resource estimate", integer_slice)
        self.assertIn("Yosys `stat` output", integer_slice)
        self.assertIn("tinystories-representative-core-w4a8-integer", integer_slice)
        self.assertIn('"estimated_internal_bits": 652', integer_slice)
        self.assertIn('"estimated_external_bits": 4576', integer_slice)
        self.assertIn('"num_cells": 41652', integer_slice)
        self.assertIn('"num_memory_bits": 4580', integer_slice)
        self.assertIn('"num_cells": 43269', integer_slice)
        self.assertIn('"num_memory_bits": 4644', integer_slice)
        self.assertIn("historical / pre-current-source-pin", integer_slice)
        self.assertIn("pending-rerun", integer_slice)
        self.assertIn("source-closure regression check", integer_slice)
        self.assertIn("41,451 cells", integer_slice)
        self.assertIn(
            "not been accepted or promoted as a durable current resource baseline",
            integer_slice,
        )
        self.assertNotIn("none has been rerun", integer_slice)
        self.assertIn("mkIlDerivation", pipeline)
        self.assertIn("mkYosysStatDerivation", pipeline)

    def test_calyx_sv_script_does_not_use_handshake(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "calyx_to_sv_no_handshake.sh"
        ).read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")

        self.assertIn("--export-calyx", script)
        self.assertIn("-b verilog", script)
        self.assertIn("--nested", script)
        self.assertIn("--synthesis", script)
        self.assertIn("-d papercut", script)
        self.assertIn(
            "printf '%s\\n' \"$output_dir/sv/main.sv\" >\"$output_dir/sources.f\"",
            script,
        )
        self.assertNotIn("CALYX_COMPILE_PRIMITIVES_TO_SV", script)
        self.assertNotIn("CALYX_COMPILE_PRIMITIVES_TO_SV", pipeline)
        self.assertNotIn("calyx_compile_primitives_to_sv.py", script)
        self.assertNotIn("compile.sv", script)
        self.assertNotIn("primitives/core.sv", script)
        self.assertNotIn("primitives/binary_operators.sv", script)
        self.assertNotIn("primitives/memories/seq.sv", script)
        self.assertFalse(
            (REPO_ROOT / "scripts/pipeline/calyx_compile_primitives_to_sv.py").exists()
        )
        self.assertIn("-b resources", script)
        self.assertIn("resources.json", script)
        self.assertIn("missing-calyx-imports.txt", script)
        self.assertIn("CIRCT exported Futil that is incompatible", script)
        self.assertIn("Use a version-aligned official Calyx library", script)
        self.assertIn("json.load", script)
        self.assertNotIn('grep -q \'"status":"ok"\'', script)
        self.assertNotIn("handshake", script.lower())

    def test_no_handshake_backends_are_named_by_calyx_route(self) -> None:
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")

        self.assertIn("mkCalyxNativeSvDerivation", pipeline)
        self.assertIn("mkCalyxHwSvDerivation", pipeline)
        self.assertIn('"calyx-native-sv"', pipeline)
        self.assertIn('"calyx-hw-sv"', pipeline)

    def test_direct_calyx_hw_sv_script_uses_circt_lower_calyx_to_hw(self) -> None:
        script_path = REPO_ROOT / "scripts" / "pipeline" / "calyx_to_hw_sv_no_handshake.sh"
        self.assertTrue(script_path.exists())
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("CIRCT_PASS_PLUGIN", script)
        self.assertIn("--load-pass-plugin", script)
        self.assertIn("--pass-pipeline", script)
        self.assertIn("llm2fpga-calyx-hw-preflight", script)
        self.assertIn("--calyx-remove-groups", script)
        self.assertIn("--lower-calyx-to-hw", script)
        self.assertIn("--lower-hw-to-sv", script)
        self.assertIn("--lower-seq-to-sv", script)
        self.assertIn("--export-verilog", script)
        self.assertNotIn("--export-calyx", script)
        self.assertNotIn("-b verilog", script)
        self.assertNotIn("calyx_bin", script)

    def test_yosys_slang_raises_parse_depth_for_native_calyx_sv(self) -> None:
        common = (REPO_ROOT / "scripts" / "pipeline" / "common.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("--max-parse-depth", common)
        self.assertIn("YOSYS_SLANG_MAX_PARSE_DEPTH", common)

    def test_flat_scf_stage_uses_mlir_flatten_memref_for_expand_shape_reproducer(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "scf_to_flat_scf_no_handshake.sh"
        ).read_text(encoding="utf-8")
        reproducer = (
            REPO_ROOT
            / "reproducers"
            / "flat-scf-expand-shape-materialization"
            / "input.mlir"
        )

        self.assertTrue(reproducer.exists())
        self.assertIn("mlir_opt=", script)
        self.assertIn("--flatten-memref", script)
        self.assertIn("--lower-affine", script)
        self.assertNotIn("circt_opt=", script)

    def test_no_handshake_bufferization_uses_identity_layout_boundaries(self) -> None:
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "linalg_to_scf_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("--one-shot-bufferize=", script)
        self.assertIn("bufferize-function-boundaries", script)
        self.assertIn("function-boundary-type-conversion=identity-layout-map", script)

    def test_pre_calyx_uses_checked_in_mlir_pass_plugin(self) -> None:
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        calyx_script = (
            REPO_ROOT / "scripts" / "pipeline" / "scf_to_calyx_no_handshake.sh"
        ).read_text(encoding="utf-8")
        pass_source = (
            REPO_ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("--load-pass-plugin=${mlirPasses}", pipeline)
        self.assertIn("llm2fpga-lower-static-memref-views-for-calyx", pipeline)
        self.assertIn("llm2fpga-drop-calyx-unsupported-asserts", pipeline)
        self.assertIn("llm2fpga-fold-constant-truncf", pipeline)
        self.assertIn("llm2fpga-lower-roundeven-for-calyx", pipeline)
        self.assertIn("calyx_float_frontier_report.py", pipeline)
        self.assertIn("float-frontier.json", pipeline)
        self.assertIn("CALYX_PREFLIGHT_REPORT", pipeline)
        self.assertIn("calyx_preflight_report.py", pipeline)
        self.assertIn("pre-calyx-legality.json", pipeline)
        self.assertIn("--manifest-json", pipeline)
        self.assertIn("PassRegistration<LowerStaticMemRefViewsForCalyxPass>", pass_source)
        self.assertIn("PassRegistration<DropCalyxUnsupportedAssertOpsPass>", pass_source)
        self.assertIn("PassRegistration<FoldConstantTruncFOpsPass>", pass_source)
        self.assertIn("PassRegistration<LowerRoundEvenForCalyxPass>", pass_source)
        self.assertIn("flattenStaticIdentityMemRefGlobals", pass_source)
        self.assertIn("updateGetGlobalTypes", pass_source)
        self.assertIn("dense.reshape", pass_source)
        self.assertIn("materializeDenseResourceMemRefGlobals", pass_source)
        self.assertIn("DenseF32ResourceElementsAttr", pass_source)
        self.assertIn("tryGetAsArrayRef", pass_source)
        self.assertNotIn("python3 -", pipeline)
        self.assertIn("CALYX_PREFLIGHT_REPORT", calyx_script)
        self.assertIn("--require-clean", calyx_script)
        self.assertIn("pre-calyx-legality.json", calyx_script)
        self.assertIn(
            "pre-Calyx legality census found prohibited operations", calyx_script
        )

    def test_calyx_backend_has_checked_in_circt_pass_plugin_home(self) -> None:
        derivation = (REPO_ROOT / "nix" / "circt-passes.nix").read_text(
            encoding="utf-8"
        )
        cmake = (REPO_ROOT / "tools" / "circt-passes" / "CMakeLists.txt").read_text(
            encoding="utf-8"
        )
        pass_source = (
            REPO_ROOT / "tools" / "circt-passes" / "CalyxPipelinePasses.cpp"
        ).read_text(encoding="utf-8")

        self.assertIn("-DCIRCT_DIR=${circt.dev}/lib/cmake/circt", derivation)
        self.assertIn("-DMLIR_DIR=${mlir.dev}/lib/cmake/mlir", derivation)
        self.assertIn("-DLLVM_DIR=${llvm.dev}/lib/cmake/llvm", derivation)
        self.assertIn("find_package(CIRCT REQUIRED CONFIG)", cmake)
        self.assertIn("CIRCTCalyx", cmake)
        self.assertIn("llm2fpga-calyx-pipeline-sanity", pass_source)
        self.assertIn("llm2fpga-calyx-hw-preflight", pass_source)
        self.assertIn("PassRegistration<CalyxPipelineSanityPass>", pass_source)
        self.assertIn("PassRegistration<CalyxHwPreflightPass>", pass_source)
        self.assertIn("calyx.invoke blocks direct Calyx-HW lowering", pass_source)
        self.assertIn("calyx.instance blocks direct Calyx-HW lowering", pass_source)
        self.assertIn("calyx.seq_mem blocks direct Calyx-HW lowering", pass_source)

    def test_native_calyx_backend_is_pinned_and_packaged(self) -> None:
        derivation = (REPO_ROOT / "nix" / "calyx.nix").read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
        script = (
            REPO_ROOT / "scripts" / "pipeline" / "calyx_to_sv_no_handshake.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('version = "0.7.1"', derivation)
        self.assertIn("cargoLock =", derivation)
        self.assertIn("outputHashes = {", derivation)
        self.assertIn(
            '"dap-0.4.1-alpha1" = "sha256-oJHeY9Hm8DMC1T9flRyjf6EmBcJc3tuvcPlZXtHTGqs=";',
            derivation,
        )
        self.assertIn("CALYX_PRIMITIVES_DIR", derivation)
        self.assertIn("calyxTool", pipeline)
        self.assertIn("circt-translate", pipeline)
        self.assertIn("resources.json", script)

    def test_current_calyx_truncf_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-arith-truncf-constant"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        passing_shape = (reproducer_dir / "f32-constant.mlir").read_text(
            encoding="utf-8"
        )
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("arith.truncf", failing)
        self.assertIn(": f64 to f32", failing)
        self.assertIn("arith.constant 1.000000e-05 : f32", passing_shape)
        self.assertIn("Do not fix this with textual MLIR rewriting", readme)

    def test_calyx_i1_uitofp_frontier_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-i1-uitofp"
        input_mlir = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("arith.uitofp", input_mlir)
        self.assertIn(": i1 to f32", input_mlir)
        self.assertIn("extui", readme)
        self.assertIn("sitofp", readme)
        self.assertIn("Textual MLIR substitution is not an acceptable fix", readme)
        self.assertIn('"calyx-i1-uitofp-upstream-reproducer"', flake)

    def test_pre_calyx_legalizes_only_i1_uitofp_to_f32(self) -> None:
        source = (
            REPO_ROOT / "tools" / "mlir-passes" / "FoldConstantTruncFOps.cpp"
        ).read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "nix" / "pipeline.nix").read_text(
            encoding="utf-8"
        )
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("llm2fpga-lower-i1-uitofp-for-calyx", source)
        self.assertIn("arith::UIToFPOp", source)
        self.assertIn("isInteger(1)", source)
        self.assertIn("isF32()", source)
        self.assertIn("arith::ExtUIOp", source)
        self.assertIn("arith::SIToFPOp", source)
        self.assertIn("PassRegistration<LowerI1UIToFPForCalyxPass>", source)
        self.assertIn("llm2fpga-lower-i1-uitofp-for-calyx", pipeline)
        self.assertIn('"calyx-i1-uitofp-legalization-selftest"', flake)

    def test_current_calyx_memref_view_port_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-memref-view-port"
        ranked_port = (reproducer_dir / "ranked-port.mlir").read_text(
            encoding="utf-8"
        )
        reinterpret_cast = (reproducer_dir / "reinterpret-cast.mlir").read_text(
            encoding="utf-8"
        )
        flat_port = (reproducer_dir / "flat-port-no-view.mlir").read_text(
            encoding="utf-8"
        )
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("memref<2x2xi8>", ranked_port)
        self.assertIn("memref.reinterpret_cast", reinterpret_cast)
        self.assertIn("memref<4xi8>", flat_port)
        self.assertIn("one-dimensional", readme)
        self.assertIn("textual MLIR rewriting", readme)

    def test_current_calyx_assert_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-cf-assert"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        passing_shape = (reproducer_dir / "no-assert.mlir").read_text(
            encoding="utf-8"
        )
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("cf.assert", failing)
        self.assertNotIn("cf.assert", passing_shape)
        self.assertIn("valid token/index domain", readme)
        self.assertIn("textual MLIR rewriting", readme)

    def test_calyx_math_roundeven_regression_case_is_tracked(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-math-roundeven"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("math.roundeven", failing)
        self.assertIn("llm2fpga-lower-roundeven-for-calyx", readme)
        self.assertIn("finite values in the `i32` range", readme)
        self.assertIn("Textual MLIR substitution is not an acceptable fix", readme)

    def test_current_calyx_math_rsqrt_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-math-rsqrt"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("math.rsqrt", failing)
        self.assertIn("normalization-like variance paths", readme)
        self.assertIn("documented numerical contract", readme)
        self.assertIn("Textual MLIR substitution is not an acceptable fix", readme)

    def test_current_calyx_math_exp_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-math-exp"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("math.exp", failing)
        self.assertIn("PT2E W8A8", readme)
        self.assertIn("documented numerical contract", readme)
        self.assertIn("Textual MLIR substitution is not an acceptable fix", readme)
        flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn('"calyx-math-exp-upstream-reproducer"', flake)

    def test_calyx_dense_resource_crash_regression_is_tracked(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-unnamed-crash"
        input_mlir = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("memref.global", input_mlir)
        self.assertNotIn("dense_resource", input_mlir)
        self.assertIn("DenseResourceElementsAttr", readme)
        self.assertIn("checked-in MLIR pass plugin", readme)
        self.assertIn("Textual MLIR", readme)

    def test_native_calyx_float_const_parse_blocker_is_tracked(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-native-float-const"
        input_futil = (reproducer_dir / "input.futil").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("std_float_const(0, 32, 0.000000)", input_futil)
        self.assertIn("native Calyx 0.7.1 rejects", readme)
        self.assertIn("backend compatibility blocker", readme)
        self.assertIn("primitives/float.futil", readme)
        self.assertIn("Textual", readme)

    def test_calyx_sv_memory_free_smoke_test_is_tracked(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-register-sv"
        input_mlir = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("calyx.register", input_mlir)
        self.assertNotIn("calyx.seq_mem", input_mlir)
        self.assertIn("positive Calyx-to-SV", readme)

    def test_current_calyx_seq_mem_sv_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-seq-mem-sv"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("calyx.seq_mem", failing)
        self.assertIn("couldn't convert to core primitive", readme)
        self.assertIn("Textual Calyx", readme)
        self.assertIn("MLIR editing is not acceptable", readme)

    def test_current_calyx_memory_sv_blocker_is_minimized(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-memory-sv"
        failing = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("calyx.memory", failing)
        self.assertIn("addr0, write_data, write_en, clk, read_data, done", readme)
        self.assertIn("does not lower Calyx memories at all", readme)

    def test_current_calyx_remove_groups_invoke_ref_assertion_is_tracked(self) -> None:
        reproducer_dir = REPO_ROOT / "reproducers" / "calyx-remove-groups-invoke-ref"
        input_mlir = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("calyx.invoke", input_mlir)
        self.assertIn("calyx.register", input_mlir)
        self.assertNotIn("calyx.seq_mem", input_mlir)
        self.assertIn("invoke/reference handling", readme)

    def test_current_calyx_remove_groups_invoke_memory_assertion_is_tracked(self) -> None:
        reproducer_dir = (
            REPO_ROOT / "reproducers" / "calyx-remove-groups-invoke-memory"
        )
        input_mlir = (reproducer_dir / "input.mlir").read_text(encoding="utf-8")
        readme = (reproducer_dir / "README.md").read_text(encoding="utf-8")

        self.assertIn("calyx.invoke", input_mlir)
        self.assertIn("calyx.seq_mem", input_mlir)
        self.assertIn("--calyx-remove-groups", readme)


if __name__ == "__main__":
    unittest.main()
