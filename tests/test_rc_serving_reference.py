import hashlib
import unittest

import torch

from TinyStories import rc_serving_contract as contract
from TinyStories import rc_serving_evidence as evidence
from TinyStories import rc_serving_source as source


class RecordingModel:
    def __init__(self) -> None:
        self.calls = []

    def __call__(self, input_ids, **kwargs):
        self.calls.append((input_ids.clone(), kwargs))
        next_cache = [torch.tensor([len(self.calls)], dtype=torch.int64)]
        return (torch.zeros((1, input_ids.shape[1], 6)), next_cache)


class RcServingReferenceTest(unittest.TestCase):
    def test_native_call_uses_only_the_source_api_boundary(self) -> None:
        model = RecordingModel()
        phase = contract.phase_by_name("prefill-8")
        logits, returned_cache = source.run_native_call(
            model, phase, torch.zeros((1, 8), dtype=torch.long), None
        )

        self.assertEqual(tuple(logits.shape), (1, 8, 6))
        self.assertEqual(returned_cache[0].item(), 1)
        _, kwargs = model.calls[0]
        self.assertIsNone(kwargs["past_key_values"])
        self.assertTrue(kwargs["use_cache"])
        self.assertFalse(kwargs["return_dict"])
        self.assertTrue(torch.equal(kwargs["cache_position"], torch.arange(8)))
        self.assertTrue(
            torch.equal(kwargs["attention_mask"], torch.ones((1, 8), dtype=torch.long))
        )
        self.assertNotIn("position_ids", kwargs)

    def test_tensor_record_survives_later_in_place_mutation(self) -> None:
        value = torch.tensor([1, 2, 3], dtype=torch.int8)
        record = evidence.tensor_record(value)
        value[0] = 9
        self.assertEqual(record["little_endian_hex"], "010203")
        self.assertEqual(
            record["sha256"], hashlib.sha256(bytes([1, 2, 3])).hexdigest()
        )

    def test_reference_schema_requires_all_three_cache_lengths(self) -> None:
        trace = contract.ServingTrace(
            prompt_token_ids=(0, 1, 2, 3, 4, 5, 0, 1),
            phases=tuple(
                contract.phase_by_name(name)
                for name in ("prefill-8", "decode-8", "decode-9")
            ),
        )
        self.assertEqual(
            [phase.cache_length_after for phase in trace.phases], [8, 9, 10]
        )

    def test_decode8_invocation_preserves_the_c8_input_cache(self) -> None:
        model = RecordingModel()
        trace = contract.ServingTrace(
            prompt_token_ids=(0, 1, 2, 3, 4, 5, 0, 1),
            phases=tuple(
                contract.phase_by_name(name)
                for name in ("prefill-8", "decode-8", "decode-9")
            ),
        )
        invocation = source.fresh_phase_invocation(model, trace, "decode-8")
        self.assertEqual(invocation.past_key_values[0].item(), 1)


if __name__ == "__main__":
    unittest.main()
