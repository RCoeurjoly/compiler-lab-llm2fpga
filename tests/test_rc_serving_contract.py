import unittest
from pathlib import Path

from TinyStories import rc_serving_contract as contract


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "TinyStories" / "rc_serving_trace_input.json"


class RcServingContractTest(unittest.TestCase):
    def test_profile_and_trace_are_fixed(self) -> None:
        trace = contract.load_trace(TRACE)
        self.assertEqual(
            contract.SERVING_RC_MODEL_KEY,
            "tinystories-w8a8-rc-serving-mask10-vocab6-width2",
        )
        self.assertEqual(
            (
                contract.VOCAB_SIZE,
                contract.NUM_LAYERS,
                contract.HIDDEN_SIZE,
                contract.NUM_HEADS,
                contract.MAX_POSITION_EMBEDDINGS,
                contract.WINDOW_SIZE,
            ),
            (6, 2, 2, 1, 10, 256),
        )
        self.assertEqual(trace.prompt_token_ids, (0, 1, 2, 3, 4, 5, 0, 1))
        self.assertEqual(
            [
                (
                    phase.name,
                    phase.input_length,
                    phase.cache_length_before,
                    phase.cache_length_after,
                    phase.cache_positions,
                )
                for phase in trace.phases
            ],
            [
                ("prefill-8", 8, 0, 8, (0, 1, 2, 3, 4, 5, 6, 7)),
                ("decode-8", 1, 8, 9, (8,)),
                ("decode-9", 1, 9, 10, (9,)),
            ],
        )

    def test_token_validation_and_ties_are_deterministic(self) -> None:
        self.assertEqual(
            contract.argmax_lowest([-2.0, 1.0, 1.0, 0.0, -3.0, 0.5]), 1
        )
        self.assertEqual(contract.validate_token_ids([0, 5], 2), (0, 5))
        with self.assertRaisesRegex(ValueError, "expected exactly 8"):
            contract.validate_token_ids([0] * 7, 8)
        with self.assertRaisesRegex(ValueError, "range"):
            contract.validate_token_ids([0, 1, 2, 3, 4, 5, 0, 6], 8)

    def test_old_stateless_rc_is_not_retargeted(self) -> None:
        old_adapter = (
            ROOT
            / "TinyStories"
            / "model_adapter_quantized_representative_core_pt2e_w8a8.py"
        ).read_text(encoding="utf-8")
        old_contract = (
            ROOT / "TinyStories" / "rc_working_contract.py"
        ).read_text(encoding="utf-8")
        self.assertIn("config.use_cache = False", old_adapter)
        self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", old_contract)
        self.assertNotIn(contract.SERVING_RC_MODEL_KEY, old_adapter)
        self.assertNotIn(contract.SERVING_RC_MODEL_KEY, old_contract)


if __name__ == "__main__":
    unittest.main()
