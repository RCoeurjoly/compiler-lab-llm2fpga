from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "artifacts/reference/tinystories-1m-fixed-point-gemv-requantize-slice.json"
CAPTURE = ROOT / "TinyStories/capture_fixed_point_gemv_requantize_slice.py"


def load_capture():
    spec = importlib.util.spec_from_file_location("fixed_point_slice_capture", CAPTURE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixedPointGemvRequantizeSliceTest(unittest.TestCase):
    def test_frozen_prompt_fixture_is_self_hashed_and_replayable(self):
        self.assertTrue(FIXTURE.is_file(), "missing named frozen-prompt fixture")
        capture = load_capture()
        capture.verify_fixture(FIXTURE)
        capture.verify_eager_replay(FIXTURE)

    def test_fixture_has_independent_gemv_requantization_replay_inputs(self):
        capture = load_capture()
        value = capture.verify_fixture(FIXTURE)
        self.assertTrue({"activation_codes_i8", "input_scale_q8_24", "output_scale_q8_24", "weight_codes_i8", "weight_scale_q8_24"} <= set(value["tensors"]))
        capture.verify_fixed_point_replay(FIXTURE)


if __name__ == "__main__":
    unittest.main()
