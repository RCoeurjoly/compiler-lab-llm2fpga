from __future__ import annotations

import importlib.util
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/probe_tinystories_1m_qk_qdq.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tinystories_qk_probe", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QkProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_q16_conversion_is_deterministic(self):
        self.assertEqual(self.module._q16([0.0, 1.5, -2.25]), [0, 98304, -147456])

    def test_scale_projection_requires_exact_width(self):
        with self.assertRaisesRegex(ValueError, "activation_scale_width_mismatch"):
            self.module._scales_q24({"scales": [1.0]})

    def test_head_scale_slice_uses_four_channel_window_per_head(self):
        scales = list(range(64))
        self.assertEqual(self.module._head_scale_slice(scales, 0), [0, 1, 2, 3])
        self.assertEqual(self.module._head_scale_slice(scales, 15), [60, 61, 62, 63])
        with self.assertRaisesRegex(ValueError, "head_index_out_of_range"):
            self.module._head_scale_slice(scales, 16)

    def test_probe_schema_is_explicitly_not_equivalence(self):
        self.assertEqual(self.module.SCHEMA, "tinystories-1m-compiler-qk-qdq-probe-v1")

    def test_build_probe_uses_per_head_scale_slices_for_all_heads(self):
        q_float = [[(head * 4 + lane + 1) / 65536.0 for lane in range(4)] for head in range(16)]
        k_float = [[-((head * 4 + lane + 1) / 65536.0) for lane in range(4)] for head in range(16)]
        q_boundary = [float(index + 1) / (1 << 24) for index in range(64)]
        k_boundary = [float(index + 65) / (1 << 24) for index in range(64)]
        bundle = SimpleNamespace(
            contract={"reference": {"prompt_tokens": [7454, 2402, 257, 640]}},
            receipt={
                "identity": {
                    "contract_sha256": "c" * 64,
                    "package": {"manifest_sha256": "p" * 64},
                },
                "activation_qdq_boundaries": {
                    "transformer.h.0.attn.attention.q_proj.output": {"scales": q_boundary},
                    "transformer.h.0.attn.attention.k_proj.output": {"scales": k_boundary},
                },
            },
        )
        trace = {
            "status": "matched",
            "trace_sha256": "t" * 64,
            "checkpoints": {
                "block.attention.q": {"package_reconstruction": q_float},
                "block.attention.k": {"package_reconstruction": k_float},
            },
        }
        with (
            mock.patch.object(self.module, "load_fixed_hardware_profile", return_value={"profile_sha256": "f" * 64}),
            mock.patch.object(self.module.adapter, "load_authenticated_package", return_value=bundle),
            mock.patch.object(self.module.adapter, "build_numeric_trace_gate", return_value=trace),
        ):
            probe = self.module.build_probe(
                Path("contract.json"),
                Path("package"),
                Path("model"),
                Path("profile.json"),
            )

        self.assertEqual(probe["status"], "compiler_qk_qdq_probe")
        self.assertFalse(any(probe["claims"].values()))
        self.assertEqual(probe["identity"]["token_index"], 3)
        self.assertEqual(probe["q"]["shape"], [16, 4])
        self.assertEqual(probe["k"]["shape"], [16, 4])
        for head in range(16):
            start = head * 4
            expected_q_roundtrip = []
            expected_k_codes = []
            expected_k_roundtrip = []
            for lane in range(4):
                value = start + lane + 1
                expected_q_roundtrip.append((127 * value + 128) // 256)
                scale = start + lane + 65
                code = -((value * 256 + scale // 2) // scale)
                expected_k_codes.append(max(-128, code))
                expected_k_roundtrip.append(-((abs(expected_k_codes[-1] * scale) + 128) // 256))
            self.assertEqual(probe["q"]["scales_q8_24"][head], list(range(start + 1, start + 5)))
            self.assertEqual(probe["k"]["scales_q8_24"][head], list(range(start + 65, start + 69)))
            self.assertEqual(probe["q"]["q16_16"][head], [start + lane + 1 for lane in range(4)])
            self.assertEqual(probe["k"]["q16_16"][head], [-(start + lane + 1) for lane in range(4)])
            self.assertEqual(probe["q"]["int8"][head], [127, 127, 127, 127])
            self.assertEqual(probe["k"]["int8"][head], expected_k_codes)
            self.assertEqual(probe["q"]["q16_16_roundtrip"][head], expected_q_roundtrip)
            self.assertEqual(probe["k"]["q16_16_roundtrip"][head], expected_k_roundtrip)
        self.assertEqual(probe["sha256"], self.module._sha({key: value for key, value in probe.items() if key != "sha256"}))


if __name__ == "__main__":
    unittest.main()
