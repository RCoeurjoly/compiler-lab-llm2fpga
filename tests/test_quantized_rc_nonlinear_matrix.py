import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "run_quantized_rc_nonlinear_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("nonlinear_matrix", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QuantizedRcNonlinearMatrixTest(unittest.TestCase):
    def test_error_diagnostic_overrides_zero_exit_and_output_file(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool = root / "tool"
            output = root / "out.mlir"
            log = root / "tool.log"
            tool.write_text(
                "#!/usr/bin/env bash\nprintf 'error: unsupported op\\n' >&2\nprintf 'partial\\n' > \"$2\"\nexit 0\n",
                encoding="utf-8",
            )
            tool.chmod(0o755)
            attempt = module.run_command(
                "fake", [str(tool), "-o", str(output)], log, output
            )

        self.assertEqual(attempt["status"], "rejected")
        self.assertEqual(attempt["exit_code"], 0)
        self.assertTrue(attempt["diagnostic_error"])
        self.assertTrue(attempt["output_exists"])

    def test_exact_claim_requires_passing_raw_code_and_token_comparison(self) -> None:
        module = load_module()
        row = {
            "route_id": "direct-math-to-funcs",
            "semantic_classification": "exact",
            "oracle_comparison": {"status": "not-run"},
        }
        with self.assertRaisesRegex(ValueError, "oracle comparison"):
            module.validate_semantic_claim(row)

    def test_scout_or_approximate_route_cannot_be_exact(self) -> None:
        module = load_module()
        row = {
            "route_id": "scout-exp-approximation",
            "semantic_classification": "exact",
            "oracle_comparison": {"status": "pass"},
        }
        with self.assertRaisesRegex(ValueError, "approximate or scout"):
            module.validate_semantic_claim(row)

    def test_route_documentation_distinguishes_upstream_and_local_steps(self) -> None:
        module = load_module()
        self.assertEqual(
            module.ROUTE_DOCUMENTATION["mlir-tosa"]["kind"],
            "upstream-specification-and-tool",
        )
        self.assertEqual(
            module.ROUTE_DOCUMENTATION["llm2fpga-zero-point-compatibility"][
                "kind"
            ],
            "repository-local-pass",
        )
        self.assertIn(
            "LegalizePt2eTosaZeroPoint.cpp",
            module.ROUTE_DOCUMENTATION["llm2fpga-zero-point-compatibility"][
                "reference"
            ],
        )

    def test_oracle_comparison_requires_six_codes_and_token_per_case(self) -> None:
        module = load_module()
        reference = {
            "results": [
                {
                    "case_id": "ascending",
                    "output_codes_i8": [1, 2, 3, 4, 5, 6],
                    "token_id": 2,
                }
            ]
        }
        candidate = {
            "results": [
                {
                    "case_id": "ascending",
                    "output_codes_i8": [1, 2, 3, 4, 5, 6],
                    "token_id": 2,
                }
            ]
        }
        self.assertEqual(module.compare_oracle(reference, candidate)["status"], "pass")
        candidate["results"][0]["output_codes_i8"][5] = 7
        self.assertEqual(module.compare_oracle(reference, candidate)["status"], "fail")
        candidate["results"][0]["output_codes_i8"] = [1, 2, 3]
        self.assertEqual(module.compare_oracle(reference, candidate)["status"], "fail")

    def test_non_executable_pipeline_helpers_are_invoked_via_bash(self) -> None:
        module = load_module()
        command = module.bash_script_command(
            "/nix/store/source/linalg_to_scf_no_handshake.sh",
            "/nix/store/mlir-opt",
            "/nix/store/input.mlir",
            "/nix/store/output.mlir",
        )
        self.assertEqual(
            command,
            [
                "bash",
                "/nix/store/source/linalg_to_scf_no_handshake.sh",
                "/nix/store/mlir-opt",
                "/nix/store/input.mlir",
                "/nix/store/output.mlir",
            ],
        )


if __name__ == "__main__":
    unittest.main()
