"""The software prompt uses the same authenticated input and exact model."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pipeline/prompt_tinystories_software.py"


def load_cli():
    spec = importlib.util.spec_from_file_location("software_prompt_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeTokenizer:
    def __init__(self, ids):
        self.ids = ids

    def encode(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return list(self.ids)

    def decode(self, ids, *, clean_up_tokenization_spaces, skip_special_tokens):
        assert clean_up_tokenization_spaces is False
        assert skip_special_tokens is False
        return "  a little story"


class SoftwarePromptTest(unittest.TestCase):
    def test_prompt_and_generated_ids_match_exact_reference(self):
        cli = load_cli()
        reference = {"prompt_ids": [7454, 2402, 257, 1110],
                     "tokens": list(range(100, 116)),
                     "tokenizer_sha256": cli.TOKENIZER_SHA256,
                     "model_sha256": "a" * 64, "model_identity": {"source": "exact"}}
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(cli, "load_tokenizer", return_value=FakeTokenizer(reference["prompt_ids"])), \
             patch.object(cli, "generate_software_reference", return_value=reference) as generate:
            receipt_path = Path(temp_dir) / "software.json"
            result = cli.run_prompt("Once upon a day", Path("/package"), Path("/snapshot"),
                                    receipt_path=receipt_path)
            stored = json.loads(receipt_path.read_text())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["tokens"], reference["tokens"])
        self.assertEqual(result["continuation_text"], "  a little story")
        self.assertEqual(result["token_check"], "exact_software_model")
        self.assertEqual(stored["receipt_sha256"], result["receipt_sha256"])
        generate.assert_called_once_with(reference["prompt_ids"], Path("/package"), Path("/snapshot"))

    def test_invalid_prompt_never_loads_model(self):
        cli = load_cli()
        with patch.object(cli, "load_tokenizer", return_value=FakeTokenizer([1, 2, 3])), \
             patch.object(cli, "generate_software_reference", side_effect=AssertionError("loaded model")):
            result = cli.run_prompt("bad", Path("/package"), Path("/snapshot"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("exactly four", result["error"])

    def test_main_prints_token_ids_and_text(self):
        cli = load_cli()
        output = io.StringIO()
        result = {"status": "passed", "prompt_ids": [1, 2, 3, 4],
                  "tokens": [5, 6], "continuation_text": " a story"}
        with patch.object(cli, "run_prompt", return_value=result), redirect_stdout(output):
            code = cli.main(["--prompt", "Once upon a day", "--package", "/package",
                             "--model-snapshot", "/snapshot"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(),
                         "Prompt IDs: 1 2 3 4\nGenerated IDs: 5 6\nContinuation:\n a story\n")

    def test_main_reports_missing_model_package(self):
        cli = load_cli()
        error = io.StringIO()
        with patch.dict(cli.os.environ, {"TINYSTORIES_1M_EXACT_PACKAGE": ""}, clear=False), \
             redirect_stderr(error):
            code = cli.main(["--prompt", "Once upon a day", "--model-snapshot", "/snapshot"])
        self.assertEqual(code, 1)
        self.assertIn("nix develop", error.getvalue())


if __name__ == "__main__":
    unittest.main()
