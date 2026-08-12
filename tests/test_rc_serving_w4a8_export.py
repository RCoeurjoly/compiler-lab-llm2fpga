import tempfile
import unittest
from pathlib import Path

import torch
from torch import nn

from TinyStories import rc_serving_w4a8_export as export


class _FakeExported:
    def __init__(self, tensors: dict[str, torch.Tensor]) -> None:
        self.state_dict = tensors
        self.constants: dict[str, torch.Tensor] = {}


class RcServingW4A8ExportTest(unittest.TestCase):
    def test_convert_w4a8_program_materializes_signed_int4_weight(self) -> None:
        class Linear(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.linear = nn.Linear(4, 2, bias=False)

            def forward(self, value: torch.Tensor) -> torch.Tensor:
                return self.linear(value)

        model = Linear().eval()
        example = (torch.tensor([[1.0, -1.0, 0.5, 0.25]]),)
        converted = export.convert_w4a8_program(model, example)
        weights = export.integer_weight_tensors(converted)
        self.assertTrue(weights)
        self.assertTrue(all(tensor.dtype == torch.int8 for tensor in weights.values()))
        self.assertTrue(all(int(tensor.min()) >= -8 for tensor in weights.values()))
        self.assertTrue(all(int(tensor.max()) <= 7 for tensor in weights.values()))

    def test_pack_signed_nibbles_uses_low_even_high_odd_order(self) -> None:
        values = torch.tensor([-8, -1, 0, 7, 3], dtype=torch.int8)
        self.assertEqual(export.pack_signed_nibbles(values), bytes([0xF8, 0x70, 0x03]))

    def test_pack_signed_nibbles_rejects_out_of_range_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "signed W4"):
            export.pack_signed_nibbles(torch.tensor([-9, 0], dtype=torch.int8))

    def test_records_deduplicate_identical_weights_across_phases(self) -> None:
        weight = torch.tensor([[-8, -1], [0, 7]], dtype=torch.int8)
        phases = {
            "prefill-8": _FakeExported({"linear_weight": weight}),
            "decode-8": _FakeExported({"linear_weight": weight.clone()}),
            "decode-9": _FakeExported({"linear_weight": weight.clone()}),
        }
        records, image = export.quantized_tensor_records(phases)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].phases, ("prefill-8", "decode-8", "decode-9"))
        self.assertEqual(records[0].shape, (2, 2))
        self.assertEqual(image, bytes([0xF8, 0x70]))

    def test_records_ignore_non_integer_state_but_require_a_weight(self) -> None:
        phases = {
            name: _FakeExported({"scale": torch.tensor(0.25)})
            for name in ("prefill-8", "decode-8", "decode-9")
        }
        with self.assertRaisesRegex(ValueError, "no signed W4 weight"):
            export.quantized_tensor_records(phases)

    def test_write_frozen_files_is_byte_deterministic(self) -> None:
        weight = torch.tensor([-8, -1, 0, 7], dtype=torch.int8)
        phases = {
            name: _FakeExported({"linear_weight": weight.clone()})
            for name in ("prefill-8", "decode-8", "decode-9")
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            export.write_frozen_tensor_bundle(phases, first)
            export.write_frozen_tensor_bundle(phases, second)
            self.assertEqual(
                (first / "manifest.json").read_bytes(),
                (second / "manifest.json").read_bytes(),
            )
            self.assertEqual(
                (first / "weights.bin").read_bytes(),
                (second / "weights.bin").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
