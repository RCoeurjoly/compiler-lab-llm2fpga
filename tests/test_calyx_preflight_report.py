import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "scripts" / "pipeline" / "calyx_preflight_report.py"


class CalyxPreflightReportTest(unittest.TestCase):
    def run_report(
        self, mlir: str, *, require_clean: bool = False
    ) -> tuple[int, dict[str, object] | None, str, bytes | None]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mlir"
            output_path = Path(tmp) / "report.json"
            input_path.write_text(mlir, encoding="utf-8")
            cmd = [sys.executable, str(REPORT), str(input_path), str(output_path)]
            if require_clean:
                cmd.append("--require-clean")
            result = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            output = output_path.read_bytes() if output_path.is_file() else None
            report = json.loads(output) if output is not None else None
            return result.returncode, report, result.stderr, output

    def assert_valid_self_hash(self, report: dict[str, object]) -> None:
        payload = dict(report)
        actual = payload.pop("sha256")
        expected = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(actual, expected)

    def test_counts_result_bearing_custom_operations_and_ignores_comments(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "%0 = math.floor %arg0 : f64\n"
            "  %1 = arith.negf %arg1 : f32\n"
            "    %2 = math.absi %arg2 : i64\n"
            "// %3 = math.floor %arg0 : f64\n"
            "%4 = arith.uitofp %flag : i1 to f32\n"
            "memref.copy %a, %b : memref<1xi8> to memref<1xi8>\n"
            "memref.collapse_shape %a [[0, 1]] : memref<1x1xi8> into memref<1xi8>\n"
            "memref.expand_shape %a [[0, 1]] output_shape [1, 1] : memref<1xi8> into memref<1x1xi8>\n"
            "%5 = memref.reinterpret_cast %a to offset: [0], sizes: [1], strides: [1]\n",
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["prohibited_ops"],
            {
                "arith.negf": 1,
                "arith.uitofp": 1,
                "math.absi": 1,
                "math.floor": 1,
                "memref.collapse_shape": 1,
                "memref.copy": 1,
                "memref.expand_shape": 1,
                "memref.reinterpret_cast": 1,
            },
        )
        self.assertEqual(
            report["first_locations"],
            {
                "arith.negf": {"line": 2, "column": 8},
                "arith.uitofp": {"line": 5, "column": 6},
                "math.absi": {"line": 3, "column": 10},
                "math.floor": {"line": 1, "column": 6},
                "memref.collapse_shape": {"line": 7, "column": 1},
                "memref.copy": {"line": 6, "column": 1},
                "memref.expand_shape": {"line": 8, "column": 1},
                "memref.reinterpret_cast": {"line": 9, "column": 6},
            },
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_counts_generic_escaped_result_list_and_comment_trivia_forms(self) -> None:
        mlir = (
            "%floor = \"math.floor\" // operand starts after valid trivia\n"
            "  (%arg0) : (f64) -> f64\n"
            "%neg0, %neg1 = \"arith.negf\"(%arg1) : (f32) -> (f32, f32)\n"
            "%abs:2 = \"math.absi\"(%arg2) : (i64) -> (i64, i64)\n"
            "%escaped = \"math.\\66loor\"(%arg0) : (f64) -> f64\n"
            "%u = \"arith.\\75itofp\"(%flag) : (i1) -> f32\n"
            "\"memref.copy\"(%a, %b) : (memref<1xi8>, memref<1xi8>) -> ()\n"
            "// \"math.absi\"(%arg2) : (i64) -> i64\n"
        )
        rc, report, stderr, output = self.run_report(mlir)

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["prohibited_ops"],
            {
                "arith.negf": 1,
                "arith.uitofp": 1,
                "math.absi": 1,
                "math.floor": 2,
                "memref.copy": 1,
            },
        )
        self.assertEqual(
            report["first_locations"],
            {
                "arith.negf": {"line": 3, "column": 16},
                "arith.uitofp": {"line": 6, "column": 6},
                "math.absi": {"line": 4, "column": 10},
                "math.floor": {"line": 1, "column": 10},
                "memref.copy": {"line": 7, "column": 1},
            },
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

        rc2, report2, stderr2, output2 = self.run_report(mlir)
        self.assertEqual(rc2, 0, stderr2)
        self.assertEqual(report2, report)
        self.assertEqual(output2, output)

    def test_unknown_quoted_operation_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "%0 = \"mystery.operation\"() : () -> i32\n", require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "unknown_operation",
                    "line": 1,
                    "column": 6,
                    "message": "unknown quoted operation: mystery.operation",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_malformed_quoted_operation_escape_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "%0 = \"math.\\6loor\"(%arg0) : (f64) -> f64\n", require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": 6,
                    "message": "malformed quoted operation: escape must contain two hexadecimal digits",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_unterminated_quoted_operation_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "%0 = \"math.floor(%arg0) : (f64) -> f64\n", require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(report["scanner_diagnostics"][0]["kind"], "malformed_quoted_operation")
        self.assertEqual(report["scanner_diagnostics"][0]["line"], 1)
        self.assertEqual(report["scanner_diagnostics"][0]["column"], 6)
        self.assert_valid_self_hash(report)

    def test_malformed_trivia_after_quoted_operation_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "%0 = \"math.floor\" / not-a-comment\n", require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "malformed_trivia",
                    "line": 1,
                    "column": 19,
                    "message": "malformed trivia after quoted operation",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_clean_scalar_mlir_has_exact_schema_v2_and_hash(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "%0 = arith.sitofp %arg0 : i32 to f32\n", require_clean=True
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(
            set(report),
            {
                "schema_version",
                "status",
                "prohibited_ops",
                "first_locations",
                "scanner_diagnostics",
                "sha256",
            },
        )
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_operation_names_in_comments_and_attribute_strings_are_not_counted(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "// math.floor arith.negf math.absi\n"
            "%0 = arith.constant 0 : i32 {note = \"math.floor and mystery.operation\"}\n"
            r'%1 = arith.constant 0 : i32 {note = "math.floor \" \\ \n \t"}'
            "\n",
            require_clean=True,
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_quoted_symbol_does_not_hide_neighboring_generic_operation(self) -> None:
        rc, report, stderr, _ = self.run_report(
            'module { func.func @"math.floor"(%arg0: f32) -> f32 { '
            '%0 = "math.floor"(%arg0) : (f32) -> f32 return %0 : f32 } }\n',
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": 60}},
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_location_string_does_not_hide_neighboring_generic_operation(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "module { func.func @main(%arg0: f32) -> f32 { "
            '%0 = "math.floor"(%arg0) : (f32) -> f32 '
            'return %0 : f32 } } loc("math.floor")\n',
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": 52}},
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_malformed_balanced_location_cannot_hide_generic_operations(self) -> None:
        rc, report, stderr, _ = self.run_report(
            'loc("safe" %0 = "math.floor"(%arg0) : (f32) -> f32)\n'
            'loc("safe" "mystery.operation"() : () -> ())\n',
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": 17}},
        )
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "malformed_location",
                    "line": 1,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "malformed_location",
                    "line": 2,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "unknown_operation",
                    "line": 2,
                    "column": 12,
                    "message": "unknown quoted operation: mystery.operation",
                },
            ],
        )
        self.assert_valid_self_hash(report)

    def test_unclosed_location_cannot_hide_nested_generic_operations(self) -> None:
        rc, report, stderr, _ = self.run_report(
            'loc("safe"\n'
            '%0 = "scf.execute_region"() ({\n'
            '  %1 = "math.floor"(%arg0) : (f32) -> f32\n'
            '  "mystery.operation"() : () -> ()\n'
            '}) : () -> f32\n',
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 3, "column": 8}},
        )
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "malformed_location",
                    "line": 1,
                    "column": 1,
                    "message": "unclosed location expression",
                },
                {
                    "kind": "unknown_operation",
                    "line": 4,
                    "column": 3,
                    "message": "unknown quoted operation: mystery.operation",
                },
            ],
        )
        self.assert_valid_self_hash(report)

    def test_malformed_callsite_location_cannot_hide_unknown_operation(self) -> None:
        rc, report, stderr, _ = self.run_report(
            'loc(callsite("safe" at "caller" '
            '"mystery.operation"() : () -> ()))\n',
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "malformed_location",
                    "line": 1,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "unknown_operation",
                    "line": 1,
                    "column": 33,
                    "message": "unknown quoted operation: mystery.operation",
                },
            ],
        )
        self.assert_valid_self_hash(report)

    def test_counts_multiple_and_nested_operations_on_one_line(self) -> None:
        mlir = (
            "module { func.func @main(%arg0: i32, %arg1: f32) -> f32 { "
            "%0 = arith.sitofp %arg0 : i32 to f32 "
            "%1 = math.floor %arg1 : f32 "
            "%2 = \"scf.execute_region\"() ({ %3 = math.floor %1 : f32 "
            "\"scf.yield\"(%3) : (f32) -> () }) : () -> f32 "
            "return %2 : f32 } }"
        )
        rc, report, stderr, _ = self.run_report(mlir, require_clean=True)

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": mlir.index("math.floor") + 1}},
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_accepts_result_group_trivia_before_generic_operation(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "module {\n"
            "  func.func @main(%arg0: f32) {\n"
            "    %r: 1 = \"math.floor\"(%arg0) : (f32) -> f32\n"
            "    return\n"
            "  }\n"
            "}\n",
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 3, "column": 13}},
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_multiline_attribute_key_is_not_an_operation(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "module attributes {\n"
            "  math.floor = \"not an operation\"\n"
            "} {\n"
            "  func.func @main() {\n"
            "    \"func.return\"() {math.floor} : () -> ()\n"
            "  }\n"
            "}\n",
            require_clean=True,
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_malformed_zero_result_generic_operation_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "\"math.floor\" / not-a-comment\n", require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": 1}},
        )
        self.assertEqual(len(report["scanner_diagnostics"]), 1)
        self.assertEqual(report["scanner_diagnostics"][0]["kind"], "malformed_trivia")
        self.assertEqual(report["scanner_diagnostics"][0]["line"], 1)
        self.assertEqual(report["scanner_diagnostics"][0]["column"], 14)
        self.assert_valid_self_hash(report)

    def test_unknown_custom_operations_fail_closed_with_and_without_results(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "mystery.zero_result\n"
            "%0 = mystery.with_result %arg0 : i32\n",
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(
            [diagnostic["kind"] for diagnostic in report["scanner_diagnostics"]],
            ["unknown_operation", "unknown_operation"],
        )
        self.assertEqual(
            [
                (diagnostic["line"], diagnostic["column"])
                for diagnostic in report["scanner_diagnostics"]
            ],
            [(1, 1), (2, 6)],
        )
        self.assert_valid_self_hash(report)


if __name__ == "__main__":
    unittest.main()
