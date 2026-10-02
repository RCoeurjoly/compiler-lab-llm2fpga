"""Short text prompt behavior at the tokenizer and USER1 boundaries."""
from contextlib import nullcontext, redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.test_tinystories_generation_jtag import GenerationDevice


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline/prompt_tinystories_generation_jtag.py"


def load_cli():
    spec = importlib.util.spec_from_file_location("short_prompt_cli", SCRIPT)
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
        return "  made  a story"


class CloseableDevice(GenerationDevice):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.closed = False

    def close(self):
        self.closed = True


class JtagOps:
    @staticmethod
    def clock_tms(*_):
        return None

    @staticmethod
    def reset_tap(device):
        device.reset(device)

    @staticmethod
    def shift_ir(*_):
        return None


class ShortPromptTokenizerTest(unittest.TestCase):
    def test_clone_contains_authenticated_runtime_inputs(self):
        cli = load_cli()
        self.assertTrue(cli.DEFAULT_TOKENIZER_DIR.is_dir())
        self.assertTrue(cli.DEFAULT_TRANSPORT_DIR.is_dir())
        self.assertTrue(cli.DEFAULT_IMAGE.is_file())
        cli.verify_bundled_runtime()

    def test_frozen_text_yields_four_authenticated_ids(self):
        cli = load_cli()
        self.assertEqual(cli.encode_prompt("Once upon a time", FakeTokenizer([7454, 2402, 257, 640])),
                         [7454, 2402, 257, 640])

    def test_three_and_five_ids_are_rejected_without_truncation(self):
        cli = load_cli()
        for ids in ([1, 2, 3], [1, 2, 3, 4, 5]):
            with self.subTest(ids=ids), self.assertRaisesRegex(ValueError, "exactly four"):
                cli.encode_prompt("any text", FakeTokenizer(ids))

    def test_changed_tokenizer_bytes_fail_before_library_load(self):
        cli = load_cli()
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "tokenizer.json").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tokenizer SHA-256 mismatch"):
                cli.load_tokenizer(Path(temp_dir))


