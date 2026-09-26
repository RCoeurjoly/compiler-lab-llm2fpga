import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.pipeline.build_rc_phase_handoff import build_handoff
from scripts.pipeline.run_rc_serving_w4a8_sv import SemanticMemory, SvMemoryPort
from scripts.pipeline.run_rc_serving_w4a8_sv import parse_sv_memory_ports
from scripts.pipeline.verify_rc_serving_phase_abi import verify


PHASES = ("prefill-8", "decode-8", "decode-9")


def fixture():
    abi = {"schema": "rc-serving-w4a8-compiler-phase-abi-v1", "phases": []}
    phase_data = {}
    cursor = 0
    for name, length in zip(PHASES, (8, 9, 10)):
        leaves = []
        semantic = [SemanticMemory(i, (1,), 32) for i in range(37)]
        semantic[0] = SemanticMemory(0, (8,) if name == "prefill-8" else (1,), 64)
        token_port = 31 if name == "prefill-8" else 27
        semantic[token_port] = SemanticMemory(token_port, (1, 8) if name == "prefill-8" else (1, 1), 64)
        semantic[32] = SemanticMemory(32, (1, 8, 6) if name == "prefill-8" else (1, 1, 6), 32)
        for leaf in range(4):
            semantic[33 + leaf] = SemanticMemory(33 + leaf, (1, 1, length, 2), 32)
            if name != "prefill-8":
                semantic[28 + leaf] = SemanticMemory(28 + leaf, (1, 1, length - 1, 2), 32)
            leaves.append({"leaf": leaf, "shape": [1, 1, length, 2], "word_count": 2 * length,
                           "start_address": cursor + 7 + leaf * 2 * length})
        abi["phases"].append({"name": name, "token_address": cursor,
                              "logits": {"shape": [6], "word_count": 6, "start_address": cursor + 1},
                              "cache_leaves": leaves})
        source = name.encode()
        digest = hashlib.sha256(source).hexdigest()
        phase_data[name] = {
            "semantic": tuple(semantic),
            "token_input_port": token_port,
            "rtl": tuple(SvMemoryPort(i, m.width, 64) for i, m in enumerate(semantic)),
            "sv_sha256": digest,
            "namespace_receipt": {"input_sha256": digest, "output_sha256": "0" * 64,
                                  "modules": {"main_1": name.replace("-", "") + "__main_1"}},
            "flat_scf_sha256": "1" * 64,
            "exported_sha256": "2" * 64,
            "initial_memories": {},
        }
        cursor += 7 + 8 * length
    return abi, phase_data


class BuildHandoffTests(unittest.TestCase):
    def test_zero_extent_placeholder_keeps_64_bit_address_pin(self):
        source = """module main_1(
          output logic [63:0] arg_mem_0_addr0,
          output logic arg_mem_0_content_en,
          output logic arg_mem_0_write_en,
          output logic [31:0] arg_mem_0_write_data,
          input logic [31:0] arg_mem_0_read_data,
          input logic arg_mem_0_done
        ); endmodule"""
        parsed = parse_sv_memory_ports(source)
        self.assertEqual(parsed[0].depth, 1)
        self.assertEqual(parsed[0].address_width, 64)

    def test_handoff_carries_explicit_address_pin_width(self):
        abi, phases = fixture()
        ports = list(phases["prefill-8"]["rtl"])
        ports[1] = SvMemoryPort(1, 32, 1, 64)
        phases["prefill-8"]["rtl"] = tuple(ports)
        self.assertEqual(build_handoff(abi, phases)["phases"][0]["rtl_memories"][1]["address_width"], 64)

    def test_connects_cache_leaves_and_last_prefill_logits(self):
        abi, phases = fixture()
        manifest = build_handoff(abi, phases)
        self.assertEqual(manifest["phase_order"], list(PHASES))
        self.assertEqual(manifest["phases"][0]["logits"], {"port": 32, "offset": 42, "words": 6})
        self.assertEqual([phase["token_input_port"] for phase in manifest["phases"]], [31, 27, 27])
        self.assertEqual(manifest["handoffs"][0]["token_destination_port"], 27)
        self.assertEqual(manifest["handoffs"][0]["cache"][0],
                         {"source_port": 33, "destination_port": 28, "width": 32, "words": 16})
        self.assertEqual(manifest["handoffs"][1]["cache"][3]["words"], 18)

    def test_rejects_cache_width_depth_and_leaf_order_mutations(self):
        for mutation, expected in (("width", "width"), ("depth", "depth"), ("order", "leaf")):
            with self.subTest(mutation=mutation):
                abi, phases = fixture()
                if mutation == "width":
                    items = list(phases["decode-8"]["semantic"])
                    items[28] = SemanticMemory(28, (1, 1, 8, 2), 64)
                    phases["decode-8"]["semantic"] = tuple(items)
                elif mutation == "depth":
                    items = list(phases["decode-8"]["semantic"])
                    items[28] = SemanticMemory(28, (1, 1, 7, 2), 32)
                    phases["decode-8"]["semantic"] = tuple(items)
                else:
                    abi["phases"][0]["cache_leaves"][0]["leaf"] = 1
                with self.assertRaisesRegex(ValueError, expected):
                    build_handoff(abi, phases)

    def test_rejects_stale_namespaced_source_receipt(self):
        abi, phases = fixture()
        phases["decode-9"]["namespace_receipt"]["input_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "source hash"):
            build_handoff(abi, phases)

    def test_rejects_position_ids_as_token_input(self):
        abi, phases = fixture()
        phases["prefill-8"]["token_input_port"] = 0
        with self.assertRaisesRegex(ValueError, "token input"):
            build_handoff(abi, phases)

    def test_rejects_corrupted_initial_memory_image(self):
        abi, phases = fixture()
        phases["prefill-8"]["initial_memories"] = {
            "31": {"width": 64, "words": ["0000000000000001"],
                   "sha256": hashlib.sha256(bytes(8)).hexdigest()}
        }
        with self.assertRaisesRegex(ValueError, "initial memory.*hash"):
            build_handoff(abi, phases)

    def test_existing_phase_verifier_checks_token_not_position_port(self):
        abi, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {}
            for name, length in zip(PHASES, (8, 9, 10)):
                shapes = ["1xi8"] * 37
                shapes[0] = "8xi64" if name == "prefill-8" else "1xi64"
                shapes[31 if name == "prefill-8" else 27] = "1x8xi64" if name == "prefill-8" else "1x1xi64"
                if name != "prefill-8":
                    for leaf in range(4):
                        shapes[28 + leaf] = f"1x1x{length - 1}x2xf32"
                shapes[32] = "1x8x6xf32" if name == "prefill-8" else "1x1x6xf32"
                for leaf in range(4):
                    shapes[33 + leaf] = f"1x1x{length}x2xf32"
                source = "module { func.func @main(" + ", ".join(
                    f"%arg{number}: memref<{shape}>" for number, shape in enumerate(shapes)
                ) + ") { } }\n"
                path = root / f"{name}.mlir"
                path.write_text(source)
                paths[name] = path
            abi_path = root / "abi.json"
            abi_path.write_text(json.dumps(abi))
            self.assertEqual(verify(abi_path, paths)["status"], "pass")
            original = paths["prefill-8"].read_text()
            paths["prefill-8"].write_text(original.replace("%arg31: memref<1x8xi64>", "%arg31: memref<1x7xi64>"))
            with self.assertRaisesRegex(ValueError, "token input"):
                verify(abi_path, paths)


if __name__ == "__main__":
    unittest.main()
