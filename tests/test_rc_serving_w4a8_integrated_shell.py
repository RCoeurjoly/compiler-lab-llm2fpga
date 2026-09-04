import unittest

from scripts.pipeline.generate_rc_serving_w4a8_integrated_shell import (
    MemoryPort,
    build_readback_bindings,
    render_public_shell,
)


class IntegratedShellTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ports = tuple(
            MemoryPort(i, 64 if i in (3, 4, 5, 6) else 32, 8)
            for i in range(22)
        )
        words = []
        address = 0
        for phase in ("prefill-8", "decode-8", "decode-9"):
            words.append({"address": address, "phase": phase, "kind": "token", "flat_index": 0, "width": 64})
            address += 1
            for kind, count in (("logits", 1), ("cache", 4)):
                for leaf in range(count):
                    words.append({"address": address, "phase": phase, "kind": kind, "leaf": leaf if kind == "cache" else None, "flat_index": 0, "width": 32})
                    address += 1
        self.manifest = {"address_count": address, "words": words}

    def test_bindings_follow_integrated_output_order(self) -> None:
        bindings = build_readback_bindings(self.manifest, tuple(range(4, 22)))
        self.assertEqual(bindings[0].memory, 4)
        self.assertEqual(bindings[1].memory, 7)
        self.assertEqual(bindings[6].memory, 5)
        self.assertEqual(bindings[12].memory, 6)

    def test_shell_has_narrow_transaction_and_readback_ports(self) -> None:
        source = render_public_shell(
            self.manifest, self.ports, prompt_port=3, output_ports=tuple(range(4, 22))
        )
        for name in (
            "prompt_index", "prompt_data", "prompt_write", "go", "busy", "done",
            "protocol_error", "readback_address", "readback_request",
            "readback_response_valid", "readback_response_data",
        ):
            self.assertIn(name, source)
        self.assertIn("main_1 generated", source)
        self.assertIn("prompt_written[prompt_index]", source)
        self.assertIn("if (busy || prompt_written != 8'hff)", source)
        self.assertIn("readback_address >= 18", source)
        self.assertNotIn("argmax", source.lower())
        self.assertNotIn("phase scheduling", source.lower())

    def test_rejects_duplicate_or_missing_readback_words(self) -> None:
        broken = dict(self.manifest)
        broken["words"] = list(self.manifest["words"][:-1])
        with self.assertRaisesRegex(ValueError, "dense"):
            build_readback_bindings(broken, tuple(range(4, 22)))


if __name__ == "__main__":
    unittest.main()
