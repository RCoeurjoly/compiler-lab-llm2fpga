import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "scripts" / "pipeline" / "calyx_preflight_report.py"
REPORT_SPEC = importlib.util.spec_from_file_location(
    "calyx_preflight_report_under_test", REPORT
)
assert REPORT_SPEC is not None and REPORT_SPEC.loader is not None
REPORT_MODULE = importlib.util.module_from_spec(REPORT_SPEC)
sys.modules[REPORT_SPEC.name] = REPORT_MODULE
REPORT_SPEC.loader.exec_module(REPORT_MODULE)

PURE_LOCATION_CORPUS = {
    "name": 'module { func.func @main() { return } } loc("math.floor")\n',
    "file_line": (
        'module { func.func @main() { return } } loc("math.floor":7)\n'
    ),
    "file_line_column": (
        'module { func.func @main() { return } } loc("math.floor":7:11)\n'
    ),
    "file_hex_line_column": (
        'module { func.func @main() { return } } loc("math.floor":0x7:0xB)\n'
    ),
    "file_range_same_line": (
        'module { func.func @main() { return } } '
        'loc("math.floor":7:11 to :19)\n'
    ),
    "file_range_multiple_lines": (
        'module { func.func @main() { return } } '
        'loc("math.floor":7:11 to 13:19)\n'
    ),
    "name_with_child": (
        'module { func.func @main() { return } } '
        'loc("outer"("math.floor":7:11))\n'
    ),
    "unknown": "module { func.func @main() { return } } loc(unknown)\n",
    "alias": (
        '#source = loc("math.floor":7:11)\n'
        "module { func.func @main() { return } } loc(#source)\n"
    ),
    "numeric_alias": (
        '#0 = loc("math.floor":7:11)\n'
        "module { func.func @main() { return } } loc(#0)\n"
    ),
    "alias_chain": (
        '#base = loc("math.floor":7:11)\n'
        "#source = #base\n"
        "module { func.func @main() { return } } loc(#source)\n"
    ),
    "callsite": (
        'module { func.func @main() { return } } '
        'loc(callsite("math.floor":7:11 at '
        '"mystery.operation"(unknown)))\n'
    ),
    "fused": (
        'module { func.func @main() { return } } '
        'loc(fused["math.floor":7:11, '
        '"mystery.operation"(unknown)])\n'
    ),
    "empty_fused": (
        "module { func.func @main() { return } } loc(fused[])\n"
    ),
}

PARSER_VALIDATED_LOCATION_CORPUS = {
    "fused_string_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<"math.floor">['
        '"mystery.operation":7:11, unknown])\n'
    ),
    "fused_structured_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<{description = "math.floor", frames = [1, 2]}>['
        '"mystery.operation":7:11])\n'
    ),
    "fused_typed_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<dense<[1, 2]> : tensor<2xi64>>['
        '"math.floor":7:11])\n'
    ),
    "fused_float_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<1.250000e+00 : f32>["math.floor":7:11])\n'
    ),
    "fused_location_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<loc("math.floor")>[unknown])\n'
    ),
    "fused_alias_metadata": (
        '#metadata = "math.floor"\n'
        "module { func.func @main() { return } } "
        "loc(fused<#metadata>[unknown])\n"
    ),
    "fused_distinct_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<distinct[0]<"math.floor">>[unknown])\n'
    ),
    "fused_dialect_metadata": (
        "module { func.func @main() { return } } "
        "loc(fused<#llvm.access_group<id = distinct[0]<>>>[unknown])\n"
    ),
    "nested": (
        '#source = loc("math.floor":7:11)\n'
        'module { func.func @main() { return } } '
        'loc(callsite(fused<"metadata">[#source, unknown] at '
        '"caller"(fused["mystery.operation", unknown])))\n'
    ),
}

VALID_LOCATION_CORPUS = {
    **PURE_LOCATION_CORPUS,
    **PARSER_VALIDATED_LOCATION_CORPUS,
}

