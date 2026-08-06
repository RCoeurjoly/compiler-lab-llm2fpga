import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/run_rc_sv_equivalence.py"
VERILATOR_5022 = Path(
    "/nix/store/7mil9l34vfbvmh0cm6wvbdapwv77bz9v-verilator-5.022/bin/verilator"
)
spec = importlib.util.spec_from_file_location("run_rc_sv_equivalence", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RcObservableDriverTest(unittest.TestCase):
    """Behavior tests for the payload-neutral observable-shard driver."""

    @staticmethod
    def _ports():
        ports = {number: (32, 2) for number in range(146)}
        ports[25] = (64, 8)
        ports[26] = (8, 64)
        ports[44] = (32, 32)
        ports[45] = (32, 16)
        for number in range(46, 146):
            ports[number] = (8, 64)
        return ports

    @classmethod
    def _sv(cls):
        declarations = [
            "  input logic clk",
            "  input logic reset",
            "  input logic go",
            "  output logic done",
        ]
        assignments = []
        immutable = set(range(25)) | set(range(27, 46)) | {25}
        for number, (width, depth) in sorted(cls._ports().items()):
            addr_width = max(1, (depth - 1).bit_length())

            def pin(direction, pin_name, pin_width):
                packed = f" [{pin_width - 1}:0]" if pin_width > 1 else ""
                return f"  {direction} logic{packed} arg_mem_{number}_{pin_name}"

            declarations.extend([
                pin("output", "addr0", addr_width),
                pin("output", "content_en", 1),
                pin("output", "write_en", 1),
                pin("output", "write_data", width),
                pin("input", "read_data", width),
                pin("input", "done", 1),
            ])
            expression = "1'b0" if number in immutable else "1'b1"
            assignments.append(f"assign arg_mem_{number}_write_en = {expression};")
        return (
            "module main_1(\n"
            + ",\n".join(declarations)
            + "\n);\n"
            + "assign done = 1'b0;\n"
            + "\n".join(assignments)
            + "\nendmodule\n"
        )

    @staticmethod
    def _image_and_manifest():
        segments = []
        payload = bytearray()

        def append(name, *, dtype, shape, byte_length):
            offset = len(payload)
            payload.extend(range(byte_length))
            segments.append({
                "name": name,
                "offset": offset,
                "byte_length": byte_length,
                "source_category": "state",
                "dtype": dtype,
                "shape": shape,
            })

        for number in range(21):
            append(f"state/_frozen_param{number}", dtype="int8", shape=[4], byte_length=4)
        for name in (
            "state/transformer.h.0.attn.attention.bias",
            "state/transformer.h.0.attn.attention.lifted_tensor_0",
            "state/transformer.h.1.attn.attention.bias",
            "state/transformer.h.1.attn.attention.lifted_tensor_1",
        ):
            append(name, dtype="float32", shape=[1], byte_length=4)
        for number in range(16):
            append(f"state/external_2_{number:02d}", dtype="float32", shape=[2], byte_length=8)
        append("state/external_18", dtype="float32", shape=[18], byte_length=72)
        append("state/external_12", dtype="float32", shape=[12], byte_length=48)
        return bytes(payload), {"segments": segments}

    @staticmethod
    def _source_ir(image, manifest):
        selected = [
            *(f"state/external_2_{number:02d}" for number in range(16)),
            "state/external_18",
            "state/external_12",
        ]
        by_name = {segment["name"]: segment for segment in manifest["segments"]}
        declarations = [
            '  memref.global "private" constant @scalar_zero : memref<f32> = '
            'dense<0.000000e+00> {alignment = 64 : i64}'
        ]
        resources = []
        gets = ["    %0 = memref.get_global @scalar_zero : memref<f32>"]
        for ordinal, name in enumerate(selected, start=1):
            segment = by_name[name]
            shape = segment["shape"]
            shape_text = "x".join(map(str, shape))
            symbol = f"external_{ordinal}"
            resource = f"resource_{ordinal}"
            raw = image[
                segment["offset"] : segment["offset"] + segment["byte_length"]
            ]
            declarations.append(
                f'  memref.global "private" constant @{symbol} : '
                f"memref<{shape_text}xf32> = dense_resource<{resource}> "
                "{alignment = 64 : i64}"
            )
            resources.append(
                f'      {resource}: "0x{(b"\x04\x00\x00\x00" + raw).hex().upper()}"'
            )
            gets.append(
                f"    %{ordinal} = memref.get_global @{symbol} : "
                f"memref<{shape_text}xf32>"
            )
        flat_scf = (
            "module {\n" + "\n".join(declarations)
            + "\n}\n\n{-#\n  dialect_resources: {\n    builtin: {\n"
            + ",\n".join(resources) + "\n    }\n  }\n#-}\n"
        )
        pre_calyx = (
            "module {\n  func.func @main() {\n" + "\n".join(gets) + "\n  }\n}\n"
        )
        return flat_scf.encode("utf-8"), pre_calyx.encode("utf-8")

    @classmethod
    def _binding_receipt(cls, image, manifest, sv=None):
        flat_scf, pre_calyx = cls._source_ir(image, manifest)
        manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
        return module._build_calyx_memory_bindings(
            flat_scf=flat_scf,
            pre_calyx=pre_calyx,
            image=image,
            manifest=manifest,
            abi=module._memory_abi(cls._sv() if sv is None else sv),
            manifest_bytes=manifest_bytes,
        )

    @staticmethod
    def _rehash_memory_abi_receipt(receipt):
        rows = receipt["ports"]
        receipt["canonical_json"] = json.dumps(
            rows, sort_keys=True, separators=(",", ":")
        )
        receipt["sha256"] = hashlib.sha256(
            receipt["canonical_json"].encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _rehash_calyx_memory_bindings(receipt):
        payload_keys = (
            "schema", "flat_scf_sha256", "pre_calyx_sha256", "image_sha256",
            "image_manifest_sha256", "memory_abi_sha256", "ports",
        )
        payload = {key: receipt[key] for key in payload_keys}
        receipt["canonical_json"] = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        )
        receipt["sha256"] = hashlib.sha256(
            receipt["canonical_json"].encode("utf-8")
        ).hexdigest()

    @classmethod
    def _frozen_reducer_receipts(cls):
        """Build fully structured strict receipts for reducer contract tests."""

        image, manifest = cls._image_and_manifest()
        flat_scf, pre_calyx = cls._source_ir(image, manifest)
        sv = cls._sv()
        memory_abi = module._memory_abi_receipt(module._memory_abi(sv))
        bindings = cls._binding_receipt(image, manifest, sv)
        proof = hashlib.sha256(b"frozen-reducer-proof").hexdigest()
        inputs = {
            "sv_sha256": hashlib.sha256(sv.encode("utf-8")).hexdigest(),
            "image_sha256": hashlib.sha256(image).hexdigest(),
            "manifest_sha256": hashlib.sha256(
                json.dumps(manifest, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "flat_scf_sha256": hashlib.sha256(flat_scf).hexdigest(),
            "pre_calyx_sha256": hashlib.sha256(pre_calyx).hexdigest(),
        }
        sv_receipt = {
            "raw_sha256": inputs["sv_sha256"],
            "normalized_sha256": hashlib.sha256(
                module._normalized_sv_text(sv).encode("utf-8")
            ).hexdigest(),
        }
        fixture_sha256 = hashlib.sha256(b"strict-frozen-fixture").hexdigest()
        configuration = {
            "verilate_jobs": 4,
            "build_jobs": 4,
            "verilator_threads": 1,
            "verilator_output_split": 100,
            "verilator_output_split_cfuncs": 50,
            "fixture_schema": module.STRICT_FIXTURE_SCHEMA,
            "f32_constant_bits_sha256": proof,
            "calyx_memory_bindings_sha256": bindings["sha256"],
        }
        cache_identity = {
            "fixture": {
                "mode": "observable-shard-generic",
                "fixture_schema": module.STRICT_FIXTURE_SCHEMA,
            },
            "f32_constant_bits_sha256": proof,
            "calyx_memory_bindings_sha256": bindings["sha256"],
        }
        cache_hashes = {
            "raw_sv_sha256": sv_receipt["raw_sha256"],
            "normalized_sv_sha256": sv_receipt["normalized_sha256"],
            "fixture_sha256": fixture_sha256,
            "binary_sha256": hashlib.sha256(b"Vtb").hexdigest(),
            "memory_abi_sha256": hashlib.sha256(
                (memory_abi["canonical_json"] + "\n").encode("utf-8")
            ).hexdigest(),
            "runtime_memory_sha256": hashlib.sha256(b"runtime-memories").hexdigest(),
            "calyx_memory_bindings_sha256": bindings["sha256"],
        }

        def case(index, cycles, ordinal):
            return {
                "index": index,
                "cycles": cycles,
                "expected_codes_i8": [0, 1, 2, 3, 4, 5],
                "observed_codes_i8": [0, 1, 2, 3, 4, 5],
                "expected_token": 5,
                "observed_token": 5,
                "write_mask": "111111",
                "completion": {
                    "done": True,
                    "completion_count": 1,
                    "within_bound": True,
                    "reset": {"complete": True, "cycles": 3, "ordinal": ordinal},
                },
                "reset": {"complete": True, "cycles": 3, "ordinal": ordinal},
            }

        def strict_receipt(*, cases, oracle, completed, reset_count=None):
            receipt = {
                "schema": module.STRICT_RESULT_SCHEMA,
                "status": "pass",
                "completed": completed,
                "cases": cases,
                "f32_constant_bits": {"sha256": proof},
                "oracle": oracle,
                "runner_sha256": hashlib.sha256(b"strict-runner").hexdigest(),
                "inputs": dict(inputs),
                "sv": dict(sv_receipt),
                "fixture_sha256": fixture_sha256,
                "configuration": dict(configuration),
                "cache_identity": json.loads(json.dumps(cache_identity)),
                "cache_hashes": dict(cache_hashes),
                "calyx_memory_bindings": json.loads(json.dumps(bindings)),
                "memory_abi": json.loads(json.dumps(memory_abi)),
                "simulator": {"name": "verilator", "version": "test"},
                "cycle_bound": 1_000_000,
            }
            if reset_count is not None:
                receipt["reset_count"] = reset_count
            return receipt

        names = ["ascending", "zeros"]
        metadata_sha256 = {
            name: hashlib.sha256(f"{name}:metadata".encode("utf-8")).hexdigest()
            for name in names
        }
        payload_sha256 = {
            name: hashlib.sha256(f"{name}:payload".encode("utf-8")).hexdigest()
            for name in names
        }
        oracle_receipt = {
            "artifacts": {
                "image_sha256": inputs["image_sha256"],
                "image_manifest_sha256": inputs["manifest_sha256"],
            },
        }
        fresh = {
            name: strict_receipt(
                cases=[case(4 + ordinal, 12 + ordinal, 1)],
                completed=1,
                oracle={
                    "metadata_sha256": metadata_sha256[name],
                    "payload_sha256": payload_sha256[name],
                    "receipt": json.loads(json.dumps(oracle_receipt)),
                },
            )
            for ordinal, name in enumerate(names)
        }
        sequential = strict_receipt(
            cases=[case(4 + ordinal, 12 + ordinal, ordinal + 1) for ordinal in range(len(names))],
            completed=len(names),
            reset_count=len(names),
            oracle={
                "kind": "sparse-sequence",
                "components": [
                    {
                        "metadata_sha256": metadata_sha256[name],
                        "payload_sha256": payload_sha256[name],
                        "receipt": json.loads(json.dumps(oracle_receipt)),
                    }
                    for name in names
                ],
            },
        )
        return names, proof, fresh, sequential

    def _strict_fixture_text(self):
        image, manifest = self._image_and_manifest()
        with tempfile.TemporaryDirectory() as directory:
            fixture = module._strict_fixture(
                self._sv(), image, manifest, Path(directory), cycle_bound=123,
                calyx_memory_bindings=self._binding_receipt(image, manifest),
            )
            return fixture.read_text(encoding="utf-8")

    def test_equivalence_cli_rejects_early_output_diagnostic(self):
        """Catches allowing a diagnostic completion shortcut in proof mode."""

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.main_from_args([
                "--equivalence-shard", "oracle.json", "--stop-after-output",
            ])

    def test_fixture_requires_done_all_final_writes_and_stable_sampling(self):
        """Catches a generic fixture that accepts an early or partial output."""

        tb = self._strict_fixture_text()
        self.assertIn("final_write_mask == 6'b111111", tb)
        self.assertIn("TIMEOUT", tb)
        self.assertIn("LATE_FINAL_WRITE", tb)
        self.assertIn("repeat (2) @(posedge clk);", tb)
        self.assertIn("ORACLE_RECORD_ARGMAX", tb)
        self.assertIn("launch_cycle = clock_cycle", tb)
        self.assertIn("done_cycle = clock_cycle", tb)
        self.assertIn("completion_count_at_done = completion_count", tb)
        self.assertIn("reset_complete=1 reset_cycles=3 reset_ordinal=%0d", tb)
        self.assertIn("SEQUENCE_PASS", tb)
        self.assertIn('$fopen(oracle_path, "r")', tb)
        self.assertIn('$fscanf(oracle_fd, "%h", expected_record)', tb)
        self.assertIn('$readmemh("mem0.hex", mem0);', tb)
        self.assertNotIn("ascending", tb)
        self.assertNotIn("token_ids", tb)

    def test_strict_failure_dumps_complete_output_tensor(self):
        """Catches losing the terminal tensor needed to localize a raw-code mismatch."""

        tb = self._strict_fixture_text()
        self.assertIn("OUTPUT_TENSOR context=%0d", tb)
        self.assertIn("for (lane = 0; lane < 48; lane = lane + 1)", tb)

    def test_strict_fixture_lints_with_project_verilator_5022(self):
        """Catches malformed generated control flow before a real build."""

        self.assertTrue(VERILATOR_5022.is_file())
        image, manifest = self._image_and_manifest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.sv"
            source.write_text(self._sv(), encoding="utf-8")
            fixture = module._strict_fixture(
                self._sv(), image, manifest, root, cycle_bound=123,
                calyx_memory_bindings=self._binding_receipt(image, manifest),
            )
            completed = subprocess.run(
                [
                    str(VERILATOR_5022),
                    "--lint-only",
                    "--timing",
                    "--Wno-fatal",
                    "--top-module",
                    "tb",
                    str(source),
                    str(fixture),
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_parser_rejects_zero_exit_without_case_pass(self):
        """Catches treating simulator $finish as a successful shard result."""

        with self.assertRaisesRegex(RuntimeError, "missing CASE_PASS"):
            module._parse_shard_output(
                "- tb.sv: $finish", expected_count=1, cycle_bound=1_000_000
            )

    def test_parser_requires_contiguous_indexes_and_a_matching_shard_terminal(self):
        """Catches dropped/duplicated contexts hidden behind a SHARD_PASS line."""

        output = "\n".join([
            "CASE_PASS index=4 cycles=12 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
            "CASE_PASS index=6 cycles=13 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
            "SHARD_PASS start=4 count=2 completed=2 min_cycles=12 max_cycles=13",
        ])
        with self.assertRaisesRegex(RuntimeError, "contiguous"):
            module._parse_shard_output(
                output, expected_start=4, expected_count=2, cycle_bound=1_000_000
            )

    def test_parser_returns_latency_summary_for_valid_shard(self):
        """Catches a receipt with no independently parsed completion evidence."""

        output = "\n".join([
            "CASE_PASS index=4 cycles=12 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
            "CASE_PASS index=5 cycles=13 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
            "SHARD_PASS start=4 count=2 completed=2 min_cycles=12 max_cycles=13",
        ])
        parsed = module._parse_shard_output(
            output, expected_start=4, expected_count=2, cycle_bound=1_000_000
        )
        self.assertEqual(parsed["completed"], 2)
        self.assertEqual(parsed["min_cycles"], 12)
        self.assertEqual(parsed["max_cycles"], 13)

    def test_parser_rejects_case_cycles_outside_the_requested_bound(self):
        """Catches accepting a transcript whose case violates its receipt bound."""

        for cycles in (0, 13):
            with self.subTest(cycles=cycles):
                output = "\n".join([
                    f"CASE_PASS index=4 cycles={cycles} expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
                    f"SHARD_PASS start=4 count=1 completed=1 min_cycles={cycles} max_cycles={cycles}",
                ])
                with self.assertRaisesRegex(RuntimeError, "cycle bound"):
                    module._parse_shard_output(
                        output,
                        expected_start=4,
                        expected_count=1,
                        cycle_bound=12,
                    )

    def test_parser_rejects_case_pass_after_shard_summary(self):
        """Catches accepting terminal records after a purported shard summary."""

        output = "\n".join([
            "SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12",
            "CASE_PASS index=4 cycles=12 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
        ])
        with self.assertRaisesRegex(RuntimeError, "after SHARD_PASS"):
            module._parse_shard_output(
                output,
                expected_start=4,
                expected_count=1,
                cycle_bound=12,
            )

    def test_parser_rejects_malformed_terminal_prefixed_lines_before_valid_output(self):
        """Catches malformed proof records being ignored as simulator chatter."""

        valid = "\n".join([
            "CASE_PASS index=4 cycles=12 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 write_mask=111111",
            "SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12",
        ])
        malformed = (
            "CASE_PASS malformed",
            "CASE_FAIL malformed",
            "SHARD_PASS malformed",
            "SEQUENCE_PASS malformed",
            "ABI_RECEIPT malformed",
            "IMMUTABLE_WRITE malformed",
        )
        for line in malformed:
            with self.subTest(line=line), self.assertRaisesRegex(RuntimeError, "malformed"):
                module._parse_shard_output(
                    f"{line}\n{valid}",
                    expected_start=4,
                    expected_count=1,
                    cycle_bound=12,
                )

        parsed = module._parse_shard_output(
            f"CASE_PASSENGER is unrelated simulator chatter\n{valid}",
            expected_start=4,
            expected_count=1,
            cycle_bound=12,
        )
        self.assertEqual(parsed["completed"], 1)

    def test_parser_rejects_nonlowest_tied_argmax(self):
        """Catches accepting a pass record that silently changes tie policy."""

        output = "\n".join([
            "CASE_PASS index=4 cycles=12 expected_codes=7,7,0,0,0,0 observed_codes=7,7,0,0,0,0 expected_token=1 observed_token=1 write_mask=111111",
            "SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12",
        ])
        with self.assertRaisesRegex(RuntimeError, "lowest-index argmax"):
            module._parse_shard_output(
                output, expected_start=4, expected_count=1, cycle_bound=1_000_000
            )

    def test_parser_turns_immutable_write_fatal_into_a_counterexample(self):
        """Catches losing evidence when the DUT aborts before CASE_FAIL emits."""

        with self.assertRaises(module.ShardOutputError) as raised:
            module._parse_shard_output(
                "IMMUTABLE_WRITE port=0 addr=1",
                expected_start=4,
                expected_count=1,
                cycle_bound=1_000_000,
            )
        self.assertEqual(raised.exception.counterexample, {
            "reason": "IMMUTABLE_WRITE",
            "port": 0,
            "address": 1,
            "record": "IMMUTABLE_WRITE port=0 addr=1",
        })

    def test_preflight_binds_oracle_image_and_manifest_hashes(self):
        """Catches reusing an oracle built against a different frozen image."""

        image_bytes = b"image"
        manifest_bytes = b'{"segments": []}\n'
        shard = {
            "receipt": {
                "artifacts": {
                    "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "image_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                },
            },
        }
        self.assertIsNone(module._validate_oracle_image_provenance(
            shard, image_bytes=image_bytes, manifest_bytes=manifest_bytes
        ))
        with self.assertRaisesRegex(RuntimeError, "image_sha256"):
            module._validate_oracle_image_provenance(
                shard, image_bytes=b"different", manifest_bytes=manifest_bytes
            )

    def test_strict_compile_cache_identity_excludes_oracle_payload_path(self):
        """Catches recompiling a generic fixture merely because a shard changes."""

        first = module._fixture_cache_identity(argparse.Namespace(
            equivalence_shard=Path("first-oracle.json"), static_fixture_case=False,
        ))
        second = module._fixture_cache_identity(argparse.Namespace(
            equivalence_shard=Path("second-oracle.json"), static_fixture_case=False,
        ))
        self.assertEqual(first, second)
        self.assertEqual(first["mode"], "observable-shard-generic")
        self.assertNotIn("oracle", json.dumps(first))

    def test_strict_mode_rejects_missing_or_invalid_exact_constant_receipt(self):
        """Catches accepting a strict proof without a validated Futil-bit receipt."""

        with self.assertRaisesRegex(RuntimeError, "f32 constant"):
            module._validate_f32_constant_bits_receipt(None, strict=True)

        valid = {
            "schema": "rc-calyx-f32-constant-bits-v1",
            "status": "pass",
            "mismatch_count": 0,
            "calyx_mlir_sha256": "a" * 64,
            "futil_sha256": "b" * 64,
            "constants": [{
                "component": "main",
                "symbol": "cst_0",
                "word_u32": 1,
            }],
        }
        self.assertEqual(
            module._validate_f32_constant_bits_receipt(valid, strict=True), valid
        )
        invalid_receipts = {
            "schema": {**valid, "schema": "wrong-schema"},
            "mismatch": {**valid, "mismatch_count": 1},
            "source hash": {**valid, "calyx_mlir_sha256": "not-a-sha256"},
            "Futil hash": {**valid, "futil_sha256": "not-a-sha256"},
        }
        for name, receipt in invalid_receipts.items():
            with self.subTest(receipt=name), self.assertRaisesRegex(RuntimeError, "f32 constant"):
                module._validate_f32_constant_bits_receipt(receipt, strict=True)

    def test_strict_compile_identity_changes_with_constant_receipt(self):
        """Catches reusing a strict Verilator cache from another exact-bit proof."""

        args = argparse.Namespace(
            sv=Path("main.sv"), image=Path("image.bin"), manifest=Path("manifest.json"),
            flat_scf=Path("flat.scf.mlir"), pre_calyx=Path("pre-calyx.mlir"),
            reference=None, equivalence_shard=Path("oracle.json"), simulator="verilator",
            timeout_cycles=1, heartbeat_cycles=0, stop_after_output=False,
            trace_output_writes=False, case_id=None, static_fixture_case=False,
        )
        self.assertNotEqual(
            module._compile_identity(
                args, f32_constant_bits_sha256="a" * 64,
                calyx_memory_bindings_sha256="c" * 64,
            ),
            module._compile_identity(
                args, f32_constant_bits_sha256="b" * 64,
                calyx_memory_bindings_sha256="c" * 64,
            ),
        )

    def test_strict_compile_identity_changes_with_memory_binding_receipt(self):
        """Catches reusing a strict cache after its source-memory binding changes."""

        args = argparse.Namespace(
            sv=Path("main.sv"), image=Path("image.bin"), manifest=Path("manifest.json"),
            flat_scf=Path("flat.scf.mlir"), pre_calyx=Path("pre-calyx.mlir"),
            reference=None, equivalence_shard=Path("oracle.json"), simulator="verilator",
            timeout_cycles=1, heartbeat_cycles=0, stop_after_output=False,
            trace_output_writes=False, case_id=None, static_fixture_case=False,
        )
        self.assertNotEqual(
            module._compile_identity(
                args, f32_constant_bits_sha256="a" * 64,
                calyx_memory_bindings_sha256="b" * 64,
            ),
            module._compile_identity(
                args, f32_constant_bits_sha256="a" * 64,
                calyx_memory_bindings_sha256="c" * 64,
            ),
        )

    def test_strict_cli_requires_both_source_ir_artifacts(self):
        """Catches strict proof mode constructing bindings without exact source IR."""

        required = [
            "--equivalence-shard", "oracle.json",
            "--f32-constant-bits", "f32.json",
            "--f32-calyx-mlir", "normalized.calyx.mlir",
            "--f32-raw-futil", "exported.raw.futil",
            "--sv", "main.sv",
            "--image", "image.bin",
            "--manifest", "manifest.json",
            "--work-dir", "work",
            "--fixture-only",
        ]
        for flag, value in (
            ("--flat-scf", "flat.scf.mlir"),
            ("--pre-calyx", "pre-calyx.mlir"),
        ):
            stderr = io.StringIO()
            with self.subTest(missing=flag), redirect_stderr(stderr), \
                 self.assertRaises(SystemExit) as error:
                other = (
                    ["--pre-calyx", "pre-calyx.mlir"]
                    if flag == "--flat-scf"
                    else ["--flat-scf", "flat.scf.mlir"]
                )
                module.main_from_args([*required, *other])
            self.assertEqual(error.exception.code, 2)
            self.assertIn(f"requires {flag}", stderr.getvalue())

    @staticmethod
    def _write_oracle_shard(
        root, *, image_bytes, manifest_bytes, start=4,
        word="0005050403020100", name="oracle",
    ):
        payload = root / f"shard-{start}-{start + 1}.hex"
        payload.write_text(f"{word}\n", encoding="ascii")
        artifacts = {name: "0" * 64 for name in (
            "exported_program_sha256",
            "export_manifest_sha256",
            "reference_sha256",
            "image_sha256",
            "image_manifest_sha256",
            "generator_sha256",
            "contract_sha256",
        )}
        artifacts["image_sha256"] = hashlib.sha256(image_bytes).hexdigest()
        artifacts["image_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        metadata = {
            "schema_version": 1,
            "status": "complete",
            "receipt": {
                "artifacts": artifacts,
                "python_version": "test-python",
                "pytorch_version": "test-torch",
                "pytorch_num_threads": 1,
            },
            "enumeration": {
                "kind": "base-six-lexical-rightmost-fastest",
                "start": start,
                "stop": start + 1,
                "total_contexts": 1_679_616,
            },
            "record_format": {
                "word_hex_characters": 16,
                "line_bytes": 17,
                "code_lanes": 6,
                "code_bits": 8,
                "token_bits": [48, 55],
                "reserved_bits": [56, 63],
            },
            "payload": {
                "file": payload.name,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                "records": 1,
                "bytes": 17,
            },
            "elapsed_seconds": 0.0,
        }
        metadata_path = root / f"{name}.json"
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        return metadata_path

    def test_sparse_sequence_verifies_components_and_materializes_ordered_runtime_inputs(self):
        """Catches deriving sparse context indexes from one contiguous shard start."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_bytes = b"image"
            manifest_bytes = b'{"segments": []}\n'
            first = self._write_oracle_shard(
                root, image_bytes=image_bytes, manifest_bytes=manifest_bytes,
                start=67141, word="0005050403020100", name="ascending",
            )
            second = self._write_oracle_shard(
                root, image_bytes=image_bytes, manifest_bytes=manifest_bytes,
                start=0, word="0000000000000000", name="zeros",
            )
            runtime = root / "runtime"
            runtime.mkdir()
            sequence = module._verified_equivalence_sequence(
                [first, second], runtime,
                image_bytes=image_bytes, manifest_bytes=manifest_bytes,
            )

            self.assertEqual(sequence["indexes"], [67141, 0])
            self.assertEqual(
                sequence["payload_path"].read_text(encoding="ascii"),
                "0005050403020100\n0000000000000000\n",
            )
            self.assertEqual(
                sequence["context_index_path"].read_text(encoding="ascii"),
                "67141\n0\n",
            )
            self.assertEqual(
                [part["metadata_path"].name for part in sequence["components"]],
                ["ascending.json", "zeros.json"],
            )
            runtime_args = module._strict_runtime_args(
                argparse.Namespace(timeout_cycles=99), sequence
            )
            self.assertIn(f"+context_index_file={sequence['context_index_path']}", runtime_args)
            self.assertIn("+sequence_count=2", runtime_args)
            self.assertFalse(any(arg.startswith("+shard_start=") for arg in runtime_args))

    def test_sparse_sequence_parser_requires_ordered_reset_and_completion_evidence(self):
        """Catches accepting sparse cases without proof each launch was reset and bounded."""

        output = "\n".join([
            "CASE_PASS index=67141 cycles=12 expected_codes=-1,0,1,2,3,4 observed_codes=-1,0,1,2,3,4 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111",
            "CASE_PASS index=0 cycles=13 expected_codes=4,3,2,1,0,-1 observed_codes=4,3,2,1,0,-1 expected_token=0 observed_token=0 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=2 write_mask=111111",
            "SEQUENCE_PASS count=2 completed=2 resets=2 min_cycles=12 max_cycles=13",
        ])
        parsed = module._parse_sequence_output(
            output, expected_indexes=[67141, 0], cycle_bound=20
        )
        self.assertEqual([case["index"] for case in parsed["cases"]], [67141, 0])
        self.assertEqual(parsed["reset_count"], 2)
        self.assertTrue(all(case["reset"]["complete"] for case in parsed["cases"]))
        self.assertTrue(all(case["completion"]["within_bound"] for case in parsed["cases"]))

        missing_reset = output.replace(" reset_complete=1", "", 1)
        with self.assertRaisesRegex(RuntimeError, "CASE_PASS|reset"):
            module._parse_sequence_output(
                missing_reset, expected_indexes=[67141, 0], cycle_bound=20
            )

    def test_parser_rejects_multiple_completions_per_case(self):
        """Catches a proof transcript that reports more than one DUT completion."""

        output = "\n".join([
            "CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=2 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111",
            "SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12",
        ])
        with self.assertRaisesRegex(RuntimeError, "completion"):
            module._parse_shard_output(
                output,
                expected_start=4,
                expected_count=1,
                cycle_bound=1_000_000,
                _require_lifecycle_evidence=True,
            )

    def test_frozen_four_reducer_compares_fresh_and_sequential_lifecycle(self):
        """Catches promoting fresh passes without matching one-process reset evidence."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        summary = module._frozen_four_summary(names, fresh, sequential, proof)
        self.assertEqual(summary["status"], "pass")
        self.assertEqual(summary["sequential_reset"]["reset_count"], len(names))

        sequential["cases"][0]["completion"]["within_bound"] = False
        with self.assertRaisesRegex(RuntimeError, "ascending.*completion"):
            module._frozen_four_summary(names, fresh, sequential, proof)

    def test_frozen_four_reducer_validates_each_receipt_lifecycle_invariant(self):
        """Catches matching fabricated lifecycle records that are not valid passes."""

        def set_done_false(case):
            case["completion"]["done"] = False

        def set_multiple_completions(case):
            case["completion"]["completion_count"] = 2

        def set_unbounded(case):
            case["completion"]["within_bound"] = False

        def set_incomplete_reset(case):
            case["completion"]["reset"]["complete"] = False
            case["reset"]["complete"] = False

        def set_wrong_reset_cycles(case):
            case["completion"]["reset"]["cycles"] = 2
            case["reset"]["cycles"] = 2

        mutations = {
            "done": set_done_false,
            "completion_count": set_multiple_completions,
            "within_bound": set_unbounded,
            "reset.complete": set_incomplete_reset,
            "reset.cycles": set_wrong_reset_cycles,
        }
        for field, mutate in mutations.items():
            with self.subTest(field=field):
                names, proof, fresh, sequential = self._frozen_reducer_receipts()
                # Both receipts agree, so pairwise-only comparison cannot catch it.
                mutate(fresh["ascending"]["cases"][0])
                mutate(sequential["cases"][0])
                with self.assertRaisesRegex(RuntimeError, f"ascending.*{field}"):
                    module._frozen_four_summary(names, fresh, sequential, proof)

    def test_frozen_four_reducer_rejects_shared_bogus_raw_manifest_hash(self):
        """Catches equal fresh/sequential manifest hashes detached from oracle provenance."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        bogus_manifest_sha256 = "e" * 64
        for receipt in [*fresh.values(), sequential]:
            receipt["inputs"]["manifest_sha256"] = bogus_manifest_sha256
        with self.assertRaisesRegex(RuntimeError, "manifest_sha256"):
            module._frozen_four_summary(names, fresh, sequential, proof)

    def test_frozen_four_reducer_binds_manifest_through_calyx_memory_receipt(self):
        """Catches a forged input/oracle manifest hash detached from Calyx bindings."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        bogus_manifest_sha256 = "e" * 64
        for receipt in [*fresh.values(), sequential]:
            receipt["inputs"]["manifest_sha256"] = bogus_manifest_sha256
            oracle = receipt["oracle"]
            components = (
                oracle["components"]
                if oracle.get("kind") == "sparse-sequence"
                else [oracle]
            )
            for component in components:
                component["receipt"]["artifacts"][
                    "image_manifest_sha256"
                ] = bogus_manifest_sha256
        with self.assertRaisesRegex(
            RuntimeError, "calyx_memory_bindings.*manifest_sha256"
        ):
            module._frozen_four_summary(names, fresh, sequential, proof)

    def test_frozen_four_reducer_rejects_cycle_mismatch(self):
        """Catches a sequential run that has equal outputs but a different latency."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        sequential["cases"][0]["cycles"] += 1
        with self.assertRaisesRegex(RuntimeError, "ascending.*cycles"):
            module._frozen_four_summary(names, fresh, sequential, proof)

    def test_frozen_four_reducer_rejects_each_strict_provenance_boundary(self):
        """Catches equal outputs from different strict compilation or fixture evidence."""

        def mutate_binding(receipt):
            bindings = receipt["calyx_memory_bindings"]
            bindings["ports"][1]["global"] = "different_global"
            self._rehash_calyx_memory_bindings(bindings)
            receipt["configuration"]["calyx_memory_bindings_sha256"] = bindings["sha256"]
            receipt["cache_identity"]["calyx_memory_bindings_sha256"] = bindings["sha256"]
            receipt["cache_hashes"]["calyx_memory_bindings_sha256"] = bindings["sha256"]

        def mutate_memory_abi(receipt):
            memory_abi = receipt["memory_abi"]
            memory_abi["ports"][0]["write_enable_sha256"] = "f" * 64
            self._rehash_memory_abi_receipt(memory_abi)
            bindings = receipt["calyx_memory_bindings"]
            bindings["memory_abi_sha256"] = memory_abi["sha256"]
            self._rehash_calyx_memory_bindings(bindings)
            receipt["configuration"]["calyx_memory_bindings_sha256"] = bindings["sha256"]
            receipt["cache_identity"]["calyx_memory_bindings_sha256"] = bindings["sha256"]
            receipt["cache_hashes"]["memory_abi_sha256"] = hashlib.sha256(
                (memory_abi["canonical_json"] + "\n").encode("utf-8")
            ).hexdigest()
            receipt["cache_hashes"]["calyx_memory_bindings_sha256"] = bindings["sha256"]

        def mutate_inputs(receipt):
            receipt["inputs"]["manifest_sha256"] = "e" * 64

        def mutate_sv(receipt):
            receipt["sv"]["normalized_sha256"] = "d" * 64
            receipt["cache_hashes"]["normalized_sv_sha256"] = "d" * 64

        def mutate_fixture(receipt):
            receipt["fixture_sha256"] = "c" * 64
            receipt["cache_hashes"]["fixture_sha256"] = "c" * 64

        def mutate_configuration(receipt):
            receipt["configuration"]["verilate_jobs"] = 5

        def mutate_cache_identity(receipt):
            receipt["cache_identity"]["fixture"]["fixture_schema"] = "wrong-schema"

        def mutate_cache_hashes(receipt):
            receipt["cache_hashes"]["binary_sha256"] = "b" * 64

        mutations = {
            "calyx_memory_bindings": mutate_binding,
            "memory_abi": mutate_memory_abi,
            "inputs": mutate_inputs,
            "sv": mutate_sv,
            "fixture_sha256": mutate_fixture,
            "configuration": mutate_configuration,
            "cache_identity": mutate_cache_identity,
            "cache_hashes": mutate_cache_hashes,
        }
        for boundary, mutate in mutations.items():
            with self.subTest(boundary=boundary):
                names, proof, fresh, sequential = self._frozen_reducer_receipts()
                mutate(sequential)
                with self.assertRaisesRegex(RuntimeError, boundary):
                    module._frozen_four_summary(names, fresh, sequential, proof)

    def test_frozen_four_reducer_persists_failure_evidence(self):
        """Catches a reducer mismatch that leaves no durable counterexample in $out."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        sequential["cases"][0]["cycles"] += 1
        writer = getattr(module, "_write_frozen_four_summary", None)
        self.assertIsNotNone(writer, "frozen reducer must persist its own failure receipt")
        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.json"
            with self.assertRaisesRegex(RuntimeError, "ascending.*cycles"):
                writer(summary_path, names, fresh, sequential, proof)
            counterexample = json.loads(
                summary_path.with_name("counterexample.json").read_text(encoding="utf-8")
            )
            self.assertEqual(counterexample["stage"], "frozen_reducer")
            self.assertIn("cycles", counterexample["error"])
            self.assertEqual(counterexample["proof"], {"f32_constant_bits_sha256": proof})
            self.assertEqual(counterexample["fresh_receipts"], fresh)
            self.assertEqual(counterexample["sequential_reset"], sequential)

    def test_frozen_four_reducer_cli_persists_receipt_load_failures(self):
        """Catches argparse exit discarding missing or malformed reducer evidence."""

        for name, payload, expected_error in (
            ("missing", None, "cannot load frozen reducer fresh receipt"),
            ("malformed", "{not-json", "cannot load frozen reducer fresh receipt"),
        ):
            with self.subTest(receipt=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                proof_path = root / "f32-constant-bits.json"
                proof_path.write_bytes(b"frozen-reducer-proof")
                fresh_path = root / "ascending.json"
                if payload is not None:
                    fresh_path.write_text(payload, encoding="utf-8")
                sequential_path = root / "sequential-reset.json"
                summary_path = root / "summary.json"
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    module.main_from_args([
                        "--reduce-frozen-four",
                        "--f32-constant-bits", str(proof_path),
                        "--fresh-receipt", f"ascending={fresh_path}",
                        "--sequential-receipt", str(sequential_path),
                        "--result-json", str(summary_path),
                    ])
                self.assertEqual(raised.exception.code, 2)
                counterexample = json.loads(
                    summary_path.with_name("counterexample.json").read_text(encoding="utf-8")
                )
                self.assertEqual(counterexample["stage"], "frozen_reducer")
                self.assertIn(expected_error, counterexample["error"])
                self.assertEqual(
                    counterexample["proof"],
                    {"f32_constant_bits_sha256": module._sha256_path(proof_path)},
                )
                self.assertIn("fresh_receipts", counterexample)
                self.assertIn("sequential_reset", counterexample)
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                self.assertEqual(summary["status"], "fail")

    def test_frozen_four_reducer_cli_persists_malformed_receipt_structure(self):
        """Catches valid JSON whose nested receipt structure bypasses failure evidence."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        sequential["f32_constant_bits"] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof_path = root / "f32-constant-bits.json"
            proof_path.write_bytes(b"frozen-reducer-proof")
            self.assertEqual(module._sha256_path(proof_path), proof)
            fresh_flags = []
            for name in names:
                path = root / f"{name}.json"
                path.write_text(json.dumps(fresh[name]), encoding="utf-8")
                fresh_flags.extend(["--fresh-receipt", f"{name}={path}"])
            sequential_path = root / "sequential-reset.json"
            sequential_path.write_text(json.dumps(sequential), encoding="utf-8")
            summary_path = root / "summary.json"
            with (
                redirect_stdout(io.StringIO()),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                module.main_from_args([
                    "--reduce-frozen-four",
                    "--f32-constant-bits", str(proof_path),
                    *fresh_flags,
                    "--sequential-receipt", str(sequential_path),
                    "--result-json", str(summary_path),
                ])
            self.assertEqual(raised.exception.code, 2)
            counterexample = json.loads(
                summary_path.with_name("counterexample.json").read_text(encoding="utf-8")
            )
            self.assertEqual(counterexample["stage"], "frozen_reducer")
            self.assertIn("f32_constant_bits", counterexample["error"])
            self.assertEqual(counterexample["sequential_reset"], sequential)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "fail")

    def test_calyx_memory_bindings_hash_exact_manifest_bytes(self):
        """Catches binding a canonicalized manifest instead of the frozen input bytes."""

        image, manifest = self._image_and_manifest()
        flat_scf, pre_calyx = self._source_ir(image, manifest)
        manifest_bytes = (
            json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        )
        receipt = module._build_calyx_memory_bindings(
            flat_scf=flat_scf,
            pre_calyx=pre_calyx,
            image=image,
            manifest=manifest,
            manifest_bytes=manifest_bytes,
            abi=module._memory_abi(self._sv()),
        )
        self.assertEqual(
            receipt["image_manifest_sha256"],
            hashlib.sha256(manifest_bytes).hexdigest(),
        )

    def test_frozen_four_reducer_cli_writes_a_summary(self):
        """Catches Nix bypassing the runner's durable frozen-reducer path."""

        names, proof, fresh, sequential = self._frozen_reducer_receipts()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof_path = root / "f32-constant-bits.json"
            proof_path.write_bytes(b"frozen-reducer-proof")
            self.assertEqual(module._sha256_path(proof_path), proof)
            fresh_flags = []
            for name in names:
                path = root / f"{name}.json"
                path.write_text(json.dumps(fresh[name]), encoding="utf-8")
                fresh_flags.extend(["--fresh-receipt", f"{name}={path}"])
            sequential_path = root / "sequential-reset.json"
            sequential_path.write_text(json.dumps(sequential), encoding="utf-8")
            summary_path = root / "summary.json"
            with redirect_stdout(io.StringIO()):
                module.main_from_args([
                    "--reduce-frozen-four",
                    "--f32-constant-bits", str(proof_path),
                    *fresh_flags,
                    "--sequential-receipt", str(sequential_path),
                    "--result-json", str(summary_path),
                ])
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["schema"], module.FROZEN_FOUR_SCHEMA)

    def test_nix_frozen_four_wires_one_ordered_sequence_process(self):
        """Catches a derivation that emits only four independent simulator runs."""

        source = (ROOT / "diagnostics/rc-observable-equivalence.nix").read_text()
        self.assertEqual(source.count("--equivalence-sequence"), 1)
        self.assertIn('--result-json "$out/sequential-reset.json"', source)
        self.assertIn("--reduce-frozen-four", source)
        self.assertNotIn("_frozen_four_summary", source)
        self.assertNotIn("importlib.util.spec_from_file_location", source)
        self.assertIn("constant-proof/normalized.calyx.mlir", source)
        self.assertIn("constant-proof/exported.raw.futil", source)
        self.assertNotIn(
            'mv "$out/shard-$index-$((index + 1)).hex" "$out/$case_name.hex"',
            source,
        )

    def test_f32_receipt_rehashes_exact_raw_verifier_inputs(self):
        """Catches accepting self-attested source/Futil hashes with no artifact check."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calyx_mlir = root / "normalized.calyx.mlir"
            raw_futil = root / "exported.raw.futil"
            calyx_mlir.write_bytes(b"component source\n")
            raw_futil.write_bytes(b"component main() -> () { cells {} }\n")
            receipt_path = root / "f32-constant-bits.json"
            receipt_path.write_text(json.dumps({
                "schema": "rc-calyx-f32-constant-bits-v1",
                "status": "pass",
                "mismatch_count": 0,
                "calyx_mlir_sha256": hashlib.sha256(calyx_mlir.read_bytes()).hexdigest(),
                "futil_sha256": hashlib.sha256(raw_futil.read_bytes()).hexdigest(),
                "constants": [{"component": "main", "symbol": "cst_0", "word_u32": 1}],
            }, sort_keys=True), encoding="utf-8")

            loaded = module._load_f32_constant_bits_receipt(
                receipt_path, strict=True,
                calyx_mlir_path=calyx_mlir, raw_futil_path=raw_futil,
            )
            self.assertEqual(loaded["calyx_mlir"]["sha256"], hashlib.sha256(calyx_mlir.read_bytes()).hexdigest())
            raw_futil.write_bytes(raw_futil.read_bytes() + b"// tampered\n")
            with self.assertRaisesRegex(RuntimeError, "Futil.*does not match"):
                module._load_f32_constant_bits_receipt(
                    receipt_path, strict=True,
                    calyx_mlir_path=calyx_mlir, raw_futil_path=raw_futil,
                )

    def _strict_run_paths(self, root):
        image, manifest = self._image_and_manifest()
        inputs = root / "inputs"
        inputs.mkdir()
        sv_path = inputs / "main.sv"
        image_path = inputs / "image.bin"
        manifest_path = inputs / "manifest.json"
        sv_path.write_text(self._sv(), encoding="utf-8")
        image_path.write_bytes(image)
        manifest_bytes = json.dumps(manifest, sort_keys=True).encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        flat_scf, pre_calyx = self._source_ir(image, manifest)
        (inputs / "flat.scf.mlir").write_bytes(flat_scf)
        (inputs / "pre-calyx.mlir").write_bytes(pre_calyx)
        oracle_path = self._write_oracle_shard(
            root, image_bytes=image, manifest_bytes=manifest_bytes
        )
        proof_dir = root / "constant-proof"
        proof_dir.mkdir()
        (proof_dir / "normalized.calyx.mlir").write_bytes(b"component source\n")
        (proof_dir / "exported.raw.futil").write_bytes(b"component main\n")
        (root / "f32-constant-bits.json").write_text(json.dumps({
            "schema": "rc-calyx-f32-constant-bits-v1",
            "status": "pass",
            "mismatch_count": 0,
            "calyx_mlir_sha256": module._sha256_path(proof_dir / "normalized.calyx.mlir"),
            "futil_sha256": module._sha256_path(proof_dir / "exported.raw.futil"),
            "constants": [{
                "component": "main",
                "symbol": "cst_0",
                "word_u32": 1,
            }],
        }, sort_keys=True), encoding="utf-8")
        return sv_path, image_path, manifest_path, oracle_path

    @staticmethod
    def _strict_source_flags(root):
        return [
            "--flat-scf", str(root / "inputs/flat.scf.mlir"),
            "--pre-calyx", str(root / "inputs/pre-calyx.mlir"),
        ]

    def _run_strict_run_only(
        self,
        root,
        oracle_path,
        sv_path,
        image_path,
        manifest_path,
        *,
        timeout_cycles=1_000_000,
    ):
        module.main_from_args([
            "--equivalence-shard", str(oracle_path),
            "--f32-constant-bits", str(root / "f32-constant-bits.json"),
            "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
            "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
            *self._strict_source_flags(root),
            "--sv", str(sv_path),
            "--image", str(image_path),
            "--manifest", str(manifest_path),
            "--work-dir", str(root),
            "--timeout-cycles", str(timeout_cycles),
            "--run-only", "--verify-cache",
        ])

    def _write_strict_cache(self, root, *, sv_path, image_path, manifest_path, oracle_path, binary_text):
        binary = root / "obj_dir" / "Vtb"
        binary.parent.mkdir()
        binary.write_text(binary_text, encoding="utf-8")
        binary.chmod(0o755)
        raw_text = sv_path.read_text(encoding="utf-8")
        memory_abi = module._memory_abi(raw_text)
        normalized_text = module._normalized_sv_text(raw_text)
        normalized_sv = root / "main.sv"
        normalized_sv.write_text(normalized_text, encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        calyx_memory_bindings = module._build_calyx_memory_bindings(
            flat_scf=(root / "inputs/flat.scf.mlir").read_bytes(),
            pre_calyx=(root / "inputs/pre-calyx.mlir").read_bytes(),
            image=image_path.read_bytes(),
            manifest=manifest,
            abi=memory_abi,
            manifest_bytes=manifest_path.read_bytes(),
        )
        (root / "external-memory-bindings.json").write_text(
            calyx_memory_bindings["canonical_json"], encoding="utf-8"
        )
        fixture = module._strict_fixture(
            raw_text,
            image_path.read_bytes(),
            manifest,
            root,
            cycle_bound=1_000_000,
            calyx_memory_bindings=calyx_memory_bindings,
            memory_abi=memory_abi,
        )
        args = argparse.Namespace(
            sv=sv_path,
            image=image_path,
            manifest=manifest_path,
            flat_scf=root / "inputs/flat.scf.mlir",
            pre_calyx=root / "inputs/pre-calyx.mlir",
            reference=None,
            equivalence_shard=oracle_path,
            simulator="verilator",
            timeout_cycles=1_000_000,
            heartbeat_cycles=0,
            stop_after_output=False,
            trace_output_writes=False,
            case_id=None,
            static_fixture_case=False,
            f32_constant_bits=root / "f32-constant-bits.json",
            f32_constant_bits_sha256=module._sha256_path(root / "f32-constant-bits.json"),
            f32_calyx_mlir=root / "constant-proof/normalized.calyx.mlir",
            f32_raw_futil=root / "constant-proof/exported.raw.futil",
        )
        raw = raw_text.encode("utf-8")
        artifacts = {
            "raw_sv_sha256": hashlib.sha256(raw).hexdigest(),
            "normalized_sv_sha256": hashlib.sha256(normalized_sv.read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "binary_bytes": binary.stat().st_size,
            "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "memory_abi_sha256": module._sha256_path(root / "memory-abi.json"),
            "runtime_memory_sha256": module._strict_runtime_memory_sha256(root),
            "calyx_memory_bindings_sha256": calyx_memory_bindings["sha256"],
        }
        module._write_cache_metadata(
            root,
            module._compiled_cache_metadata(
                args,
                {
                    "verilate_jobs": 4,
                    "build_jobs": 4,
                    "verilator_threads": 1,
                    "verilator_output_split": 100,
                    "verilator_output_split_cfuncs": 50,
                    "fixture_schema": module.STRICT_FIXTURE_SCHEMA,
                    "f32_constant_bits_sha256": args.f32_constant_bits_sha256,
                    "calyx_memory_bindings_sha256": calyx_memory_bindings["sha256"],
                },
                {},
                artifacts,
                binary,
                root,
                module._memory_abi_receipt(memory_abi),
                calyx_memory_bindings,
            ),
        )

    def test_run_only_writes_a_durable_strict_receipt_from_terminal_records(self):
        """Catches a run-only proof that omits its receipt or oracle binding."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            with redirect_stdout(io.StringIO()):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--run-only", "--verify-cache",
                ])
            receipt = json.loads((root / "equivalence-receipt.json").read_text())
            bindings = json.loads((root / "compile-metadata.json").read_text())[
                "calyx_memory_bindings"
            ]
            self.assertEqual(receipt["status"], "pass")
            self.assertEqual(receipt["range"], {"start": 4, "stop": 5, "count": 1})
            self.assertEqual(receipt["completed"], 1)
            self.assertEqual(
                module._strict_frozen_receipt_identity(
                    receipt,
                    proof_sha256=module._sha256_path(root / "f32-constant-bits.json"),
                    label="run-only receipt",
                )["cache_identity"]["fixture"]["mode"],
                "observable-shard-generic",
            )
            self.assertEqual(
                receipt["f32_constant_bits"]["sha256"],
                module._sha256_path(root / "f32-constant-bits.json"),
            )
            self.assertEqual(
                receipt["oracle"]["payload_sha256"],
                hashlib.sha256((root / "shard-4-5.hex").read_bytes()).hexdigest(),
            )
            binding_sha256 = bindings["sha256"]
            external_binding_bytes = (
                root / "external-memory-bindings.json"
            ).read_bytes()
            self.assertEqual(
                hashlib.sha256(external_binding_bytes).hexdigest(),
                binding_sha256,
            )
            self.assertEqual(
                external_binding_bytes, bindings["canonical_json"].encode("utf-8")
            )
            self.assertEqual(
                json.loads(external_binding_bytes),
                {
                    key: value
                    for key, value in bindings.items()
                    if key not in ("canonical_json", "sha256")
                },
            )
            self.assertIn(binding_sha256, (root / "tb.sv").read_text(encoding="utf-8"))
            self.assertEqual(
                receipt["calyx_memory_bindings"], bindings
            )
            identity_row = next(
                row for row in bindings["ports"]
                if row["port"] != 27 and row["shape_transform"] == "identity"
            )
            self.assertEqual(identity_row["source_shape"], identity_row["lowered_shape"])
            self.assertEqual(identity_row["shape_transform"], "identity")
            for field in ("source_shape", "lowered_shape", "shape_transform"):
                self.assertIn(field, identity_row)
            expected_inputs = {
                "flat_scf_sha256": module._sha256_path(root / "inputs/flat.scf.mlir"),
                "pre_calyx_sha256": module._sha256_path(root / "inputs/pre-calyx.mlir"),
                "manifest_sha256": module._sha256_path(manifest_path),
            }
            metadata = json.loads((root / "compile-metadata.json").read_text())
            for name, digest in expected_inputs.items():
                self.assertEqual(metadata["inputs"][name], digest)
                self.assertEqual(receipt["inputs"][name], digest)

    def test_run_only_rejects_rehashed_shape_provenance_receipt(self):
        """Catches accepting a valid rehashed binding whose source shape changed."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            metadata_path = root / "compile-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            changed = metadata["calyx_memory_bindings"]
            identity_row = next(
                row for row in changed["ports"]
                if row["port"] != 27 and row["shape_transform"] == "identity"
            )
            self.assertEqual(identity_row["source_shape"], [2])
            identity_row["source_shape"] = [1, 2]
            identity_row["shape_transform"] = "contiguous-flatten"
            payload = {
                key: value
                for key, value in changed.items()
                if key not in ("canonical_json", "sha256")
            }
            changed["canonical_json"] = json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            )
            changed["sha256"] = hashlib.sha256(
                changed["canonical_json"].encode("utf-8")
            ).hexdigest()
            self.assertEqual(
                module._validate_calyx_memory_bindings_receipt(changed), changed
            )
            module._write_cache_metadata(root, metadata)

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--run-only", "--verify-cache",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "cached Calyx memory binding receipt does not match exact source inputs",
                counterexample["error"],
            )

    def test_run_only_rejects_metadata_rebound_external_binding_artifact(self):
        """Catches accepting arbitrary binding bytes relabeled by cache metadata."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            metadata_path = root / "compile-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            bindings = metadata["calyx_memory_bindings"]
            self.assertEqual(
                metadata["compile_identity"]["calyx_memory_bindings_sha256"],
                bindings["sha256"],
            )
            self.assertEqual(
                metadata["compile"]["configuration"]["calyx_memory_bindings_sha256"],
                bindings["sha256"],
            )
            arbitrary_bytes = b"not a Calyx memory binding receipt\n"
            (root / "external-memory-bindings.json").write_bytes(arbitrary_bytes)
            metadata["compile"]["artifacts"]["calyx_memory_bindings_sha256"] = (
                hashlib.sha256(arbitrary_bytes).hexdigest()
            )
            module._write_cache_metadata(root, metadata)

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                self._run_strict_run_only(
                    root, oracle_path, sv_path, image_path, manifest_path
                )
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "cached strict artifact binding SHA-256 does not match rebuilt receipt",
                counterexample["error"],
            )

    def test_run_only_rejects_configuration_binding_sha_mismatch(self):
        """Catches configuration provenance contradicting a rebuilt binding receipt."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            metadata_path = root / "compile-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["compile"]["configuration"]["calyx_memory_bindings_sha256"] = (
                "0" * 64
            )
            module._write_cache_metadata(root, metadata)

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                self._run_strict_run_only(
                    root, oracle_path, sv_path, image_path, manifest_path
                )
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "cached strict configuration binding SHA-256 does not match rebuilt receipt",
                counterexample["error"],
            )

    def test_run_only_rejects_configuration_f32_sha_mismatch(self):
        """Catches configuration provenance contradicting the exact f32 proof."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            metadata_path = root / "compile-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["compile"]["configuration"]["f32_constant_bits_sha256"] = (
                "0" * 64
            )
            module._write_cache_metadata(root, metadata)

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                self._run_strict_run_only(
                    root, oracle_path, sv_path, image_path, manifest_path
                )
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "cached strict configuration f32 constant-bits SHA-256 does not match exact proof",
                counterexample["error"],
            )

    def test_run_only_rejects_rehashed_derivable_fixture_inputs(self):
        """Catches rebasing mutable cache hashes after fixture input corruption."""

        mutations = {
            "normalized main.sv": "strict cached normalized main.sv does not equal",
            "tb.sv binding marker": "strict cached tb.sv fixture does not equal",
            "memory ABI receipt": "strict cached memory ABI receipt does not equal",
            "image-backed memory": "strict cached runtime-memory SHA-256 does not match",
            "receipt-backed f32 memory": "strict cached runtime-memory SHA-256 does not match",
        }
        for name, expected_error in mutations.items():
            with self.subTest(artifact=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
                self._write_strict_cache(
                    root,
                    sv_path=sv_path,
                    image_path=image_path,
                    manifest_path=manifest_path,
                    oracle_path=oracle_path,
                    binary_text=(
                        "#!/bin/sh\n"
                        "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                        "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                    ),
                )
                metadata_path = root / "compile-metadata.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                artifacts = metadata["compile"]["artifacts"]

                if name == "normalized main.sv":
                    path = root / "main.sv"
                    path.write_bytes(path.read_bytes() + b"// rebased mutation\n")
                    artifacts["normalized_sv_sha256"] = module._sha256_path(path)
                elif name == "tb.sv binding marker":
                    path = root / "tb.sv"
                    source = path.read_text(encoding="utf-8")
                    binding_sha256 = metadata["calyx_memory_bindings"]["sha256"]
                    self.assertIn(binding_sha256, source)
                    path.write_text(
                        source.replace(binding_sha256, "0" * 64, 1), encoding="utf-8"
                    )
                    artifacts["fixture_sha256"] = module._sha256_path(path)
                elif name == "memory ABI receipt":
                    path = root / "memory-abi.json"
                    path.write_bytes(path.read_bytes() + b"rehashed metadata mutation\n")
                    artifacts["memory_abi_sha256"] = module._sha256_path(path)
                elif name == "image-backed memory":
                    path = root / "mem0.hex"
                    path.write_bytes(b"ffffffff\n" + path.read_bytes().split(b"\n", 1)[1])
                    artifacts["runtime_memory_sha256"] = module._strict_runtime_memory_sha256(root)
                elif name == "receipt-backed f32 memory":
                    path = root / "mem27.hex"
                    path.write_bytes(b"3f800000\n" + path.read_bytes().split(b"\n", 1)[1])
                    artifacts["runtime_memory_sha256"] = module._strict_runtime_memory_sha256(root)
                else:
                    self.fail(f"unhandled mutation: {name}")
                module._write_cache_metadata(root, metadata)

                with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                    RuntimeError, "cache_validation"
                ):
                    self._run_strict_run_only(
                        root, oracle_path, sv_path, image_path, manifest_path
                    )
                counterexample = json.loads((root / "counterexample.json").read_text())
                self.assertEqual(counterexample["stage"], "cache_validation")
                self.assertIn(expected_error, counterexample["error"])

    def test_run_only_rejects_rebased_cached_memory_abi_receipt(self):
        """Catches a valid rehashed ABI receipt that contradicts current SV."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            metadata_path = root / "compile-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            changed = metadata["memory_abi"]
            self.assertNotEqual(changed["ports"][0]["write_enable_sha256"], "0" * 64)
            changed["ports"][0]["write_enable_sha256"] = "0" * 64
            changed["canonical_json"] = json.dumps(
                changed["ports"], sort_keys=True, separators=(",", ":")
            )
            changed["sha256"] = hashlib.sha256(
                changed["canonical_json"].encode("utf-8")
            ).hexdigest()
            self.assertEqual(module._validate_memory_abi_receipt(changed), changed)
            abi_path = root / "memory-abi.json"
            abi_path.write_text(changed["canonical_json"] + "\n", encoding="utf-8")
            metadata["compile"]["artifacts"]["memory_abi_sha256"] = (
                module._sha256_path(abi_path)
            )
            module._write_cache_metadata(root, metadata)

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                self._run_strict_run_only(
                    root, oracle_path, sv_path, image_path, manifest_path
                )
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "cached memory ABI receipt does not match exact current SV inputs",
                counterexample["error"],
            )

    def test_run_only_rejects_fixture_default_timeout_mismatch(self):
        """Catches validating a tb.sv built with another timeout default."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                self._run_strict_run_only(
                    root,
                    oracle_path,
                    sv_path,
                    image_path,
                    manifest_path,
                    timeout_cycles=999_999,
                )
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "cached strict fixture timeout default does not match --timeout-cycles",
                counterexample["error"],
            )

    def test_run_only_rejects_raw_sv_artifact_sha_mismatch(self):
        """Catches a cached raw-SV hash that contradicts the input snapshot."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )
            metadata_path = root / "compile-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["compile"]["artifacts"]["raw_sv_sha256"] = "0" * 64
            module._write_cache_metadata(root, metadata)

            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                self._run_strict_run_only(
                    root, oracle_path, sv_path, image_path, manifest_path
                )
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn(
                "strict cached raw SV SHA-256 does not match exact current input snapshot",
                counterexample["error"],
            )

    def test_run_only_launches_a_private_snapshot_after_cache_validation(self):
        """Catches a cache replacement between validation and the simulator exec."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            shard = module._verified_equivalence_shard(oracle_path)
            expected_oracle = root / "expected-oracle.hex"
            expected_oracle.write_bytes(shard["payload_path"].read_bytes())
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text=(
                    "#!/bin/sh\n"
                    "oracle_path=''\n"
                    "for argument in \"$@\"; do\n"
                    "  case \"$argument\" in\n"
                    "    +oracle_file=*) oracle_path=${argument#+oracle_file=} ;;\n"
                    "  esac\n"
                    "done\n"
                    "[ -n \"$oracle_path\" ] || exit 82\n"
                    f"cmp -s \"$oracle_path\" \"{expected_oracle}\" || exit 83\n"
                    "IFS= read -r first_word < mem27.hex\n"
                    "[ \"$first_word\" = \"00000000\" ] || exit 84\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                ),
            )

            original_run = module.subprocess.run
            launches = []
            mutated = False

            def replace_cache_at_launch(command, *args, **kwargs):
                nonlocal mutated
                if (
                    not mutated
                    and isinstance(command, (list, tuple))
                    and command
                    and Path(str(command[0])).name == "Vtb"
                ):
                    mutated = True
                    (root / "mem27.hex").write_bytes(
                        b"3f800000\n" + (root / "mem27.hex").read_bytes().split(b"\n", 1)[1]
                    )
                    shard["payload_path"].write_bytes(b"deadbeef\n")
                    launches.append((Path(str(command[0])), Path(kwargs["cwd"])))
                return original_run(command, *args, **kwargs)

            module.subprocess.run = replace_cache_at_launch
            try:
                with redirect_stdout(io.StringIO()):
                    self._run_strict_run_only(
                        root, oracle_path, sv_path, image_path, manifest_path
                    )
            finally:
                module.subprocess.run = original_run

            self.assertTrue(mutated)
            self.assertEqual(len(launches), 1)
            launched_binary, launch_cwd = launches[0]
            self.assertNotEqual(launch_cwd, root)
            self.assertNotEqual(launched_binary, root / "obj_dir" / "Vtb")
            self.assertEqual(launched_binary.parent, launch_cwd)
            receipt = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(receipt["status"], "pass")

    def test_run_only_sparse_sequence_snapshots_oracle_and_context_outside_cache(self):
        """Catches a sequence run that creates or consumes its inputs under cache."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, first_oracle = self._strict_run_paths(root)
            second_oracle = self._write_oracle_shard(
                root,
                image_bytes=image_path.read_bytes(),
                manifest_bytes=manifest_path.read_bytes(),
                start=0,
                word="0000000000000000",
                name="second-sequence-oracle",
            )
            first = module._verified_equivalence_shard(first_oracle)
            second = module._verified_equivalence_shard(second_oracle)
            expected_payload = root / "expected-sequence.hex"
            expected_payload.write_bytes(
                first["payload_path"].read_bytes() + second["payload_path"].read_bytes()
            )
            expected_indexes = root / "expected-sequence.indexes"
            expected_indexes.write_bytes(b"4\n0\n")
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=first_oracle,
                binary_text=(
                    "#!/bin/sh\n"
                    "oracle_path=''\n"
                    "context_path=''\n"
                    "for argument in \"$@\"; do\n"
                    "  case \"$argument\" in\n"
                    "    +oracle_file=*) oracle_path=${argument#+oracle_file=} ;;\n"
                    "    +context_index_file=*) context_path=${argument#+context_index_file=} ;;\n"
                    "  esac\n"
                    "done\n"
                    "[ -n \"$oracle_path\" ] || exit 82\n"
                    "[ -n \"$context_path\" ] || exit 83\n"
                    f"cmp -s \"$oracle_path\" \"{expected_payload}\" || exit 84\n"
                    f"cmp -s \"$context_path\" \"{expected_indexes}\" || exit 85\n"
                    "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                    "echo 'CASE_PASS index=0 cycles=13 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=2 write_mask=111111'\n"
                    "echo 'SEQUENCE_PASS count=2 completed=2 resets=2 min_cycles=12 max_cycles=13'\n"
                ),
            )

            original_run = module.subprocess.run
            launches = []

            def replace_oracle_components_at_launch(command, *args, **kwargs):
                if (
                    isinstance(command, (list, tuple))
                    and command
                    and Path(str(command[0])).name == "Vtb"
                ):
                    first["payload_path"].write_bytes(b"deadbeef\n")
                    second["payload_path"].write_bytes(b"cafebabe\n")
                    launches.append((Path(str(command[0])), Path(kwargs["cwd"])))
                return original_run(command, *args, **kwargs)

            module.subprocess.run = replace_oracle_components_at_launch
            try:
                with redirect_stdout(io.StringIO()):
                    module.main_from_args([
                        "--equivalence-sequence", str(first_oracle), str(second_oracle),
                        "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                        "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                        "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                        *self._strict_source_flags(root),
                        "--sv", str(sv_path),
                        "--image", str(image_path),
                        "--manifest", str(manifest_path),
                        "--work-dir", str(root),
                        "--run-only", "--verify-cache",
                    ])
            finally:
                module.subprocess.run = original_run

            self.assertEqual(list(root.glob("sequence-*.hex")), [])
            self.assertEqual(list(root.glob("sequence-*.indexes")), [])
            self.assertEqual(len(launches), 1)
            launched_binary, launch_cwd = launches[0]
            self.assertNotEqual(launch_cwd, root)
            self.assertEqual(launched_binary.parent, launch_cwd)
            receipt = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(receipt["status"], "pass")
            self.assertEqual(
                [component["payload_path"] for component in receipt["oracle"]["components"]],
                [str(first["payload_path"]), str(second["payload_path"])],
            )
            self.assertNotIn(str(launch_cwd), json.dumps(receipt["oracle"]))

    def test_run_only_writes_counterexample_before_reporting_immutable_write(self):
        """Catches a fatal immutable write that returns without durable evidence."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text="#!/bin/sh\necho 'IMMUTABLE_WRITE port=0 addr=1'\nexit 1\n",
            )
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "counterexample"):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--run-only", "--verify-cache",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "simulation_result")
            self.assertEqual(
                counterexample["f32_constant_bits"]["sha256"],
                module._sha256_path(root / "f32-constant-bits.json"),
            )
            self.assertEqual(
                module._validate_calyx_memory_bindings_receipt(
                    counterexample["calyx_memory_bindings"]
                ),
                counterexample["calyx_memory_bindings"],
            )
            self.assertEqual(
                module._validate_memory_abi_receipt(counterexample["memory_abi"]),
                counterexample["memory_abi"],
            )
            self.assertEqual(
                module._strict_cache_hashes(counterexample["cache_hashes"]),
                counterexample["cache_hashes"],
            )
            self.assertEqual(
                counterexample["cache_identity"]["calyx_memory_bindings_sha256"],
                counterexample["calyx_memory_bindings"]["sha256"],
            )
            self.assertEqual(
                counterexample["cache_identity"]["f32_constant_bits_sha256"],
                counterexample["f32_constant_bits"]["sha256"],
            )
            self.assertEqual(counterexample["case"]["reason"], "IMMUTABLE_WRITE")
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")

    def test_codegen_failure_writes_strict_evidence_before_reraising(self):
        """Catches a Verilator codegen error escaping before a receipt exists."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            fake_verilator = root / "failing-verilator"
            fake_verilator.write_text(
                "#!/bin/sh\n"
                "echo 'controlled Verilator codegen failure' >&2\n"
                "exit 23\n",
                encoding="utf-8",
            )
            fake_verilator.chmod(0o755)
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "verilator_codegen"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--verilator", str(fake_verilator),
                    "--compile-only",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["status"], "fail")
            self.assertEqual(counterexample["stage"], "verilator_codegen")
            self.assertEqual(counterexample["returncode"], 23)
            self.assertIn("controlled Verilator codegen failure", counterexample["output"])
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")
            self.assertEqual(failed["failure"]["stage"], "verilator_codegen")

    def test_cpp_build_failure_writes_strict_evidence_before_reraising(self):
        """Catches a generated-C++ build error escaping before a receipt exists."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            fake_verilator = root / "successful-verilator"
            fake_verilator.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"--version\" ]; then echo 'fake Verilator'; exit 0; fi\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = \"-Mdir\" ]; then\n"
                "    mkdir -p \"$2\"\n"
                "    : > \"$2/Vtb.cpp\"\n"
                "    : > \"$2/Vtb.h\"\n"
                "    exit 0\n"
                "  fi\n"
                "  shift\n"
                "done\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_verilator.chmod(0o755)
            fake_make = root / "failing-make"
            fake_make.write_text(
                "#!/bin/sh\n"
                "echo 'controlled C++ build failure' >&2\n"
                "exit 24\n",
                encoding="utf-8",
            )
            fake_make.chmod(0o755)
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cpp_build"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--verilator", str(fake_verilator),
                    "--make", str(fake_make),
                    "--compile-only",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["status"], "fail")
            self.assertEqual(counterexample["stage"], "cpp_build")
            self.assertEqual(counterexample["returncode"], 24)
            self.assertIn("controlled C++ build failure", counterexample["output"])
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")
            self.assertEqual(failed["failure"]["stage"], "cpp_build")

    def test_fixture_setup_failure_writes_strict_evidence_before_reraising(self):
        """Catches malformed strict SV escaping binding preflight without evidence."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            sv_path.write_text("module unrelated; endmodule\n", encoding="utf-8")
            timing_path = root / "setup-timing.json"
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "preflight"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--timing-json", str(timing_path),
                    "--fixture-only",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["status"], "fail")
            self.assertEqual(counterexample["stage"], "preflight")
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")
            self.assertEqual(failed["failure"]["stage"], "preflight")
            timed = json.loads(timing_path.read_text())
            self.assertEqual(timed["failure"]["stage"], "preflight")

    def test_run_only_cache_load_failure_writes_strict_evidence_before_reraising(self):
        """Catches a missing verified cache escaping strict run-only without evidence."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            timing_path = root / "cache-timing.json"
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--timing-json", str(timing_path),
                    "--run-only", "--verify-cache",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["status"], "fail")
            self.assertEqual(counterexample["stage"], "cache_validation")
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")
            self.assertEqual(failed["failure"]["stage"], "cache_validation")
            timed = json.loads(timing_path.read_text())
            self.assertEqual(timed["failure"]["stage"], "cache_validation")

    def test_run_only_missing_binary_writes_strict_evidence_before_reraising(self):
        """Catches a verified cache whose declared binary disappeared."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text="#!/bin/sh\nexit 0\n",
            )
            (root / "obj_dir" / "Vtb").unlink()
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "cache_validation"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--run-only", "--verify-cache",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "cache_validation")
            self.assertIn("cached binary is missing", counterexample["error"])
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")
            self.assertEqual(failed["failure"]["stage"], "cache_validation")

    def test_run_only_launch_failure_writes_strict_evidence_before_reraising(self):
        """Catches a cached but non-executable binary escaping without evidence."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
            self._write_strict_cache(
                root,
                sv_path=sv_path,
                image_path=image_path,
                manifest_path=manifest_path,
                oracle_path=oracle_path,
                binary_text="#!/bin/sh\nexit 0\n",
            )
            (root / "obj_dir" / "Vtb").chmod(0o644)
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                RuntimeError, "simulation_launch"
            ):
                module.main_from_args([
                    "--equivalence-shard", str(oracle_path),
                    "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                    *self._strict_source_flags(root),
                    "--sv", str(sv_path),
                    "--image", str(image_path),
                    "--manifest", str(manifest_path),
                    "--work-dir", str(root),
                    "--run-only", "--verify-cache",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "simulation_launch")
            self.assertIn("Permission denied", counterexample["error"])
            failed = json.loads((root / "equivalence-receipt.json").read_text())
            self.assertEqual(failed["status"], "fail")
            self.assertEqual(failed["failure"]["stage"], "simulation_launch")

    def test_run_only_rejects_mutated_strict_cache_artifacts(self):
        """Catches accepting a run-only cache after its executable or payload changes."""

        mutations = {
            "Vtb executable": lambda root: (root / "obj_dir" / "Vtb").write_bytes(
                (root / "obj_dir" / "Vtb").read_bytes() + b"\n# mutation\n"
            ),
            "normalized main.sv": lambda root: (root / "main.sv").write_bytes(
                (root / "main.sv").read_bytes() + b"\n// mutation\n"
            ),
            "tb.sv fixture": lambda root: (root / "tb.sv").write_bytes(
                (root / "tb.sv").read_bytes() + b"\n// mutation\n"
            ),
            "external memory bindings": lambda root: (
                root / "external-memory-bindings.json"
            ).write_bytes(
                (root / "external-memory-bindings.json").read_bytes() + b"\n"
            ),
            "runtime memory corruption": lambda root: (root / "mem0.hex").write_bytes(
                (root / "mem0.hex").read_bytes() + b"00\n"
            ),
            "runtime memory missing": lambda root: (root / "mem45.hex").unlink(),
        }
        for name, mutate in mutations.items():
            with self.subTest(artifact=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
                self._write_strict_cache(
                    root,
                    sv_path=sv_path,
                    image_path=image_path,
                    manifest_path=manifest_path,
                    oracle_path=oracle_path,
                    binary_text=(
                        "#!/bin/sh\n"
                        "echo 'CASE_PASS index=4 cycles=12 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111'\n"
                        "echo 'SHARD_PASS start=4 count=1 completed=1 min_cycles=12 max_cycles=12'\n"
                    ),
                )
                mutate(root)
                with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                    RuntimeError, "cache_validation"
                ):
                    module.main_from_args([
                        "--equivalence-shard", str(oracle_path),
                        "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                        "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                        "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                        *self._strict_source_flags(root),
                        "--sv", str(sv_path),
                        "--image", str(image_path),
                        "--manifest", str(manifest_path),
                        "--work-dir", str(root),
                        "--run-only", "--verify-cache",
                    ])
                counterexample = json.loads((root / "counterexample.json").read_text())
                self.assertEqual(counterexample["stage"], "cache_validation")
                failed = json.loads((root / "equivalence-receipt.json").read_text())
                self.assertEqual(failed["status"], "fail")
                self.assertEqual(failed["failure"]["stage"], "cache_validation")

    def test_run_only_parser_failures_write_simulation_result_evidence(self):
        """Catches malformed integers and cycle-bound lies escaping strict receipts."""

        oversized = "9" * 5_000
        transcripts = {
            "oversized integer": "\n".join([
                f"CASE_PASS index={oversized} cycles=1 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111",
                "SHARD_PASS start=4 count=1 completed=1 min_cycles=1 max_cycles=1",
            ]),
            "cycle-bound lie": "\n".join([
                "CASE_PASS index=4 cycles=1000001 expected_codes=0,1,2,3,4,5 observed_codes=0,1,2,3,4,5 expected_token=5 observed_token=5 done=1 completion_count=1 within_bound=1 reset_complete=1 reset_cycles=3 reset_ordinal=1 write_mask=111111",
                "SHARD_PASS start=4 count=1 completed=1 min_cycles=1000001 max_cycles=1000001",
            ]),
        }
        for name, transcript in transcripts.items():
            with self.subTest(transcript=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                sv_path, image_path, manifest_path, oracle_path = self._strict_run_paths(root)
                self._write_strict_cache(
                    root,
                    sv_path=sv_path,
                    image_path=image_path,
                    manifest_path=manifest_path,
                    oracle_path=oracle_path,
                    binary_text=f"#!/bin/sh\necho '{transcript}'\n",
                )
                with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                    RuntimeError, "counterexample"
                ):
                    module.main_from_args([
                        "--equivalence-shard", str(oracle_path),
                        "--f32-constant-bits", str(root / "f32-constant-bits.json"),
                        "--f32-calyx-mlir", str(root / "constant-proof/normalized.calyx.mlir"),
                        "--f32-raw-futil", str(root / "constant-proof/exported.raw.futil"),
                        *self._strict_source_flags(root),
                        "--sv", str(sv_path),
                        "--image", str(image_path),
                        "--manifest", str(manifest_path),
                        "--work-dir", str(root),
                        "--run-only", "--verify-cache",
                    ])
                counterexample = json.loads((root / "counterexample.json").read_text())
                self.assertEqual(counterexample["stage"], "simulation_result")
                failed = json.loads((root / "equivalence-receipt.json").read_text())
                self.assertEqual(failed["status"], "fail")
                self.assertEqual(failed["failure"]["stage"], "simulation_result")

    def test_preflight_failure_writes_counterexample_before_raising(self):
        """Catches an invalid shard path escaping proof mode without evidence."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "preflight"):
                module.main_from_args([
                    "--equivalence-shard", str(root / "missing-oracle.json"),
                    "--f32-constant-bits", str(root / "missing-f32-constant-bits.json"),
                    "--f32-calyx-mlir", str(root / "missing-normalized.calyx.mlir"),
                    "--f32-raw-futil", str(root / "missing-exported.raw.futil"),
                    "--flat-scf", str(root / "missing-flat.scf.mlir"),
                    "--pre-calyx", str(root / "missing-pre-calyx.mlir"),
                    "--sv", str(root / "missing.sv"),
                    "--image", str(root / "missing.bin"),
                    "--manifest", str(root / "missing-manifest.json"),
                    "--work-dir", str(root),
                    "--fixture-only",
                ])
            counterexample = json.loads((root / "counterexample.json").read_text())
            self.assertEqual(counterexample["stage"], "preflight")


if __name__ == "__main__":
    unittest.main()
