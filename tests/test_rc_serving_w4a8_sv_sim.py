import importlib.util
import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/run_rc_serving_w4a8_sv.py"
spec = importlib.util.spec_from_file_location("run_rc_serving_w4a8_sv", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class RcServingW4A8SvSimTest(unittest.TestCase):
    def test_flat_scf_abi_preserves_semantic_argument_order(self) -> None:
        mlir = """
        module {
          func.func @main(%arg0: memref<1xi64>, %arg1: memref<2x2xi8>,
                          %arg2: memref<1x1x6xf32>, %arg3: memref<1x1x9x2xf32>) {
            return
          }
        }
        """
        abi = module.parse_flat_scf_abi(mlir)
        self.assertEqual(
            [(item.number, item.shape, item.width) for item in abi],
            [(0, (1,), 64), (1, (2, 2), 8), (2, (1, 1, 6), 32),
             (3, (1, 1, 9, 2), 32)],
        )

    def test_decode_phase_classifies_five_outputs_after_32_inputs(self) -> None:
        roles = module.phase_roles("decode-8", semantic_port_count=37)
        self.assertEqual(roles.inputs, tuple(range(32)))
        self.assertEqual(roles.outputs, tuple(range(32, 37)))
        self.assertEqual(roles.logits, 32)
        self.assertEqual(roles.cache_outputs, (33, 34, 35, 36))

    def test_prefill_phase_classifies_five_outputs_after_28_inputs(self) -> None:
        roles = module.phase_roles("prefill-8", semantic_port_count=33)
        self.assertEqual(roles.inputs, tuple(range(28)))
        self.assertEqual(roles.outputs, tuple(range(28, 33)))

    def test_memory_words_preserve_signed_and_ieee_bit_patterns(self) -> None:
        self.assertEqual(module.memory_words(bytes([0xFF, 0x80]), width=8), ["ff", "80"])
        floats = struct.pack("<ff", 1.0, -2.5)
        self.assertEqual(module.memory_words(floats, width=32), ["3f800000", "c0200000"])
        integers = struct.pack("<q", 6)
        self.assertEqual(module.memory_words(integers, width=64), ["0000000000000006"])

    def test_memory_words_reject_partial_elements(self) -> None:
        with self.assertRaisesRegex(ValueError, "multiple of 4"):
            module.memory_words(b"abc", width=32)

    def test_sv_memory_ports_are_derived_from_main_1_header(self) -> None:
        sv = """module main_1(
          output logic arg_mem_0_addr0, output logic arg_mem_0_content_en,
          output logic arg_mem_0_write_en, output logic [63:0] arg_mem_0_write_data,
          input logic [63:0] arg_mem_0_read_data, input logic arg_mem_0_done,
          output logic [2:0] arg_mem_1_addr0, output logic arg_mem_1_content_en,
          output logic arg_mem_1_write_en, output logic [7:0] arg_mem_1_write_data,
          input logic [7:0] arg_mem_1_read_data, input logic arg_mem_1_done
        ); endmodule"""
        ports = module.parse_sv_memory_ports(sv)
        self.assertEqual([(port.number, port.width, port.depth) for port in ports],
                         [(0, 64, 2), (1, 8, 8)])

    def test_semantic_abi_rejects_rtl_width_or_depth_mismatch(self) -> None:
        semantic = (module.SemanticMemory(0, (3,), 8),)
        with self.assertRaisesRegex(ValueError, "depth"):
            module.validate_abi(semantic, (module.SvMemoryPort(0, 8, 2),))
        with self.assertRaisesRegex(ValueError, "width"):
            module.validate_abi(semantic, (module.SvMemoryPort(0, 32, 4),))

    def test_runtime_values_follow_buffer_then_user_input_signature_order(self) -> None:
        specs = [
            SimpleNamespace(kind=SimpleNamespace(name="PARAMETER"), target="weight"),
            SimpleNamespace(kind=SimpleNamespace(name="BUFFER"), target="buffer"),
            SimpleNamespace(kind=SimpleNamespace(name="USER_INPUT"), target=None),
        ]
        exported = SimpleNamespace(
            graph_signature=SimpleNamespace(input_specs=specs),
            state_dict={"weight": "w", "buffer": "b"},
            constants={},
            example_inputs=(("token",), {}),
        )
        self.assertEqual(module.runtime_values(exported), ("b", "token"))


if __name__ == "__main__":
    unittest.main()