MALFORMED_LOCATION_CORPUS = {
    "fused_missing_comma": (
        'module { func.func @main() { return } } '
        'loc(fused["safe" "math.floor"()])\n'
    ),
    "fused_unclosed_metadata": (
        'module { func.func @main() { return } } '
        'loc(fused<"metadata"["math.floor"()])\n'
    ),
    "fused_malformed_metadata_dictionary": (
        'module { func.func @main() { return } } '
        'loc(fused<{description "math.floor"()}>[unknown])\n'
    ),
    "callsite_missing_at": (
        'module { func.func @main() { return } } '
        'loc(callsite("callee" "math.floor"()))\n'
    ),
    "name_child_unbalanced": (
        'module { func.func @main() { return } } '
        'loc("name"("math.floor")\n'
    ),
    "file_integer_overflow": (
        'module { func.func @main() { return } } '
        'loc("math.floor":18446744073709551616:1)\n'
    ),
    "undefined_location_alias": (
        "module { func.func @main() { return } } loc(#missing)\n"
    ),
    "non_location_alias": (
        "#source = 42 : i64\n"
        "module { func.func @main() { return } } loc(#source)\n"
    ),
    "invalid_arbitrary_metadata": (
        "module { func.func @main() { return } } "
        'loc(fused<bogus("math.floor"() '
        '"mystery.operation"())>[unknown])\n'
    ),
}

LOCATION_NEIGHBORING_OPERATIONS = (
    "module {\n"
    "  func.func @main(%arg0: f32) -> f32 {\n"
    '    %0 = "math.floor"(%arg0) : (f32) -> f32\n'
    '    %1 = "scf.execute_region"() ({\n'
    '      %2 = "math.floor"(%0) : (f32) -> f32\n'
    '      "scf.yield"(%2) : (f32) -> ()\n'
    "    }) : () -> f32\n"
    "    return %1 : f32\n"
    "  }\n"
    '} loc(fused<"metadata">['
    '"math.floor", "mystery.operation"(unknown)])\n'
)

TOP_LEVEL_ARRAY_ALIAS_METADATA = (
    '#metadata = ["math.floor", "mystery.operation"]\n'
    "module { func.func @main() { return } } "
    "loc(fused<#metadata>[unknown])\n"
)

TOP_LEVEL_ARRAY_ALIAS_WITH_INVALID_OPERATION_NAME = (
    '#metadata = ["bad name"]\n'
    "module { func.func @main() { return } } "
    "loc(fused<#metadata>[unknown])\n"
)

TOP_LEVEL_INVALID_NAME_ALIAS_WITH_COMPACT_NEIGHBORS = (
    'module { func.func @before(%x: f32) -> f32 { %0 = "math.floor"(%x) '
    ": (f32) -> f32 return %0 : f32 } } "
    '#metadata = ["bad name"] '
    'module { func.func @after(%x: f32) -> f32 { %0 = "math.floor"(%x) '
    ": (f32) -> f32 return %0 : f32 } }\n"
)

INVALID_NAME_BOUNDED_DATA_CONTEXTS = (
    '#metadata = "bad name"\n'
    '#source = loc(callsite("bad name"(unknown) at '
    'fused["caller bad", unknown]))\n'
    'module attributes {math.note = "bad name", sym_name = "bad name"} { '
    'func.func @"bad name"() { "func.return"() '
    '{math.note = "bad name", sym_name = "bad name"} : () -> () } '
    '} loc(#source)\n'
)

INVALID_NAME_DIALECT_TYPE = (
    'module { func.func @main(%arg0: !llvm.struct<"bad name", (i32)>) '
    "{ return } }\n"
)

INVALID_NAME_COMPLEX_LOCATION_METADATA = (
    "module { func.func @main() { return } } "
    'loc(fused<"bad name">[unknown])\n'
)

TOP_LEVEL_ALIAS_WITH_COMPACT_NEIGHBORS = (
    'module { func.func @before(%x: f32) -> f32 { %0 = "math.floor"(%x) '
    ": (f32) -> f32 return %0 : f32 } } "
    '#metadata = [distinct[0]<"math.floor">, '
    "#llvm.access_group<id = distinct[1]<>>, "
    '"mystery.operation"] '
    'module { func.func @after(%x: f32) -> f32 { %0 = "math.floor"(%x) '
    ": (f32) -> f32 return %0 : f32 } }\n"
)


