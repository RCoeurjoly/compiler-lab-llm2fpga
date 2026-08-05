import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import inspect
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/run_rc_sv_equivalence.py"
spec = importlib.util.spec_from_file_location("run_rc_sv_equivalence", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RcSvEquivalenceFixtureTest(unittest.TestCase):
    @staticmethod
    def _fixture_ports():
        ports = {number: (32, 2) for number in range(146)}
        ports[25] = (64, 8)
        ports[26] = (8, 64)
        for number in range(28, 44):
            ports[number] = (32, 2)
        ports[44] = (32, 32)
        ports[45] = (32, 16)
        for number in range(46, 146):
            ports[number] = (8, 64)
        return ports

    @classmethod
    def _fixture_sv(cls, *, unsupported_write_enable=False):
        declarations = []
        assignments = []
        immutable = (
            set(range(25))
            | set(range(27, 46))
            | {25}
        )
        for number, (width, depth) in sorted(cls._fixture_ports().items()):
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
            if unsupported_write_enable and number == 46:
                expression = "write_active_46 & write_guard_46"
            elif number in immutable:
                expression = f"read_guard_{number} ? 1'd0 : 1'd0"
            else:
                expression = f"write_active_{number}"
            assignments.append(
                f"assign arg_mem_{number}_write_en = {expression};"
            )
        return (
            "module main_1(\n"
            + ",\n".join(declarations)
            + "\n);\n"
            + "\n".join(assignments)
            + "\nendmodule\n"
        )

    @staticmethod
    def _fixture_image_and_manifest():
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
    def _fixture_reference():
        return {
            "results": [
                {
                    "case_id": "ascending",
                    "token_ids": [0, 1, 2, 3, 4, 5, 0, 1],
                    "output_codes_i8": [1, 2, 3, 4, 5, 6],
                    "token_id": 5,
                },
                {
                    "case_id": "descending",
                    "token_ids": [5, 4, 3, 2, 1, 0, 5, 4],
                    "output_codes_i8": [-1, -2, -3, -4, -5, -6],
                    "token_id": 0,
                },
            ]
        }

    @classmethod
    def _fixture_abi_receipt(cls):
        return module._memory_abi_receipt(module._memory_abi(cls._fixture_sv()))

    @classmethod
    def _binding_fixture(cls, *, flatten_tail=False):
        image, manifest = cls._fixture_image_and_manifest()
        payload = bytearray(image)
        manifest = json.loads(json.dumps(manifest))
        declarations = [
            '  memref.global "private" constant @scalar_zero : memref<f32> = '
            'dense<0.000000e+00> {alignment = 64 : i64}'
        ]
        resources = []
        ordered = [("scalar_zero", [])]
        raw_by_symbol = {}

        def add_resource(symbol, shape, words, segment_names, *, lowered_shape=None):
            raw = b"".join(word.to_bytes(4, "little") for word in words)
            resource = f"resource_{symbol}"
            declarations.append(
                f'  memref.global "private" constant @{symbol} : '
                f'memref<{"x".join(map(str, shape))}xf32> = '
                f'dense_resource<{resource}> {{alignment = 64 : i64}}'
            )
            resource_hex = "0x" + (b"\x04\x00\x00\x00" + raw).hex().upper()
            resources.append(f'      {resource}: "{resource_hex}"')
            raw_by_symbol[symbol] = raw
            ordered.append((symbol, shape if lowered_shape is None else lowered_shape))
            for name in segment_names:
                offset = len(payload)
                payload.extend(raw)
                manifest["segments"].append({
                    "name": name,
                    "offset": offset,
                    "byte_length": len(raw),
                    "source_category": "state",
                    "dtype": "float32",
                    "shape": shape,
                })

        add_resource("prefix", [2], [0x3F000111, 0x3F000111], ["state/prefix"])
        # Image order is zero then one, deliberately opposite to get_global order.
        add_resource("z_one", [2], [0x3F800000, 0x3F800000], [])
        add_resource("a_zero", [2], [0, 0], ["state/zero"])
        for name in ("state/one-b", "state/one-a"):
            raw = raw_by_symbol["z_one"]
            offset = len(payload)
            payload.extend(raw)
            manifest["segments"].append({
                "name": name,
                "offset": offset,
                "byte_length": len(raw),
                "source_category": "state",
                "dtype": "float32",
                "shape": [2],
            })
        for port in range(31, 44):
            word = 0x3F100000 + port
            add_resource(f"tail_{port}", [2], [word, word], [f"state/tail-{port}"])
        add_resource("tail_44", [18], [0x3F200044] * 18, ["state/tail-44"])
        if flatten_tail:
            add_resource(
                "tail_45", [2, 2], [0x3F200045] * 4, ["state/tail-45"],
                lowered_shape=[4],
            )
        else:
            add_resource("tail_45", [12], [0x3F200045] * 12, ["state/tail-45"])

        flat_scf = (
            "module {\n"
            + "\n".join(declarations)
            + "\n}\n\n{-#\n  dialect_resources: {\n    builtin: {\n"
            + ",\n".join(resources)
            + "\n    }\n  }\n#-}\n"
        )
        gets = []
        for ordinal, (symbol, shape) in enumerate(ordered):
            element_type = "f32" if not shape else f'{"x".join(map(str, shape))}xf32'
            gets.append(
                f"    %{ordinal} = memref.get_global @{symbol} : memref<{element_type}>"
            )
        pre_calyx = "module {\n  func.func @main() {\n" + "\n".join(gets) + "\n  }\n}\n"
        return {
            "flat_scf": flat_scf,
            "pre_calyx": pre_calyx,
            "image": bytes(payload),
            "manifest": manifest,
            "abi": module._memory_abi(cls._fixture_sv()),
            "raw_by_symbol": raw_by_symbol,
        }

    def _fixture_text(self, **kwargs):
        image, manifest = self._fixture_image_and_manifest()
        with tempfile.TemporaryDirectory() as directory:
            path = module._fixture(
                self._fixture_sv(),
                image,
                manifest,
                self._fixture_reference(),
                Path(directory),
                **kwargs,
            )
            return path.read_text(encoding="utf-8")

    @staticmethod
    def _large_scalar_or(terms=3_000):
        names = [f"term_{index:04d}" for index in range(terms)]
        return "module m; logic enable; assign enable = " + " | ".join(names) + "; endmodule", names

    @staticmethod
    def _large_flat_ternary(*, declaration="logic [12:0] state", arms=2_000):
        chain = " : ".join(
            f"cond_{index:04d} ? 13'd{index}" for index in range(arms)
        )
        return f"module m; {declaration}; assign state = {chain} : 13'd0; endmodule"

    @staticmethod
    def _normalizer_page_sizes(source):
        return [
            expression.count(" | ") + 1
            for expression in re.findall(
                r"assign __llm2fpga_sim_[A-Za-z0-9_]+ = (.*?);", source, re.DOTALL
            )
        ]

    def test_calyx_memory_ports_are_parsed(self):
        source = """
        module main_1(
          input logic clk, output logic [2:0] arg_mem_25_addr0,
          output logic arg_mem_25_content_en, output logic arg_mem_25_write_en,
          output logic [63:0] arg_mem_25_write_data,
          input logic [63:0] arg_mem_25_read_data, input logic arg_mem_25_done,
          output logic [5:0] arg_mem_26_addr0,
          output logic [7:0] arg_mem_26_write_data,
          input logic [7:0] arg_mem_26_read_data, input logic arg_mem_26_done);
        endmodule
        """
        ports = module._ports(source)
        self.assertEqual(ports[25], (64, 8))
        self.assertEqual(ports[26], (8, 64))

    def test_memory_abi_marks_only_proven_zero_write_enables_immutable(self):
        abi = module._memory_abi(self._fixture_sv())
        self.assertEqual(abi[0].kind, "image")
        self.assertEqual(abi[25].kind, "token")
        self.assertEqual(abi[26].kind, "output")
        self.assertEqual(abi[46].kind, "scratch")
        self.assertEqual(abi[25].width, 64)
        self.assertEqual(abi[25].depth, 8)
        self.assertEqual(abi[26].width, 8)
        self.assertEqual(abi[26].depth, 64)
        self.assertEqual(
            {number for number, port in abi.items() if port.kind == "image"},
            module.IMAGE_PORTS,
        )
        self.assertEqual(
            {number for number, port in abi.items() if port.kind in ("image", "token")},
            module.IMMUTABLE_PORTS,
        )
        self.assertEqual(
            {number for number, port in abi.items() if port.kind in ("output", "scratch")},
            module.MUTABLE_PORTS,
        )

    def test_memory_abi_rejects_unknown_write_enable_form(self):
        with self.assertRaisesRegex(RuntimeError, "write-enable"):
            module._memory_abi(self._fixture_sv(unsupported_write_enable=True))

    def test_memory_abi_rejects_a_changed_frozen_image_port(self):
        changed = self._fixture_sv().replace(
            "assign arg_mem_0_write_en = read_guard_0 ? 1'd0 : 1'd0;",
            "assign arg_mem_0_write_en = write_active_0;",
        )
        with self.assertRaisesRegex(RuntimeError, "frozen memory ABI"):
            module._memory_abi(changed)

    def test_memory_abi_rejects_wrong_token_dimensions(self):
        changed = self._fixture_sv().replace(
            "output logic [63:0] arg_mem_25_write_data",
            "output logic [31:0] arg_mem_25_write_data",
        ).replace(
            "input logic [63:0] arg_mem_25_read_data",
            "input logic [31:0] arg_mem_25_read_data",
        )
        with self.assertRaisesRegex(RuntimeError, "arg_mem_25"):
            module._memory_abi(changed)

    def test_memory_abi_rejects_unclassified_external_pin(self):
        changed = self._fixture_sv().replace(
            "  output logic arg_mem_0_content_en,",
            "  output logic arg_mem_0_content_en,\n  output logic arg_mem_0_extra,",
        )
        with self.assertRaisesRegex(RuntimeError, "unclassified external"):
            module._memory_abi(changed)

    def test_memory_abi_rejects_missing_service_pin(self):
        changed = self._fixture_sv().replace("  input logic arg_mem_46_done,\n", "")
        with self.assertRaisesRegex(RuntimeError, "six ABI pins"):
            module._memory_abi(changed)

    def test_memory_abi_receipt_is_canonical_and_hashed(self):
        receipt = module._memory_abi_receipt(module._memory_abi(self._fixture_sv()))
        self.assertEqual(receipt["sha256"], hashlib.sha256(
            receipt["canonical_json"].encode("utf-8")
        ).hexdigest())
        self.assertEqual(len(receipt["ports"]), 146)
        self.assertEqual(receipt["ports"][0]["number"], 0)
        self.assertEqual(receipt["ports"][-1]["number"], 145)

    def test_external_float_bindings_follow_get_global_order(self):
        fixture = self._binding_fixture()
        receipt = module._build_calyx_memory_bindings(
            flat_scf=fixture["flat_scf"].encode(),
            pre_calyx=fixture["pre_calyx"].encode(),
            image=fixture["image"],
            manifest=fixture["manifest"],
            abi=fixture["abi"],
        )
        rows = {row["port"]: row for row in receipt["ports"]}
        self.assertEqual(rows[29]["words_u32"], [0x3F800000, 0x3F800000])
        self.assertEqual(rows[30]["words_u32"], [0, 0])
        self.assertEqual(
            rows[29]["image_segment_aliases"], ["state/one-a", "state/one-b"]
        )
        self.assertEqual(rows[29]["source_shape"], [2])
        self.assertEqual(rows[29]["lowered_shape"], [2])
        self.assertEqual(rows[29]["shape_transform"], "identity")

    def test_external_float_bindings_accept_contiguous_flatten(self):
        fixture = self._binding_fixture(flatten_tail=True)
        try:
            receipt = module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )
        except RuntimeError as error:
            self.fail(f"contiguous flatten should be accepted: {error}")
        row = {item["port"]: item for item in receipt["ports"]}[45]
        self.assertEqual(row["source_shape"], [2, 2])
        self.assertEqual(row["lowered_shape"], [4])
        self.assertEqual(row["shape_transform"], "contiguous-flatten")

    def test_external_float_bindings_reject_malformed_resource_framing(self):
        fixture = self._binding_fixture()
        fixture["flat_scf"] = fixture["flat_scf"].replace(
            "0x04000000", "0x05000000", 1
        )
        with self.assertRaisesRegex(RuntimeError, "framing"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_wrong_resource_payload_length(self):
        fixture = self._binding_fixture()
        raw_hex = fixture["raw_by_symbol"]["prefix"].hex().upper()
        fixture["flat_scf"] = fixture["flat_scf"].replace(raw_hex, raw_hex[:-8], 1)
        with self.assertRaisesRegex(RuntimeError, "payload length"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_non_f32_source_global(self):
        fixture = self._binding_fixture()
        fixture["flat_scf"] = fixture["flat_scf"].replace(
            "@prefix : memref<2xf32>", "@prefix : memref<2xi32>", 1
        )
        with self.assertRaisesRegex(RuntimeError, "f32"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_inline_nonzero_decimal(self):
        fixture = self._binding_fixture()
        fixture["flat_scf"] = fixture["flat_scf"].replace(
            "dense_resource<resource_prefix>", "dense<1.000000e+00>", 1
        )
        with self.assertRaisesRegex(RuntimeError, "inline"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_allow_inline_zero_only_at_port_27(self):
        fixture = self._binding_fixture()
        fixture["flat_scf"] = re.sub(
            r'@prefix : memref<2xf32> = dense_resource<resource_prefix>',
            '@prefix : memref<f32> = dense<0.0>',
            fixture["flat_scf"], count=1,
        )
        fixture["pre_calyx"] = fixture["pre_calyx"].replace(
            "@prefix : memref<2xf32>", "@prefix : memref<f32>", 1
        )
        offset = len(fixture["image"])
        fixture["image"] += b"\0" * 4
        fixture["manifest"]["segments"].append({
            "name": "state/inline-zero",
            "offset": offset,
            "byte_length": 4,
            "source_category": "state",
            "dtype": "float32",
            "shape": [1],
        })
        with self.assertRaisesRegex(RuntimeError, "port 27"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_missing_get_global(self):
        fixture = self._binding_fixture()
        fixture["pre_calyx"] = re.sub(
            r"^\s*%18 = memref\.get_global[^\n]*\n", "", fixture["pre_calyx"],
            flags=re.MULTILINE,
        )
        with self.assertRaisesRegex(RuntimeError, "exactly 19"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_reordered_get_global_results(self):
        fixture = self._binding_fixture()
        fixture["pre_calyx"] = fixture["pre_calyx"].replace("    %1 =", "    %tmp =", 1)
        fixture["pre_calyx"] = fixture["pre_calyx"].replace("    %2 =", "    %1 =", 1)
        fixture["pre_calyx"] = fixture["pre_calyx"].replace("    %tmp =", "    %2 =", 1)
        with self.assertRaisesRegex(RuntimeError, "ordered"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_source_lowered_shape_disagreement(self):
        fixture = self._binding_fixture()
        fixture["pre_calyx"] = fixture["pre_calyx"].replace(
            "@z_one : memref<2xf32>", "@z_one : memref<1xf32>", 1
        )
        with self.assertRaisesRegex(RuntimeError, "shape disagrees"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_same_size_shape_disagreement(self):
        fixture = self._binding_fixture()
        fixture["pre_calyx"] = fixture["pre_calyx"].replace(
            "@z_one : memref<2xf32>", "@z_one : memref<1x2xf32>", 1
        )
        with self.assertRaisesRegex(RuntimeError, "shape disagrees"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_missing_identical_image_segment(self):
        fixture = self._binding_fixture()
        fixture["manifest"]["segments"] = [
            segment for segment in fixture["manifest"]["segments"]
            if segment["name"] != "state/prefix"
        ]
        with self.assertRaisesRegex(RuntimeError, "no byte-identical"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_bindings_reject_insufficient_abi_depth(self):
        fixture = self._binding_fixture()
        original = fixture["abi"][29]
        fixture["abi"][29] = module.MemoryPort(
            number=29, width=32, depth=1, kind=original.kind,
            write_enable_sha256=original.write_enable_sha256,
        )
        with self.assertRaisesRegex(RuntimeError, "cannot hold"):
            module._build_calyx_memory_bindings(
                flat_scf=fixture["flat_scf"].encode(),
                pre_calyx=fixture["pre_calyx"].encode(),
                image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
            )

    def test_external_float_binding_receipt_rejects_post_hash_row_mutation(self):
        fixture = self._binding_fixture()
        receipt = module._build_calyx_memory_bindings(
            flat_scf=fixture["flat_scf"].encode(),
            pre_calyx=fixture["pre_calyx"].encode(),
            image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
        )
        receipt["ports"][2]["words_u32"][0] = 0
        with self.assertRaisesRegex(RuntimeError, "canonical JSON"):
            module._validate_calyx_memory_bindings_receipt(receipt)

    def test_external_float_binding_receipt_rejects_canonical_arbitrary_reshape(self):
        fixture = self._binding_fixture()
        receipt = module._build_calyx_memory_bindings(
            flat_scf=fixture["flat_scf"].encode(),
            pre_calyx=fixture["pre_calyx"].encode(),
            image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
        )
        receipt["ports"][2]["lowered_shape"] = [1, 2]
        receipt["ports"][2]["shape_transform"] = "contiguous-flatten"
        payload = {
            key: value for key, value in receipt.items()
            if key not in ("canonical_json", "sha256")
        }
        receipt["canonical_json"] = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        )
        receipt["sha256"] = hashlib.sha256(
            receipt["canonical_json"].encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(RuntimeError, "shape transform"):
            module._validate_calyx_memory_bindings_receipt(receipt)

    def test_fixture_materializes_external_float_ports_only_from_receipt(self):
        fixture = self._binding_fixture()
        receipt = module._build_calyx_memory_bindings(
            flat_scf=fixture["flat_scf"].encode(),
            pre_calyx=fixture["pre_calyx"].encode(),
            image=fixture["image"], manifest=fixture["manifest"], abi=fixture["abi"],
        )
        ports = {
            number: (port.width, port.depth)
            for number, port in fixture["abi"].items()
        }
        with tempfile.TemporaryDirectory() as directory:
            module._materialize_fixture_memories(
                fixture["image"], fixture["manifest"], Path(directory), ports, receipt
            )
            self.assertEqual(
                (Path(directory) / "mem29.hex").read_text(encoding="ascii").splitlines(),
                ["3f800000", "3f800000"],
            )
            self.assertEqual(
                (Path(directory) / "mem30.hex").read_text(encoding="ascii").splitlines(),
                ["00000000", "00000000"],
            )

    def test_memory_abi_ignores_non_main_1_wrapper_ports(self):
        wrapper = """
        module misleading_wrapper(output logic arg_mem_0_write_en);
          assign arg_mem_0_write_en = 1'd1;
        endmodule
        """
        abi = module._memory_abi(wrapper + self._fixture_sv())
        self.assertEqual(abi[0].kind, "image")

    def test_memory_abi_rejects_duplicate_main_1_modules(self):
        with self.assertRaisesRegex(RuntimeError, "exactly one module main_1"):
            module._memory_abi(self._fixture_sv() + self._fixture_sv())

    def test_fixture_resets_every_mutable_port_and_faults_on_image_write(self):
        tb = self._fixture_text()
        self.assertIn(
            "task automatic reset_transaction(input longint unsigned context_index);",
            tb,
        )
        self.assertIn("for (int i=0; i<64; i++) mem26[i] = '0;", tb)
        self.assertIn("for (int i=0; i<64; i++) mem145[i] = '0;", tb)
        self.assertIn("IMMUTABLE_WRITE port=0", tb)
        self.assertIn("RC_MEMORY_ABI_SHA256", tb)
        transaction_task = tb.split("task automatic reset_transaction", 1)[1].split(
            "endtask", 1
        )[0]
        self.assertNotIn("mem0[i] = '0;", transaction_task)
        self.assertIn("mem25[token_slot] = token_value % 6;", transaction_task)
        self.assertIn(
            "repeat (3) @(posedge clk);\n"
            "    @(negedge clk);\n"
            "    reset = 1'b0;",
            transaction_task,
        )
        reset_ports = {
            int(number)
            for number in re.findall(
                r"for \(int i=0; i<\d+; i\+\+\) mem(\d+)\[i\] = '0;",
                transaction_task,
            )
        }
        self.assertTrue(module.MUTABLE_PORTS <= reset_ports)
        self.assertEqual(
            reset_ports - {module.TOKEN_PORT},
            module.MUTABLE_PORTS,
        )

    def test_fixture_requires_functional_buffers(self):
        with self.assertRaises(RuntimeError):
            module._fixture("module main(input logic clk); endmodule", b"", {"segments": []}, {}, Path("/tmp"))

    def test_large_fsm_rewrite_does_not_rewrite_wide_or_trees(self):
        source = "logic scalar; logic [12:0] wide; assign scalar = a | b; assign wide = c ? 13'd1 : 13'd0;"
        normalized = module._normalize_large_or_assignments(source)
        self.assertEqual(normalized, source)

    def test_fixture_runtime_controls_allow_quiet_cached_runs(self):
        text = self._fixture_text(
            heartbeat_cycles=0,
            case_id="ascending",
            stop_after_output=True,
            trace_output_writes=False,
        )
        self.assertIn('$value$plusargs("heartbeat_cycles=%d", heartbeat_cycles)', text)
        self.assertIn('$value$plusargs("case_index=%d", selected_case_index)', text)
        self.assertIn("if (heartbeat_cycles > 0) begin", text)
        self.assertNotIn("% 0", text)
        self.assertIn('if (trace_output_writes != 0) $display("OUTWRITE ', text)
        self.assertIn('RESULT ascending', text)
        self.assertIn('RESULT descending', text)
        self.assertIn(
            "always_ff @(posedge clk) begin\n"
            "  if (reset) begin output_write_count <= 0; last_request_port <= -1; "
            "output_write_mask <= '0; immutable_write_seen <= 1'b0; end\n",
            text,
        )
        self.assertIn(
            "if (reset) begin request_count <= 0; completion_count <= 0; "
            "memory_completion_count <= 0; end",
            text,
        )

    def test_runtime_args_select_case_without_rebuilding_fixture(self):
        args = argparse.Namespace(
            heartbeat_cycles=0,
            timeout_cycles=123,
            case_id="ascending",
            stop_after_output=True,
            trace_output_writes=False,
        )
        runtime_args = module._runtime_args(args, self._fixture_reference())
        self.assertEqual(
            runtime_args,
            [
                "+heartbeat_cycles=0",
                "+timeout_cycles=123",
                "+stop_after_output=1",
                "+trace_output_writes=0",
                "+case_index=0",
            ],
        )

    def test_static_fixture_runtime_args_omit_case_index(self):
        args = argparse.Namespace(
            heartbeat_cycles=0,
            timeout_cycles=123,
            case_id="ascending",
            stop_after_output=True,
            trace_output_writes=False,
            static_fixture_case=True,
        )
        self.assertEqual(
            module._runtime_args(args, self._fixture_reference()),
            [
                "+heartbeat_cycles=0",
                "+timeout_cycles=123",
                "+stop_after_output=1",
                "+trace_output_writes=0",
            ],
        )

    def test_fixture_accepts_static_case_id(self):
        self.assertIn("static_case_id", inspect.signature(module._fixture).parameters)

    def test_static_fixture_emits_only_the_selected_case(self):
        text = self._fixture_text(
            heartbeat_cycles=0,
            case_id="ascending",
            static_case_id="ascending",
            stop_after_output=True,
            trace_output_writes=False,
        )
        self.assertIn("RESULT ascending", text)
        self.assertNotIn("RESULT descending", text)
        self.assertNotIn("selected_case_index", text)
        self.assertNotIn('"case_index=%d"', text)

    def test_runtime_controls_use_non_elidable_plusarg_guards(self):
        text = self._fixture_text(case_id="ascending")
        self.assertNotIn("plusarg_unused", text)
        self.assertIn(
            'if ($value$plusargs("timeout_cycles=%d", timeout_cycles) '
            '&& timeout_cycles <= 0) timeout_cycles = 1;',
            text,
        )
        self.assertIn(
            'if ($value$plusargs("case_index=%d", selected_case_index) '
            '&& (selected_case_index < -1 || selected_case_index >= 2)) '
            'selected_case_index = -1;',
            text,
        )

    def test_boolean_runtime_controls_can_override_compiled_defaults(self):
        text = self._fixture_text(
            stop_after_output=True,
            trace_output_writes=True,
        )
        self.assertIn(
            'if ($value$plusargs("stop_after_output=%d", stop_after_output)) '
            'stop_after_output = (stop_after_output != 0);',
            text,
        )
        self.assertIn(
            'if ($value$plusargs("trace_output_writes=%d", trace_output_writes)) '
            'trace_output_writes = (trace_output_writes != 0);',
            text,
        )

    def test_cli_static_fixture_case_emits_a_static_fixture(self):
        image, manifest = self._fixture_image_and_manifest()
        reference = self._fixture_reference()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv = root / "main.sv"
            image_path = root / "image.bin"
            manifest_path = root / "manifest.json"
            reference_path = root / "reference.json"
            sv.write_text(self._fixture_sv(), encoding="utf-8")
            image_path.write_bytes(image)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            reference_path.write_text(json.dumps(reference), encoding="utf-8")
            output = io.StringIO()
            argv = [
                str(SCRIPT),
                "--sv", str(sv),
                "--image", str(image_path),
                "--manifest", str(manifest_path),
                "--reference", str(reference_path),
                "--work-dir", str(root),
                "--fixture-only",
                "--case-id", "ascending",
                "--static-fixture-case",
            ]
            with mock.patch.object(sys, "argv", argv), redirect_stdout(output):
                try:
                    module.main()
                except SystemExit as error:
                    self.fail(f"static fixture CLI should succeed, got {error}")
            result = json.loads(output.getvalue())
            self.assertNotIn("+case_index=0", result["runtime_args"])
            fixture = (root / "tb.sv").read_text(encoding="utf-8")
            self.assertIn("RESULT ascending", fixture)
            self.assertNotIn("RESULT descending", fixture)
            self.assertIn(result["memory_abi"]["sha256"], fixture)
            self.assertEqual(
                result["memory_abi"]["canonical_json"],
                (root / "memory-abi.json").read_text(encoding="utf-8").strip(),
            )

    def test_cli_static_fixture_requires_case_id(self):
        image, manifest = self._fixture_image_and_manifest()
        reference = self._fixture_reference()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sv = root / "main.sv"
            image_path = root / "image.bin"
            manifest_path = root / "manifest.json"
            reference_path = root / "reference.json"
            sv.write_text(self._fixture_sv(), encoding="utf-8")
            image_path.write_bytes(image)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            reference_path.write_text(json.dumps(reference), encoding="utf-8")
            argv = [
                str(SCRIPT),
                "--sv", str(sv),
                "--image", str(image_path),
                "--manifest", str(manifest_path),
                "--reference", str(reference_path),
                "--work-dir", str(root),
                "--fixture-only",
                "--static-fixture-case",
            ]
            with mock.patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as error:
                module.main()
            self.assertEqual(error.exception.code, 2)

    def test_compiled_cache_requires_a_valid_memory_abi_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {}
            for name, contents in {
                "sv": "module main_1; endmodule\n",
                "image": "image",
                "manifest": "{\"segments\": []}\n",
                "reference": "{\"results\": []}\n",
            }.items():
                path = root / name
                path.write_text(contents, encoding="utf-8")
                inputs[name] = path
            args = argparse.Namespace(
                **inputs,
                simulator="verilator",
                timeout_cycles=123,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
            )
            binary = root / "obj_dir" / "Vtb"
            binary.parent.mkdir()
            binary.write_text("binary", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._compiled_cache_metadata(args, {}, {}, {}, binary, root)

            receipt = self._fixture_abi_receipt()
            metadata = module._compiled_cache_metadata(
                args, {}, {}, {}, binary, root, receipt
            )
            self.assertEqual(metadata["memory_abi"]["sha256"], receipt["sha256"])

            malformed = dict(receipt)
            malformed["sha256"] = "0" * 64
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._compiled_cache_metadata(args, {}, {}, {}, binary, root, malformed)

            missing = dict(metadata)
            missing.pop("memory_abi")
            module._write_cache_metadata(root, missing)
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._load_cache_metadata(args, root, verify_inputs=True)

            malformed_metadata = dict(metadata)
            malformed_metadata["memory_abi"] = malformed
            module._write_cache_metadata(root, malformed_metadata)
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._load_cache_metadata(args, root, verify_inputs=True)

            noncanonical = json.loads(json.dumps(receipt))
            noncanonical["canonical_json"] = json.dumps(
                noncanonical["ports"], sort_keys=True
            )
            noncanonical["sha256"] = hashlib.sha256(
                noncanonical["canonical_json"].encode("utf-8")
            ).hexdigest()
            malformed_metadata["memory_abi"] = noncanonical
            module._write_cache_metadata(root, malformed_metadata)
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._load_cache_metadata(args, root, verify_inputs=True)

            malformed_rows = json.loads(json.dumps(receipt))
            malformed_rows["ports"][0].pop("kind")
            malformed_rows["canonical_json"] = json.dumps(
                malformed_rows["ports"], sort_keys=True, separators=(",", ":")
            )
            malformed_rows["sha256"] = hashlib.sha256(
                malformed_rows["canonical_json"].encode("utf-8")
            ).hexdigest()
            malformed_metadata["memory_abi"] = malformed_rows
            module._write_cache_metadata(root, malformed_metadata)
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._load_cache_metadata(args, root, verify_inputs=True)

            changed_class = json.loads(json.dumps(receipt))
            changed_class["ports"][0]["kind"] = "scratch"
            changed_class["canonical_json"] = json.dumps(
                changed_class["ports"], sort_keys=True, separators=(",", ":")
            )
            changed_class["sha256"] = hashlib.sha256(
                changed_class["canonical_json"].encode("utf-8")
            ).hexdigest()
            malformed_metadata["memory_abi"] = changed_class
            module._write_cache_metadata(root, malformed_metadata)
            with self.assertRaisesRegex(RuntimeError, "memory ABI receipt"):
                module._load_cache_metadata(args, root, verify_inputs=True)

    def test_verified_cache_rejects_static_fixture_mode_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {}
            for name, contents in {
                "sv": "module main_1; endmodule\n",
                "image": "image",
                "manifest": "{\"segments\": []}\n",
                "reference": "{\"results\": []}\n",
            }.items():
                path = root / name
                path.write_text(contents, encoding="utf-8")
                inputs[name] = path
            static_args = argparse.Namespace(
                **inputs,
                simulator="verilator",
                timeout_cycles=123,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
                case_id="ascending",
                static_fixture_case=True,
            )
            binary = root / "obj_dir" / "Vtb"
            binary.parent.mkdir()
            binary.write_text("binary", encoding="utf-8")
            module._write_cache_metadata(
                root,
                module._compiled_cache_metadata(
                    static_args,
                    {},
                    {},
                    {},
                    binary,
                    root,
                    self._fixture_abi_receipt(),
                ),
            )
            dynamic_args = argparse.Namespace(
                **inputs,
                simulator="verilator",
                timeout_cycles=123,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
                case_id="ascending",
                static_fixture_case=False,
            )
            with self.assertRaisesRegex(RuntimeError, "fixture"):
                module._load_cache_metadata(dynamic_args, root, verify_inputs=True)

    def test_verified_cache_rejects_different_static_fixture_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {}
            for name, contents in {
                "sv": "module main_1; endmodule\n",
                "image": "image",
                "manifest": "{\"segments\": []}\n",
                "reference": "{\"results\": []}\n",
            }.items():
                path = root / name
                path.write_text(contents, encoding="utf-8")
                inputs[name] = path
            ascending_args = argparse.Namespace(
                **inputs,
                simulator="verilator",
                timeout_cycles=123,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
                case_id="ascending",
                static_fixture_case=True,
            )
            binary = root / "obj_dir" / "Vtb"
            binary.parent.mkdir()
            binary.write_text("binary", encoding="utf-8")
            module._write_cache_metadata(
                root,
                module._compiled_cache_metadata(
                    ascending_args,
                    {},
                    {},
                    {},
                    binary,
                    root,
                    self._fixture_abi_receipt(),
                ),
            )
            descending_args = argparse.Namespace(
                **inputs,
                simulator="verilator",
                timeout_cycles=123,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
                case_id="descending",
                static_fixture_case=True,
            )
            with self.assertRaisesRegex(RuntimeError, "fixture"):
                module._load_cache_metadata(descending_args, root, verify_inputs=True)

    def test_verified_run_cache_binds_all_fixture_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {}
            for name, contents in {
                "sv": "module main_1; endmodule\n",
                "image": "image",
                "manifest": "{\"segments\": []}\n",
                "reference": "{\"results\": []}\n",
            }.items():
                path = root / name
                path.write_text(contents, encoding="utf-8")
                inputs[name] = path
            args = argparse.Namespace(
                sv=inputs["sv"],
                image=inputs["image"],
                manifest=inputs["manifest"],
                reference=inputs["reference"],
                simulator="verilator",
                timeout_cycles=123,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
            )
            metadata = module._compiled_cache_metadata(
                args,
                {"verilate_jobs": 4},
                {"verilator_compile_seconds": 1.0},
                {"binary_bytes": 2},
                root / "obj_dir" / "Vtb",
                root,
                self._fixture_abi_receipt(),
            )
            module._write_cache_metadata(root, metadata)
            self.assertIn("runner_sha256", metadata)
            loaded = module._load_cache_metadata(args, root, verify_inputs=True)
            self.assertEqual(loaded["compile"]["configuration"], {"verilate_jobs": 4})
            self.assertEqual(loaded["compile"]["binary_relative_path"], "obj_dir/Vtb")
            inputs["reference"].write_text("{\"results\": [1]}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "reference_sha256"):
                module._load_cache_metadata(args, root, verify_inputs=True)
            inputs["reference"].write_text("{\"results\": []}\n", encoding="utf-8")
            metadata["runner_sha256"] = "stale"
            module._write_cache_metadata(root, metadata)
            with self.assertRaisesRegex(RuntimeError, "runner_sha256"):
                module._load_cache_metadata(args, root, verify_inputs=True)

    def test_verified_run_only_reports_cached_compile_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {
                "sv": root / "main.sv",
                "image": root / "image.bin",
                "manifest": root / "manifest.json",
                "reference": root / "reference.json",
            }
            inputs["sv"].write_text("module main_1; endmodule\n", encoding="utf-8")
            inputs["image"].write_bytes(b"image")
            inputs["manifest"].write_text("{\"segments\": []}\n", encoding="utf-8")
            reference = self._fixture_reference()
            inputs["reference"].write_text(json.dumps(reference), encoding="utf-8")
            binary = root / "obj_dir" / "Vtb"
            binary.parent.mkdir()
            binary.write_text(
                "#!/bin/sh\necho 'RESULT ascending 1 2 3 4 5 6'\n",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            compile_args = argparse.Namespace(
                **inputs,
                simulator="verilator",
                timeout_cycles=1_000_000,
                heartbeat_cycles=0,
                stop_after_output=False,
                trace_output_writes=False,
            )
            module._write_cache_metadata(
                root,
                module._compiled_cache_metadata(
                    compile_args,
                    {"verilate_jobs": 7, "build_jobs": 3},
                    {"verilator_compile_seconds": 1.0},
                    {"binary_bytes": binary.stat().st_size},
                    binary,
                    root,
                    self._fixture_abi_receipt(),
                ),
            )
            output = io.StringIO()
            with mock.patch.object(
                sys,
                "argv",
                [
                    str(SCRIPT),
                    "--sv", str(inputs["sv"]),
                    "--image", str(inputs["image"]),
                    "--manifest", str(inputs["manifest"]),
                    "--reference", str(inputs["reference"]),
                    "--work-dir", str(root),
                    "--case-id", "ascending",
                    "--verify-cache",
                    "--run-only",
                ],
            ), redirect_stdout(output):
                module.main()
            result = json.loads(output.getvalue())
            self.assertEqual(
                result["configuration"], {"verilate_jobs": 7, "build_jobs": 3}
            )
            self.assertEqual(
                result["cached_compile"]["binary_relative_path"], "obj_dir/Vtb"
            )
            self.assertEqual(
                result["memory_abi"]["sha256"],
                self._fixture_abi_receipt()["sha256"],
            )

    def test_large_scalar_or_is_rewritten_as_continuous_bounded_pages(self):
        source, terms = self._large_scalar_or()
        normalized = module._normalize_large_or_assignments(source)
        self.assertNotIn("always_comb", normalized)
        self.assertNotIn(" if (", normalized)
        self.assertEqual(re.findall(r"term_\d{4}", normalized), terms)
        self.assertTrue(self._normalizer_page_sizes(normalized))
        self.assertLessEqual(
            max(self._normalizer_page_sizes(normalized)),
            module.NORMALIZER_PAGE_TERMS,
        )
        metrics = module._normalization_metrics(source, normalized)
        self.assertEqual(metrics["raw_sv_bytes"], len(source.encode("utf-8")))
        self.assertEqual(metrics["normalizer_page_wires"], len(self._normalizer_page_sizes(normalized)))
        self.assertEqual(metrics["normalizer_added_always_comb_blocks"], 0)
        self.assertNotIn("normalizer_procedural_blocks", metrics)

    def test_normalizer_metrics_exclude_preexisting_page_like_wires(self):
        source, _ = self._large_scalar_or()
        source = source.replace(
            "logic enable;",
            "logic enable; wire __llm2fpga_sim_preexisting;",
        )
        normalized = module._normalize_large_or_assignments(source)
        metrics = module._normalization_metrics(source, normalized)
        self.assertEqual(
            metrics["normalizer_page_wires"],
            len(self._normalizer_page_sizes(normalized)),
        )

    def test_large_proven_ternary_uses_ordered_continuous_pages(self):
        source = self._large_flat_ternary()
        normalized = module._normalize_large_or_assignments(source)
        self.assertNotIn("always_comb", normalized)
        self.assertNotIn(" if (", normalized)
        self.assertIn("wire [12:0] __llm2fpga_sim_", normalized)
        self.assertEqual(len(re.findall(r"cond_\d{4}", normalized)), 2_000)
        self.assertIn("cond_0000 ? 13'd0", normalized)
        self.assertIn("cond_1999 ? 13'd1999", normalized)

    def test_large_unproven_expressions_are_unchanged(self):
        wide_or, _ = self._large_scalar_or()
        wide_or = wide_or.replace("logic enable", "logic [12:0] enable")
        signed_ternary = self._large_flat_ternary(
            declaration="logic signed [12:0] state"
        )
        self.assertEqual(module._normalize_large_or_assignments(wide_or), wide_or)
        self.assertEqual(module._normalize_large_or_assignments(signed_ternary), signed_ternary)

    def test_verilator_compile_is_two_semantic_stages(self):
        args = argparse.Namespace(
            verilator="verilator",
            verilator_output_split=100,
            verilator_output_split_cfuncs=50,
            verilator_threads=2,
            verilator_jobs=None,
            verilate_jobs=3,
            build_jobs=7,
            make="make",
        )
        obj_dir = Path("/tmp/obj_dir")
        codegen = module._verilator_codegen_command(
            args, Path("/tmp/main.sv"), Path("/tmp/tb.sv"), obj_dir, 3
        )
        build = module._verilator_build_command(args, obj_dir, 7)
        self.assertIn("--cc", codegen)
        self.assertIn("--exe", codegen)
        self.assertIn("--main", codegen)
        self.assertIn("--threads", codegen)
        self.assertEqual(build[:5], ["make", "-C", str(obj_dir), "-f", "Vtb.mk"])
        self.assertEqual(build[-2:], ["7", "Vtb"])

    def test_legacy_verilator_jobs_populates_both_stages(self):
        args = argparse.Namespace(verilator_jobs=9, verilate_jobs=None, build_jobs=None)
        self.assertEqual(module._resolved_verilator_jobs(args), (9, 9))

    def test_flake_exposes_rc_verilator_config_matrix(self):
        self.assertTrue((ROOT / "diagnostics/rc-verilator-config-matrix.nix").is_file())
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn('"tinystories-w8a8-rc-verilator-config-matrix"', flake)

    def test_flake_exposes_rc_normalizer_semantics_check(self):
        self.assertTrue((ROOT / "diagnostics/rc-sv-normalizer-semantics.nix").is_file())
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
        self.assertIn('"tinystories-w8a8-rc-sv-normalizer-semantics"', flake)


if __name__ == "__main__":
    unittest.main()
