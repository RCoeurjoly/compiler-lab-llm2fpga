import json
import os
import tempfile
import unittest
from pathlib import Path

import torch
from transformers import DynamicCache

from TinyStories.rc_serving_w4a8_cache_abi import flatten_dynamic_cache
from TinyStories.rc_serving_contract import load_trace
from TinyStories.rc_serving_evidence import run_native_trace, tensor_record
from TinyStories.rc_serving_w4a8_integrated import (
    IntegratedW4A8Module,
    assert_integrated_observation_equal,
    convert_integrated_w4a8_program,
    materialize_integrated_bundle,
    native_cache_records_in_tensor_abi_order,
    run_integrated_eager,
)
from TinyStories.rc_serving_w4a8_source import build_w4a8_source_model


class RecordingModel(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.seen_tokens: list[tuple[int, ...]] = []
        self.seen_cache_lengths: list[int | None] = []

    def forward(self, input_ids, past_key_values, **kwargs):
        self.seen_tokens.append(tuple(int(value) for value in input_ids.reshape(-1)))
        if past_key_values is None:
            before = 0
            self.seen_cache_lengths.append(None)
        else:
            before = int(
                flatten_dynamic_cache(past_key_values, expected_layers=2)[0].shape[2]
            )
            self.seen_cache_lengths.append(before)
        after = before + int(input_ids.shape[1])
        leaves = tuple(
            torch.full((1, 1, after, 2), after * 10 + leaf, dtype=torch.float32)
            for leaf in range(4)
        )
        cache = DynamicCache.from_legacy_cache(
            ((leaves[0], leaves[1]), (leaves[2], leaves[3]))
        )

        logits = torch.zeros((1, input_ids.shape[1], 6), dtype=torch.float32)
        selected = {0: (1, 3), 8: (2, 4), 9: (0, 5)}[before]
        logits[0, -1, selected[0]] = 7.0
        logits[0, -1, selected[1]] = 7.0
        return logits, cache


class ExportableIntegratedFixture(torch.nn.Module):
    def forward(self, prompt):
        scalar = prompt.to(torch.float32).sum()
        logits = scalar.expand(1, 6)
        tokens = tuple(torch.argmax(logits, dim=-1, keepdim=True) for _ in range(3))
        outputs = list(tokens)
        for length in (8, 9, 10):
            outputs.append(logits)
            outputs.extend(
                (scalar + leaf).expand(1, 1, length, 2)
                for leaf in range(4)
            )
        return tuple(outputs)


class RcServingW4A8IntegratedTest(unittest.TestCase):
    def test_integrated_materializer_cli_has_one_program_contract(self) -> None:
        source = Path(
            "scripts/pipeline/materialize_rc_serving_w4a8_integrated.py"
        ).read_text(encoding="utf-8")
        self.assertIn("materialize_integrated_bundle", source)
        self.assertIn("--phase-oracle", source)
        self.assertNotIn("for phase", source)

    def test_integrated_conversion_saves_one_reloadable_program(self) -> None:
        prompt = torch.tensor([[0, 1, 2, 3, 4, 5, 0, 1]], dtype=torch.long)
        converted = convert_integrated_w4a8_program(
            ExportableIntegratedFixture(), prompt
        )
        expected = converted.module()(prompt)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "exported.pt2"
            torch.export.save(converted, path)
            self.assertEqual(list(Path(temporary).glob("*.pt2")), [path])
            reloaded = torch.export.load(path)
            actual = reloaded.module()(prompt)

        self.assertEqual(len(expected), 18)
        self.assertEqual(len(actual), 18)
        self.assertTrue(
            all(torch.equal(before, after) for before, after in zip(expected, actual))
        )

    def test_native_cache_records_are_reordered_by_semantic_path(self) -> None:
        leaves = [
            {"path": "['key_cache']/[0]", "tensor": "K0"},
            {"path": "['key_cache']/[1]", "tensor": "K1"},
            {"path": "['value_cache']/[0]", "tensor": "V0"},
            {"path": "['value_cache']/[1]", "tensor": "V1"},
        ]

        self.assertEqual(
            native_cache_records_in_tensor_abi_order(leaves),
            ["K0", "V0", "K1", "V1"],
        )

    def test_forward_uses_lowest_argmax_token_feedback(self) -> None:
        model = RecordingModel()
        module = IntegratedW4A8Module(model)
        prompt = torch.tensor([[0, 1, 2, 3, 4, 5, 0, 1]], dtype=torch.long)

        flat = module(prompt)

        self.assertEqual(tuple(int(token.item()) for token in flat[:3]), (1, 2, 0))
        self.assertEqual(
            model.seen_tokens,
            [(0, 1, 2, 3, 4, 5, 0, 1), (1,), (2,)],
        )
        self.assertEqual(len(flat), 18)

    def test_forward_passes_returned_cache_to_the_next_call(self) -> None:
        model = RecordingModel()
        module = IntegratedW4A8Module(model)

        flat = module(torch.tensor([[0, 1, 2, 3, 4, 5, 0, 1]], dtype=torch.long))

        self.assertEqual(model.seen_cache_lengths, [None, 8, 9])
        self.assertEqual([tuple(tensor.shape) for tensor in flat[4:8]], [(1, 1, 8, 2)] * 4)
        self.assertEqual([tuple(tensor.shape) for tensor in flat[9:13]], [(1, 1, 9, 2)] * 4)
        self.assertEqual([tuple(tensor.shape) for tensor in flat[14:18]], [(1, 1, 10, 2)] * 4)

    def test_run_integrated_eager_builds_the_contract_observation(self) -> None:
        module = IntegratedW4A8Module(RecordingModel())
        prompt = torch.tensor([[0, 1, 2, 3, 4, 5, 0, 1]], dtype=torch.long)

        observation = run_integrated_eager(module, prompt)

        self.assertEqual(observation.prompt_token_ids, (0, 1, 2, 3, 4, 5, 0, 1))
        self.assertEqual(observation.phase_tokens, (1, 2, 0))
        self.assertEqual(tuple(len(values) for values in observation.phase_logits), (6, 6, 6))
        self.assertEqual(tuple(len(leaves) for leaves in observation.phase_cache_leaves), (4, 4, 4))

    def test_observation_comparison_names_first_mismatch(self) -> None:
        module = IntegratedW4A8Module(RecordingModel())
        prompt = torch.tensor([[0, 1, 2, 3, 4, 5, 0, 1]], dtype=torch.long)
        expected = run_integrated_eager(module, prompt)
        actual = run_integrated_eager(IntegratedW4A8Module(RecordingModel()), prompt)
        actual.phase_cache_leaves[1][2].reshape(-1)[3] += 1

        with self.assertRaisesRegex(
            AssertionError, "decode-8 cache leaf 2.*flat index 3"
        ):
            assert_integrated_observation_equal(expected, actual)

    @unittest.skipUnless(
        os.environ.get("TINYSTORIES_MODEL_PATH"),
        "set TINYSTORIES_MODEL_PATH for the pinned real-model gate",
    )
    def test_integrated_eager_matches_ordered_native_reference(self) -> None:
        model_path = Path(os.environ["TINYSTORIES_MODEL_PATH"])
        trace = load_trace(Path("TinyStories/rc_serving_trace_input.json"))
        prompt = torch.tensor([trace.prompt_token_ids], dtype=torch.long)
        observation = run_integrated_eager(
            IntegratedW4A8Module(build_w4a8_source_model(model_path)), prompt
        )
        reference = run_native_trace(build_w4a8_source_model(model_path), trace)

        self.assertEqual(
            tuple(reference["trace"]["prompt_token_ids"]),
            tuple(observation.prompt_token_ids),
        )
        for phase_index, phase in enumerate(reference["phases"]):
            self.assertEqual(phase["greedy_token_id"], observation.phase_tokens[phase_index])
            self.assertEqual(
                phase["last_logits"],
                tensor_record(
                    torch.tensor(observation.phase_logits[phase_index], dtype=torch.float32)
                ),
            )
            self.assertEqual(
                native_cache_records_in_tensor_abi_order(
                    phase["cache_snapshot"]["leaves"]
                ),
                [
                    tensor_record(tensor)
                    for tensor in observation.phase_cache_leaves[phase_index]
                ],
            )

    @unittest.skipUnless(
        os.environ.get("TINYSTORIES_MODEL_PATH")
        and os.environ.get("W4A8_PHASE_ORACLE"),
        "set pinned model and phase-oracle paths for the real export gate",
    )
    def test_real_integrated_bundle_freezes_one_chained_program(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            out_dir = Path(temporary) / "bundle"
            materialize_integrated_bundle(
                Path(os.environ["TINYSTORIES_MODEL_PATH"]),
                Path("TinyStories/rc_serving_trace_input.json"),
                Path(os.environ["W4A8_PHASE_ORACLE"]),
                out_dir,
            )
            files = sorted(path.name for path in out_dir.iterdir())
            receipt = json.loads((out_dir / "receipt.json").read_text())

        self.assertEqual(
            files,
            [
                "exported.pt2",
                "graph.txt",
                "observation.json",
                "readback-manifest.json",
                "receipt.json",
            ],
        )
        self.assertEqual(receipt["exported_program_count"], 1)
        self.assertEqual(receipt["quantized_decomposed_node_count"], 489)
        self.assertTrue(receipt["frozen_phase_qparams_equal"])
        self.assertTrue(receipt["frozen_prefill_equal"])
        self.assertTrue(receipt["save_reload_equal"])


if __name__ == "__main__":
    unittest.main()