class CalyxPreflightReportTest(unittest.TestCase):
    def pinned_mlir_opt(self) -> str:
        mlir_opt = shutil.which("mlir-opt")
        if mlir_opt is None:
            self.skipTest("mlir-opt is available in the pinned Nix environment")
        return mlir_opt

    def run_report(
        self, mlir: str, *, require_clean: bool = False
    ) -> tuple[int, dict[str, object] | None, str, bytes | None]:
        report = REPORT_MODULE.build_report(mlir)
        output = (
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        rc = 1 if require_clean and report["status"] == "blocked" else 0
        return rc, report, "", output

    def run_cli_report(
        self,
        mlir: str,
        *,
        mlir_opt: str | None,
        bind_authorized_parser: bool = True,
        authorized_version: str = "21.1.2",
        authorized_sha256: str | None = None,
        require_clean: bool = False,
    ) -> tuple[int, dict[str, object] | None, str, bytes | None]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.mlir"
            output_path = Path(tmp) / "report.json"
            report_program = Path(tmp) / "calyx_preflight_report.py"
            input_path.write_text(mlir, encoding="utf-8")
            source = REPORT.read_text(encoding="utf-8")
            if bind_authorized_parser:
                authorized_path = Path(self.pinned_mlir_opt()).resolve(strict=True)
                source = source.replace(
                    "@calyxPreflightMlirOptPath@", str(authorized_path)
                )
                source = source.replace(
                    "@calyxPreflightMlirOptVersion@", authorized_version
                )
                source = source.replace(
                    "@calyxPreflightMlirOptSha256@",
                    authorized_sha256
                    or hashlib.sha256(authorized_path.read_bytes()).hexdigest(),
                )
            report_program.write_text(source, encoding="utf-8")
            cmd = [
                sys.executable,
                str(report_program),
                str(input_path),
                str(output_path),
            ]
            if mlir_opt is not None:
                cmd.extend(["--mlir-opt", mlir_opt])
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

    def test_pinned_mlir_parser_accepts_complete_builtin_location_corpus(self) -> None:
        mlir_opt = self.pinned_mlir_opt()

        version = subprocess.run(
            [mlir_opt, "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertIn("LLVM version 21.1.2", version.stdout)

        for name, mlir in VALID_LOCATION_CORPUS.items():
            with self.subTest(location=name):
                parsed = subprocess.run(
                    [mlir_opt, "-o", "/dev/null"],
                    input=mlir,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(parsed.returncode, 0, parsed.stderr)

        for name, mlir in MALFORMED_LOCATION_CORPUS.items():
            with self.subTest(mutation=name):
                parsed = subprocess.run(
                    [mlir_opt, "-o", "/dev/null"],
                    input=mlir,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertNotEqual(parsed.returncode, 0, mlir)

        parsed = subprocess.run(
            [mlir_opt, "-o", "/dev/null"],
            input=LOCATION_NEIGHBORING_OPERATIONS,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)

    def test_pure_api_accepts_only_bounded_builtin_locations_as_data(self) -> None:
        for name, mlir in PURE_LOCATION_CORPUS.items():
            with self.subTest(location=name):
                rc, report, stderr, _ = self.run_report(
                    mlir, require_clean=True
                )

                self.assertEqual(rc, 0, stderr)
                self.assertIsNotNone(report)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["prohibited_ops"], {})
                self.assertEqual(report["first_locations"], {})
                self.assertEqual(report["scanner_diagnostics"], [])
                self.assert_valid_self_hash(report)

    def test_cli_uses_pinned_parser_to_authorize_complex_location_metadata(self) -> None:
        mlir_opt = self.pinned_mlir_opt()

        for name, mlir in PARSER_VALIDATED_LOCATION_CORPUS.items():
            with self.subTest(location=name):
                rc, report, stderr, _ = self.run_cli_report(
                    mlir, mlir_opt=mlir_opt, require_clean=True
                )

                self.assertEqual(rc, 0, stderr)
                self.assertIsNotNone(report)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["prohibited_ops"], {})
                self.assertEqual(report["first_locations"], {})
                self.assertEqual(report["scanner_diagnostics"], [])
                self.assert_valid_self_hash(report)

    def test_cli_binds_successful_parse_to_authorized_parser_identity(self) -> None:
        mlir_opt = self.pinned_mlir_opt()

        rc, report, stderr, _ = self.run_cli_report(
            "module { func.func @main() { return } }\n",
            mlir_opt=mlir_opt,
            require_clean=True,
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["schema_version"], 3)
        self.assertIn("parser_validation", report)
        validation = report["parser_validation"]
        self.assertEqual(validation["identity_status"], "verified")
        self.assertEqual(validation["input_status"], "accepted")
        authorized = validation["authorized_identity"]
        observed = validation["observed_identity"]
        canonical = str(Path(mlir_opt).resolve(strict=True))
        self.assertEqual(authorized["canonical_path"], canonical)
        self.assertEqual(observed["canonical_path"], canonical)
        self.assertEqual(
            observed["sha256"],
            hashlib.sha256(Path(canonical).read_bytes()).hexdigest(),
        )
        self.assertEqual(observed["sha256"], authorized["sha256"])
        self.assertEqual(authorized["version"], "21.1.2")
        self.assertIn("LLVM version 21.1.2", observed["version_output"])
        self.assert_valid_self_hash(report)

    def test_exit_zero_non_parser_cannot_self_authorize(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            MALFORMED_LOCATION_CORPUS["invalid_arbitrary_metadata"],
            mlir_opt="/bin/true",
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["parser_validation"]["identity_status"], "mismatch"
        )
        self.assertEqual(
            report["parser_validation"]["input_status"], "not_run"
        )
        self.assertEqual(
            report["parser_validation"]["observed_identity"]["canonical_path"],
            str(Path("/bin/true").resolve(strict=True)),
        )
        self.assertEqual(
            report["scanner_diagnostics"][0]["kind"],
            "mlir_parser_identity_mismatch",
        )
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assert_valid_self_hash(report)

    def test_version_spoofing_parser_wrapper_cannot_self_authorize(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "mlir-opt"
            wrapper.write_text(
                "#!/usr/bin/env bash\n"
                "if [[ \"${1:-}\" == \"--version\" ]]; then\n"
                "  printf 'LLVM version 21.1.2\\n'\n"
                "fi\n"
                "exit 0\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            rc, report, stderr, _ = self.run_cli_report(
                MALFORMED_LOCATION_CORPUS["invalid_arbitrary_metadata"],
                mlir_opt=str(wrapper),
                require_clean=True,
            )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["parser_validation"]["identity_status"], "mismatch"
        )
        self.assertEqual(
            report["scanner_diagnostics"][0]["kind"],
            "mlir_parser_identity_mismatch",
        )
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assert_valid_self_hash(report)

    def test_authorized_parser_hash_is_checked_before_parsing(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            MALFORMED_LOCATION_CORPUS["invalid_arbitrary_metadata"],
            mlir_opt=self.pinned_mlir_opt(),
            authorized_sha256="0" * 64,
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(
            report["parser_validation"]["identity_status"], "mismatch"
        )
        self.assertEqual(
            report["parser_validation"]["input_status"], "not_run"
        )
        self.assertEqual(
            report["scanner_diagnostics"][0]["kind"],
            "mlir_parser_identity_mismatch",
        )
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assert_valid_self_hash(report)

    def test_authorized_parser_version_output_is_checked_before_parsing(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            MALFORMED_LOCATION_CORPUS["invalid_arbitrary_metadata"],
            mlir_opt=self.pinned_mlir_opt(),
            authorized_version="0.0.0",
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        validation = report["parser_validation"]
        self.assertEqual(validation["identity_status"], "mismatch")
        self.assertEqual(validation["input_status"], "not_run")
        self.assertIn(
            "LLVM version 21.1.2",
            validation["observed_identity"]["version_output"],
        )
        self.assertEqual(
            report["scanner_diagnostics"][0]["kind"],
            "mlir_parser_identity_mismatch",
        )
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assert_valid_self_hash(report)

    def test_validated_top_level_array_alias_rhs_is_data(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            TOP_LEVEL_ARRAY_ALIAS_METADATA,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_validated_alias_string_with_invalid_operation_name_is_data(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            TOP_LEVEL_ARRAY_ALIAS_WITH_INVALID_OPERATION_NAME,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )

        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_unvalidated_invalid_name_alias_stays_visible_between_true_operations(self) -> None:
        mlir = TOP_LEVEL_INVALID_NAME_ALIAS_WITH_COMPACT_NEIGHBORS
        rc, report, stderr, _ = self.run_report(mlir, require_clean=True)

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        self.assertEqual(
            report["first_locations"],
            {
                "math.floor": {
                    "line": 1,
                    "column": mlir.index('"math.floor"') + 1,
                }
            },
        )
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": mlir.index('"bad name"') + 1,
                    "message": "malformed quoted operation: invalid operation name",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_validated_invalid_name_alias_is_data_between_true_operations(self) -> None:
        mlir = TOP_LEVEL_INVALID_NAME_ALIAS_WITH_COMPACT_NEIGHBORS
        rc, report, stderr, _ = self.run_cli_report(
            mlir,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        self.assertEqual(
            report["first_locations"],
            {
                "math.floor": {
                    "line": 1,
                    "column": mlir.index('"math.floor"') + 1,
                }
            },
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_validated_alias_rhs_does_not_hide_compact_neighbor_operations(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            TOP_LEVEL_ALIAS_WITH_COMPACT_NEIGHBORS,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": 51}},
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_unvalidated_alias_rhs_remains_fail_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            TOP_LEVEL_ARRAY_ALIAS_METADATA, require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertIn(
            "unknown_operation",
            [item["kind"] for item in report["scanner_diagnostics"]],
        )
        self.assert_valid_self_hash(report)

    def test_rejected_alias_mutation_cannot_hide_rhs_or_following_operation(self) -> None:
        mlir = (
            '#metadata = ["math.floor", "mystery.operation"\n'
            'module { func.func @main(%x: f32) -> f32 { %0 = "math.floor"(%x) '
            ": (f32) -> f32 return %0 : f32 } }\n"
        )
        rc, report, stderr, _ = self.run_cli_report(
            mlir,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        diagnostic_kinds = [
            item["kind"] for item in report["scanner_diagnostics"]
        ]
        self.assertEqual(diagnostic_kinds[0], "mlir_parser_rejected")
        self.assertIn("unknown_operation", diagnostic_kinds)
        self.assert_valid_self_hash(report)

    def test_pure_api_refuses_unvalidated_arbitrary_location_metadata(self) -> None:
        mlir = MALFORMED_LOCATION_CORPUS["invalid_arbitrary_metadata"]
        rc, report, stderr, _ = self.run_report(mlir, require_clean=True)

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            [diagnostic["kind"] for diagnostic in report["scanner_diagnostics"]],
            ["malformed_location", "unknown_operation"],
        )
        self.assert_valid_self_hash(report)

    def test_parser_rejection_blocks_without_hiding_metadata_operations(self) -> None:
        mlir_opt = self.pinned_mlir_opt()
        mlir = MALFORMED_LOCATION_CORPUS["invalid_arbitrary_metadata"]

        rc, report, stderr, output = self.run_cli_report(
            mlir, mlir_opt=mlir_opt, require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            [diagnostic["kind"] for diagnostic in report["scanner_diagnostics"]],
            [
                "mlir_parser_rejected",
                "malformed_location",
                "unknown_operation",
            ],
        )
        self.assertEqual(
            report["scanner_diagnostics"][0]["message"],
            "authorized MLIR parser rejected input",
        )
        self.assert_valid_self_hash(report)

        rc2, report2, stderr2, output2 = self.run_cli_report(
            mlir, mlir_opt=mlir_opt, require_clean=True
        )
        self.assertEqual(rc2, 1, stderr2)
        self.assertEqual(report2, report)
        self.assertEqual(output2, output)

    def test_parser_rejection_keeps_operations_outside_and_after_location_visible(self) -> None:
        mlir = (
            "module { func.func @main(%arg0: f32) -> f32 { "
            '%0 = "math.floor"(%arg0) : (f32) -> f32 '
            "return %0 : f32 } } "
            'loc(fused<bogus("metadata")>[unknown])\n'
            '"mystery.operation"() : () -> ()\n'
        )
        rc, report, stderr, _ = self.run_cli_report(
            mlir, mlir_opt=self.pinned_mlir_opt(), require_clean=True
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["prohibited_ops"], {"math.floor": 1})
        self.assertEqual(
            [diagnostic["kind"] for diagnostic in report["scanner_diagnostics"]],
            [
                "mlir_parser_rejected",
                "malformed_location",
                "malformed_quoted_operation",
                "unknown_operation",
            ],
        )
        self.assert_valid_self_hash(report)

    def test_unbound_parser_identity_is_a_deterministic_blocker(self) -> None:
        mlir = "module { func.func @main() { return } }\n"

        rc, report, stderr, output = self.run_cli_report(
            mlir,
            mlir_opt=None,
            bind_authorized_parser=False,
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "mlir_parser_identity_unbound",
                    "line": 1,
                    "column": 1,
                    "message": "authorized MLIR parser identity is not bound by Nix",
                }
            ],
        )
        self.assertEqual(
            report["parser_validation"],
            {
                "authorized_identity": None,
                "identity_status": "unbound",
                "input_status": "not_run",
                "observed_identity": None,
            },
        )
        self.assert_valid_self_hash(report)

        rc2, report2, stderr2, output2 = self.run_cli_report(
            mlir,
            mlir_opt=None,
            bind_authorized_parser=False,
            require_clean=True,
        )
        self.assertEqual(rc2, 1, stderr2)
        self.assertEqual(report2, report)
        self.assertEqual(output2, output)

    def test_missing_authorized_parser_candidate_is_a_deterministic_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-mlir-opt"
            rc, report, stderr, _ = self.run_cli_report(
                "module { func.func @main() { return } }\n",
                mlir_opt=str(missing),
                require_clean=True,
            )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(
            report["parser_validation"]["identity_status"], "unavailable"
        )
        self.assertEqual(
            report["parser_validation"]["input_status"], "not_run"
        )
        self.assertEqual(
            report["scanner_diagnostics"],
            [
                {
                    "kind": "mlir_parser_unavailable",
                    "line": 1,
                    "column": 1,
                    "message": "authorized MLIR parser could not be resolved",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_malformed_fused_locations_block_without_hiding_operations(self) -> None:
        mlir = (
            'loc(fused<"safe" "math.floor"()>[unknown])\n'
            'loc(fused<{description "attribute.data"}>[unknown])\n'
            'loc(fused["safe" "mystery.operation"()])\n'
            'loc("math.floor":18446744073709551616:1)\n'
        )
        rc, report, stderr, output = self.run_report(mlir, require_clean=True)

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 1, "column": 18}},
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
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": 11,
                    "message": "malformed quoted operation: invalid operation name",
                },
                {
                    "kind": "malformed_location",
                    "line": 2,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "malformed_location",
                    "line": 3,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "malformed_quoted_operation",
                    "line": 3,
                    "column": 11,
                    "message": "malformed quoted operation: invalid operation name",
                },
                {
                    "kind": "unknown_operation",
                    "line": 3,
                    "column": 18,
                    "message": "unknown quoted operation: mystery.operation",
                },
                {
                    "kind": "malformed_location",
                    "line": 4,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "malformed_trivia",
                    "line": 4,
                    "column": 17,
                    "message": "malformed trivia after quoted operation",
                },
            ],
        )
        self.assert_valid_self_hash(report)

        rc2, report2, stderr2, output2 = self.run_report(
            mlir, require_clean=True
        )
        self.assertEqual(rc2, 1, stderr2)
        self.assertEqual(report2, report)
        self.assertEqual(output2, output)

    def test_invalid_location_aliases_block_and_keep_following_operation_visible(self) -> None:
        rc, report, stderr, _ = self.run_report(
            "loc(#missing)\n"
            "#source = 42 : i64\n"
            "loc(#source)\n"
            '"mystery.operation"() : () -> ()\n',
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
                    "kind": "malformed_location",
                    "line": 3,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "unknown_operation",
                    "line": 4,
                    "column": 1,
                    "message": "unknown quoted operation: mystery.operation",
                },
            ],
        )
        self.assert_valid_self_hash(report)

    def test_validated_fused_location_keeps_nested_generic_operations_visible(self) -> None:
        rc, report, stderr, _ = self.run_cli_report(
            LOCATION_NEIGHBORING_OPERATIONS,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )

        self.assertEqual(rc, 1, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["prohibited_ops"], {"math.floor": 2})
        self.assertEqual(
            report["first_locations"],
            {"math.floor": {"line": 3, "column": 10}},
        )
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

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
        self.assertEqual(report["schema_version"], 3)
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

    def test_malformed_zero_result_quoted_operation_name_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            '"bad name"() : () -> ()\n', require_clean=True
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
                    "column": 1,
                    "message": "malformed quoted operation: invalid operation name",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_standalone_malformed_quoted_operation_name_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            '"bad name"\n', require_clean=True
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
                    "column": 1,
                    "message": "malformed quoted operation: invalid operation name",
                }
            ],
        )
        self.assert_valid_self_hash(report)

    def test_malformed_name_with_bad_post_name_trivia_fails_closed(self) -> None:
        rc, report, stderr, _ = self.run_report(
            '"bad name" / not-a-comment\n', require_clean=True
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
                    "column": 1,
                    "message": "malformed quoted operation: invalid operation name",
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

    def test_clean_scalar_mlir_has_exact_schema_v3_and_hash(self) -> None:
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
                "parser_validation",
                "sha256",
            },
        )
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(
            report["parser_validation"],
            {
                "authorized_identity": None,
                "identity_status": "not_run",
                "input_status": "not_run",
                "observed_identity": None,
            },
        )
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

    def test_invalid_operation_name_strings_in_valid_data_contexts_are_not_operations(self) -> None:
        mlir = INVALID_NAME_BOUNDED_DATA_CONTEXTS
        cli_rc, cli_report, cli_stderr, _ = self.run_cli_report(
            mlir,
            mlir_opt=self.pinned_mlir_opt(),
            require_clean=True,
        )
        rc, report, stderr, _ = self.run_report(mlir, require_clean=True)

        self.assertEqual(cli_rc, 0, cli_stderr)
        self.assertIsNotNone(cli_report)
        self.assertEqual(cli_report["status"], "ok")
        self.assertEqual(cli_report["prohibited_ops"], {})
        self.assertEqual(cli_report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(cli_report)
        self.assertEqual(rc, 0, stderr)
        self.assertIsNotNone(report)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["prohibited_ops"], {})
        self.assertEqual(report["first_locations"], {})
        self.assertEqual(report["scanner_diagnostics"], [])
        self.assert_valid_self_hash(report)

    def test_unvalidated_dialect_type_and_complex_metadata_strings_stay_conservative(self) -> None:
        cases = {
            "dialect_type": (
                INVALID_NAME_DIALECT_TYPE,
                ["malformed_quoted_operation"],
            ),
            "complex_location_metadata": (
                INVALID_NAME_COMPLEX_LOCATION_METADATA,
                ["malformed_location", "malformed_quoted_operation"],
            ),
        }
        for name, (mlir, expected_kinds) in cases.items():
            with self.subTest(context=name):
                rc, report, stderr, _ = self.run_report(
                    mlir, require_clean=True
                )

                self.assertEqual(rc, 1, stderr)
                self.assertIsNotNone(report)
                self.assertEqual(report["status"], "blocked")
                self.assertEqual(report["prohibited_ops"], {})
                self.assertEqual(
                    [
                        diagnostic["kind"]
                        for diagnostic in report["scanner_diagnostics"]
                    ],
                    expected_kinds,
                )
                self.assert_valid_self_hash(report)

    def test_parser_validated_dialect_type_and_metadata_strings_are_data(self) -> None:
        for name, mlir in {
            "dialect_type": INVALID_NAME_DIALECT_TYPE,
            "complex_location_metadata": INVALID_NAME_COMPLEX_LOCATION_METADATA,
        }.items():
            with self.subTest(context=name):
                rc, report, stderr, _ = self.run_cli_report(
                    mlir,
                    mlir_opt=self.pinned_mlir_opt(),
                    require_clean=True,
                )

                self.assertEqual(rc, 0, stderr)
                self.assertIsNotNone(report)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["prohibited_ops"], {})
                self.assertEqual(report["first_locations"], {})
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
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": 5,
                    "message": "malformed quoted operation: invalid operation name",
                },
                {
                    "kind": "malformed_location",
                    "line": 2,
                    "column": 1,
                    "message": "malformed location expression",
                },
                {
                    "kind": "malformed_quoted_operation",
                    "line": 2,
                    "column": 5,
                    "message": "malformed quoted operation: invalid operation name",
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
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": 5,
                    "message": "malformed quoted operation: invalid operation name",
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
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": 14,
                    "message": "malformed quoted operation: invalid operation name",
                },
                {
                    "kind": "malformed_quoted_operation",
                    "line": 1,
                    "column": 24,
                    "message": "malformed quoted operation: invalid operation name",
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