class ShortPromptRunTest(unittest.TestCase):
    def test_programming_records_accepted_image_and_log(self):
        cli = load_cli()
        commands = []

        def fake_run(command, *, stdout, stderr, timeout, check):
            commands.append(command)
            stdout.write("Done\n")
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(cli.shutil, "which", return_value="/pinned/openFPGALoader"), \
             patch.object(cli.subprocess, "run", side_effect=fake_run):
            log = Path(temp_dir) / "program.log"
            result = cli.program_board(cli.DEFAULT_IMAGE, "HS3", log)
            self.assertEqual(result["log_sha256"], cli._sha256_file(log))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["image_sha256"], cli.ACCEPTED_IMAGE_SHA256)
        self.assertEqual(commands[0][-1], str(cli.DEFAULT_IMAGE))
        self.assertIn("--ftdi-serial", commands[0])

    def test_programming_rejects_altered_image_before_loader(self):
        cli = load_cli()
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "model.bit"
            image.write_bytes(b"wrong image")
            with patch.object(cli.shutil, "which", side_effect=AssertionError("looked up loader")):
                with self.assertRaisesRegex(ValueError, "bitstream SHA-256 mismatch"):
                    cli.program_board(image, "HS3", Path(temp_dir) / "program.log")

    def test_program_option_checks_prompt_before_programming(self):
        cli = load_cli()
        with patch.object(cli, "load_tokenizer", return_value=FakeTokenizer([1, 2, 3])), \
             patch.object(cli, "program_board", side_effect=AssertionError("programmed board")), \
             patch.object(cli, "open_transport", side_effect=AssertionError("opened board")):
            result = cli.run_prompt("too short", cli.DEFAULT_TOKENIZER_DIR,
                                    cli.DEFAULT_TRANSPORT_DIR, "HS3", 1.0,
                                    program=True)
        self.assertEqual(result["status"], "failed")
        self.assertIn("exactly four", result["error"])

    def test_program_option_binds_programming_receipt(self):
        cli = load_cli()
        device = CloseableDevice(tokens=tuple(range(100, 116)))
        programming = {"status": "passed", "image_sha256": cli.ACCEPTED_IMAGE_SHA256,
                       "log_sha256": "a" * 64, "serial": "HS3"}
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(cli, "load_tokenizer", return_value=FakeTokenizer([1, 2, 3, 4])), \
             patch.object(cli, "program_board", return_value=programming) as program, \
             patch.object(cli, "open_transport", return_value=(device, JtagOps)):
            receipt = Path(temp_dir) / "run.json"
            result = cli.run_prompt("good", cli.DEFAULT_TOKENIZER_DIR,
                                    cli.DEFAULT_TRANSPORT_DIR, "HS3", 1.0,
                                    receipt, program=True)
            self.assertEqual(json.loads(receipt.read_text())["programming"], programming)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(program.call_count, 1)
        self.assertTrue(device.closed)

    def test_default_cli_arguments_need_only_prompt(self):
        cli = load_cli()
        output = io.StringIO()
        with patch.object(cli, "run_prompt", return_value={
                "status": "passed", "prompt_ids": [1, 2, 3, 4],
                "tokens": [5, 6], "continuation_text": " test"}) as run, \
             patch.object(cli, "board_lock", return_value=nullcontext()), redirect_stdout(output):
            code = cli.main(["--prompt", "Once upon a day"])
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args.args[1:3],
                         (cli.DEFAULT_TOKENIZER_DIR, cli.DEFAULT_TRANSPORT_DIR))

    def call(self, cli, device, ids, *, receipt=None):
        with patch.object(cli, "load_tokenizer", return_value=FakeTokenizer(ids)), \
             patch.object(cli, "open_transport", return_value=(device, JtagOps)):
            return cli.run_prompt("A new story", Path("/unused-tokenizer"), Path("/unused-transport"),
                                  "HS3", 1.0, receipt)

    def test_new_prompt_reads_and_decodes_all_tokens_without_oracle_claim(self):
        cli = load_cli()
        device = CloseableDevice(tokens=tuple(range(100, 116)))
        with tempfile.TemporaryDirectory() as temp_dir:
            receipt = Path(temp_dir) / "run.json"
            result = self.call(cli, device, [464, 1310, 2576, 1816], receipt=receipt)
            stored = json.loads(receipt.read_text())
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["schema"], "tinystories-short-prompt-jtag-v1")
        self.assertEqual(result["prompt_ids"], [464, 1310, 2576, 1816])
        self.assertEqual(result["tokens"], list(range(100, 116)))
        self.assertEqual(result["continuation_text"], "  made  a story")
        self.assertEqual(result["token_check"], "none")
        self.assertEqual(stored["transactions"], result["transactions"])
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)
        self.assertTrue(device.closed)

    def test_main_preserves_decoded_spacing_on_stdout(self):
        cli = load_cli()
        output = io.StringIO()
        result = {"status": "passed", "prompt_ids": [1, 2, 3, 4],
                  "tokens": [5, 6], "continuation_text": "  made  a story"}
        with patch.object(cli, "run_prompt", return_value=result), \
             patch.object(cli, "board_lock", return_value=nullcontext()), redirect_stdout(output):
            code = cli.main(["--prompt", "A new story", "--tokenizer-dir", "/tokenizer",
                             "--transport-dir", "/transport"])
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(),
                         "Prompt IDs: 1 2 3 4\nGenerated IDs: 5 6\nContinuation:\n  made  a story\n")

    def test_main_reports_error_on_stderr(self):
        cli = load_cli()
        error = io.StringIO()
        with patch.object(cli, "run_prompt", return_value={"status": "failed", "error": "bad prompt"}), \
             patch.object(cli, "board_lock", return_value=nullcontext()), \
             redirect_stderr(error):
            code = cli.main(["--prompt", "bad", "--tokenizer-dir", "/tokenizer",
                             "--transport-dir", "/transport"])
        self.assertEqual(code, 1)
        self.assertIn("bad prompt", error.getvalue())

    def test_wrong_prompt_length_fails_before_opening_board(self):
        cli = load_cli()
        with patch.object(cli, "load_tokenizer", return_value=FakeTokenizer([1, 2, 3])), \
             patch.object(cli, "open_transport", side_effect=AssertionError("opened board")):
            result = cli.run_prompt("too short", Path("/unused"), Path("/unused"), "HS3", 1.0)
        self.assertEqual(result["status"], "failed")
        self.assertIn("exactly four", result["error"])
        self.assertFalse(result["inference_started"])

    def test_out_of_vocabulary_generated_id_retains_failure_receipt(self):
        cli = load_cli()
        tokens = list(range(100, 116))
        tokens[7] = 50257
        device = CloseableDevice(tokens=tuple(tokens))
        with tempfile.TemporaryDirectory() as temp_dir:
            receipt = Path(temp_dir) / "failed.json"
            result = self.call(cli, device, [464, 1310, 2576, 1816], receipt=receipt)
            stored = json.loads(receipt.read_text())
        self.assertEqual(result["status"], "failed")
        self.assertIn("generated token ID 50257", result["error"])
        self.assertEqual(stored["tokens"][7], 50257)
        self.assertNotIn("continuation_text", stored)
        self.assertTrue(device.closed)

    def test_prompt_echo_failure_closes_device_and_retains_trace(self):
        cli = load_cli()
        device = CloseableDevice(tokens=tuple(range(100, 116)), bad_prompt=True)
        result = self.call(cli, device, [464, 1310, 2576, 1816])
        self.assertEqual(result["status"], "failed")
        self.assertIn("command 6000", result["error"])
        self.assertTrue(result["transactions"])
        self.assertFalse(result["inference_started"])
        self.assertTrue(device.closed)


if __name__ == "__main__":
    unittest.main()
