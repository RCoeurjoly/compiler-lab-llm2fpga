"""Acceptance comparison must bind board, software, tokenizer, and image evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline/compare_tinystories_short_prompts.py"
PROMPT = [7454, 2402, 257, 1110]
TOKENS = list(range(100, 116))
TOKENIZER_HASH = "f6ed3d307010c244c22aeffbde05f419cf277c23e64cf98b673cac5449cfeff5"


def load_comparison():
    spec = importlib.util.spec_from_file_location("short_prompt_comparison", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def self_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / "model.bit"
        self.image.write_bytes(b"accepted image bytes")
        self.log = self.root / "program.log"
        self.log.write_text("Load SRAM: 100.00%\nDone\n", encoding="utf-8")
        self.image_sha = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.log_sha = hashlib.sha256(self.log.read_bytes()).hexdigest()
        self.board = {
            "schema": "tinystories-short-prompt-jtag-v1", "status": "passed",
            "token_check": "none", "prompt_ids": PROMPT, "tokens": TOKENS,
            "tokenizer_sha256": TOKENIZER_HASH, "transport_serial": "HS3",
            "transactions": [{"command": "2000000000000000", "captured": "2800000000001d1e"}],
        }
        self.board["receipt_sha256"] = self_hash(self.board)
        self.reference = {
            "prompt_ids": PROMPT, "tokens": TOKENS,
            "tokenizer_sha256": TOKENIZER_HASH, "model_sha256": "a" * 64,
        }
        self.program = {
            "returncode": 0, "image_sha256": self.image_sha,
            "log_sha256": self.log_sha, "serial": "HS3",
            "command": ["openFPGALoader", "-m", str(self.image)],
        }

    def compare(self):
        module = load_comparison()
        return module.compare_receipts(
            self.board, self.reference, self.program, self.image, self.log,
            accepted_image_sha256=self.image_sha,
        )

    def test_exact_sixteen_token_match_is_bound_to_programming_log(self):
        result = self.compare()
        self.assertEqual(result["status"], "passed")
        self.assertIsNone(result["first_mismatch"])
        self.assertEqual(result["board_tokens"], TOKENS)
        self.assertEqual(result["software_tokens"], TOKENS)
        self.assertEqual(result["bitstream_sha256"], self.image_sha)
        self.assertEqual(result["program_log_sha256"], self.log_sha)

    def test_first_token_divergence_is_reported_without_equivalence_claim(self):
        self.reference["tokens"] = TOKENS[:5] + [999] + TOKENS[6:]
        result = self.compare()
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["first_mismatch"], 5)

    def test_prompt_identity_mismatch_is_rejected(self):
        self.reference["prompt_ids"] = [7454, 2402, 257, 640]
        with self.assertRaisesRegex(ValueError, "prompt IDs"):
            self.compare()

    def test_tokenizer_identity_mismatch_is_rejected(self):
        self.reference["tokenizer_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "tokenizer"):
            self.compare()

    def test_wrong_image_or_program_log_is_rejected(self):
        self.program["image_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "image"):
            self.compare()
        self.program["image_sha256"] = self.image_sha
        self.log.write_text("different log", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "program log"):
            self.compare()

    def test_truncated_programming_command_is_rejected_cleanly(self):
        self.program["command"] = ["openFPGALoader", "-m"]
        with self.assertRaisesRegex(ValueError, "programming command"):
            self.compare()

    def test_transport_only_receipt_needs_software_and_programming_evidence(self):
        module = load_comparison()
        with self.assertRaisesRegex(ValueError, "software reference"):
            module.compare_receipts(self.board, None, self.program, self.image, self.log,
                                    accepted_image_sha256=self.image_sha)
        with self.assertRaisesRegex(ValueError, "programming"):
            module.compare_receipts(self.board, self.reference, None, self.image, self.log,
                                    accepted_image_sha256=self.image_sha)


if __name__ == "__main__":
    unittest.main()
