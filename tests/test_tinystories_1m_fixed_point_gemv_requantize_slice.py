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


if __name__ == "__main__":
    unittest.main()
