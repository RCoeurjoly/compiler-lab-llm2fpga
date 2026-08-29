from __future__ import annotations

import unittest
import torch
from pathlib import Path

from TinyStories import model_adapter_reference_package as package_adapter
from TinyStories.fixed_qk_trace import (
    FixedQKBlockZeroTokenStepTrace,
    FixedQKProjection,
    build_probe_metadata,
    export_block0_fixed_qk_trace,
    fixed_qdq,
    qk_scales_q24_from_boundaries,
)
from scripts.comparison.probe_tinystories_1m_qk_qdq import build_probe


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
PROFILE = ROOT / "artifacts/reference/tinystories-1m-fixed-hardware-qdq-profile.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/"
    "models--roneneldan--TinyStories-1M/snapshots/"
    "77f1b168e219585646439073245fe87e56b3023e"
)


class FixedQKTraceExportTest(unittest.TestCase):
    def test_direct_qdq_rejects_invalid_scales(self):
        value = torch.zeros((1, 1))
        for scale in (0, -1, 1 << 24):
            with self.subTest(scale=scale), self.assertRaisesRegex(ValueError, "positive unsigned"):
                fixed_qdq(value, torch.tensor([scale], dtype=torch.int64))

    def test_qdq_has_explicit_saturation_and_roundtrip(self):
        codes, fixed = fixed_qdq(torch.tensor([[0.0, 1.0, -1.0, 0.001]]), torch.tensor([1 << 16] * 4, dtype=torch.int64))
        self.assertEqual(tuple(codes.shape), (1, 4))
        self.assertEqual(codes[0, 1].item(), 127)
        self.assertEqual(codes[0, 2].item(), -128)
        self.assertTrue(torch.isfinite(fixed).all())

    def test_dequantization_matches_integer_half_away_rule(self):
        scale = 16775217
        q16 = -(127 * scale // 256)
        _, fixed = fixed_qdq(torch.tensor([[q16 / 65536.0]]), torch.tensor([scale], dtype=torch.int64))
        self.assertEqual(fixed.item(), -8322080)

    def test_projection_exports_and_replays(self):
        q = torch.nn.Linear(4, 4, bias=False)
        k = torch.nn.Linear(4, 4, bias=False)
        module = FixedQKProjection(q, k, [1 << 16] * 4, [1 << 16] * 4).eval()
        hidden = torch.tensor([[0.1, -0.2, 0.3, -0.4]])
        eager = module(hidden)
        exported = torch.export.export(module, (hidden,), strict=False)
        replay = exported.module()(hidden)
        for a, b in zip(eager, replay, strict=True):
            self.assertTrue(torch.equal(a, b))
        self.assertEqual(tuple(replay[0].shape), (1, 4))
        self.assertEqual(replay[0].dtype, torch.int8)

    @unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "authenticated package/model unavailable")
    def test_authenticated_block0_trace_exports_replays_and_places_qk_qdq_before_scores(self):
        bundle = package_adapter.load_authenticated_package(CONTRACT, PACKAGE, MODEL)
        prompt = torch.tensor([bundle.contract["reference"]["prompt_tokens"]], dtype=torch.long)
        q_scales, k_scales = qk_scales_q24_from_boundaries(bundle.receipt["activation_qdq_boundaries"])
        module = FixedQKBlockZeroTokenStepTrace(bundle.model, q_scales, k_scales).eval()

        with torch.no_grad():
            eager = module(prompt)
            exported = export_block0_fixed_qk_trace(module, prompt)
            replay = exported.module()(prompt)

        self.assertEqual(module.checkpoint_names[2:6], (
            "block.attention.q.int8",
            "block.attention.q.dequant_q16_16",
            "block.attention.k.int8",
            "block.attention.k.dequant_q16_16",
        ))
        for expected, actual in zip(eager, replay, strict=True):
            self.assertTrue(torch.equal(expected, actual))
        self.assertEqual(tuple(replay[2].shape), (16, 4))
        self.assertEqual(tuple(replay[3].shape), (16, 4))
        self.assertEqual(tuple(replay[4].shape), (16, 4))
        self.assertEqual(tuple(replay[5].shape), (16, 4))
        self.assertEqual(replay[2].dtype, torch.int8)
        self.assertEqual(replay[3].dtype, torch.int64)
        self.assertEqual(replay[4].dtype, torch.int8)
        self.assertEqual(replay[5].dtype, torch.int64)
        probe = build_probe(CONTRACT, PACKAGE, MODEL, PROFILE)
        self.assertEqual(replay[2].tolist(), probe["q"]["int8"])
        self.assertEqual(replay[3].tolist(), probe["q"]["q16_16_roundtrip"])
        self.assertEqual(replay[4].tolist(), probe["k"]["int8"])
        self.assertEqual(replay[5].tolist(), probe["k"]["q16_16_roundtrip"])

        targets = [
            str(node.target)
            for node in exported.graph_module.graph.nodes
            if node.op == "call_function"
        ]
        first_matmul = targets.index("aten.matmul.default")
        qdq_prefix = targets[:first_matmul]
        self.assertGreaterEqual(qdq_prefix.count("aten.clamp.default"), 2)
        self.assertGreaterEqual(qdq_prefix.count("aten.floor_divide.default"), 6)
        self.assertIn("aten.ceil.default", qdq_prefix)
        self.assertIn("aten.floor.default", qdq_prefix)

        metadata = build_probe_metadata(bundle, PROFILE, module)
        self.assertEqual(metadata["status"], "probe_boundary_only")
        self.assertEqual(metadata["claims"], {
            "compiler_equivalence": False,
            "rtl_equivalence": False,
            "hardware_inference": False,
            "full_block_semantics": False,
        })
        self.assertEqual(metadata["qk_boundaries"], {
            "q": "transformer.h.0.attn.attention.q_proj.output",
            "k": "transformer.h.0.attn.attention.k_proj.output",
        })
        self.assertEqual(metadata["checkpoints"]["block.attention.q.int8"], {
            "shape": [16, 4],
            "dtype": "torch.int8",
            "scale": "per-head/per-channel q8.24",
        })


if __name__ == "__main__":
    unittest.main()
