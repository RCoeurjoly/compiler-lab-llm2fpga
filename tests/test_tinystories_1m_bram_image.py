"""Tests for synthesis-visible immutable BRAM image preparation."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/prepare_tinystories_1m_bram_image.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bram_image", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BramImageTest(unittest.TestCase):
    def test_staticizer_removes_runtime_plusarg_and_scratch_initialization(self):
        module = load_module()
        source = """string DATA;\nint CODE;\ninitial begin
    CODE = $value$plusargs(\"DATA=%s\", DATA);
    $display(\"DATA (path to meminit files): %s\", DATA);
    $readmemh({DATA, \"/token_weight_codes_i8.dat\"}, token_weight_codes_i8.mem);
    $readmemh({DATA, \"/context_tokens.dat\"}, context_tokens.mem);
end
final begin
    $writememh({DATA, \"/context_tokens.out\"}, context_tokens.mem);
end
logic clk;
"""
        result = module.staticize_sv(source, {"token_weight_codes_i8"})
        self.assertNotIn("$value$plusargs", result)
        self.assertNotIn("context_tokens.dat", result)
        self.assertNotIn("$writememh", result)
        self.assertNotIn("$onehot0", result)
        self.assertIn('$readmemh("image-token_weight_codes_i8.hex", token_weight_codes_i8.mem);', result)

    def test_script_is_scoped_to_static_image_and_not_bitstream_claims(self):
        source = SCRIPT.read_text()
        self.assertIn('tinystories-1m-bram-static-image-v1', source)
        self.assertIn('"bitstream_verified": False', source)
        self.assertIn('"synthesis_image_ready": True', source)

    def test_retained_receipt_is_explicitly_not_a_bitstream_claim(self):
        receipt = __import__("json").loads(
            (ROOT / "artifacts/reference/tinystories-1m-bram-static-image-receipt.json").read_text()
        )
        self.assertEqual(receipt["status"], "prepared_not_bitstream_verified")
        self.assertEqual(receipt["verification"]["static_readmemh_parse"], "passed")
        self.assertFalse(receipt["verification"]["bitstream_verified"])


if __name__ == "__main__":
    unittest.main()
