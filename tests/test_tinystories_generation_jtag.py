"""Exercise the generation checker against the existing delayed-response USER1 ABI."""
import importlib.util
from pathlib import Path
import unittest

from tests.test_tinystories_user1_check import Device


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline/infer_tinystories_generation_jtag.py"


class GenerationDevice(Device):
    def __init__(self, tokens=(11, 612), *, stuck=False, bad_prompt=False,
                 zero_status_once=False, ignore_index=False, bad_status=False):
        super().__init__()
        self.tokens = tokens
        self.stuck = stuck
        self.bad_prompt = bad_prompt
        self.zero_status_once = zero_status_once
        self.ignore_index = ignore_index
        self.bad_status = bad_status
        self.started = False
        self.polls = 0
        self.now = 0.0
        self.zero_sent = False

    def delay(self, seconds):
        self.now += seconds

    def shift(self, tms, tdi):
        assert tms == [0] * 63 + [1]
        captured = self.response
        command = sum(bit << i for i, bit in enumerate(tdi))
        self.commands.append(command)
        op = command >> 60
        if op == 5:
            self.prompt = [0] * 4
            self.response = 0
            self.started = False
        elif op == 1:
            self.prompt[(command >> 16) & 3] = command & 65535
            self.response = command & 65535
        elif op == 6:
            self.response = 99 if self.bad_prompt else self.prompt[(command >> 16) & 3]
        elif op == 2:
            self.started = True
            self.response = 0x1000000000000000
        elif op == 3:
            if self.started:
                self.polls += 1
                status = 0x2a00000000000000 if self.stuck or self.polls < 3 else 0x2c00000000000000
                if self.bad_status:
                    status = 0x2e00000000000000
                self.response = status | self.prompt[0]
                if self.zero_status_once and not self.zero_sent and self.polls == 2:
                    captured = 0
                    self.zero_sent = True
            else:
                self.response = 0x2800000000000000 | self.prompt[0]
        elif op == 4:
            index = 0 if self.ignore_index else command & 15
            self.response = self.tokens[index]
        else:
            raise AssertionError(f"unexpected opcode {op}")
        return [(captured >> i) & 1 for i in range(64)]


class GenerationJtagTest(unittest.TestCase):
    def execute(self, device, expected=(11, 612), *, prompt=(7454, 2402, 257, 640),
                generation_steps=None):
        self.assertTrue(SCRIPT.is_file(), "missing generation inference checker")
        spec = importlib.util.spec_from_file_location("generation_jtag", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mode = {} if generation_steps is None else {"generation_steps": generation_steps}
        return module.infer_generation(
            device, clock_tms=lambda *_: None, reset_tap=device.reset,
            shift_ir=lambda *_: None, prompt=prompt,
            expected_tokens=expected, timeout=0.5,
            delay=device.delay, monotonic=lambda: device.now,
            **mode,
        )

    def test_exact_two_tokens_require_one_start_and_indexed_reads(self):
        device = GenerationDevice()
        result = self.execute(device)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["tokens"], [11, 612])
        self.assertEqual(device.resets, 1)
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)
        self.assertEqual([command & 15 for command in device.commands if command >> 60 == 4], [0, 1])
        self.assertEqual(device.prompt, [7454, 2402, 257, 640])

    def test_sixteen_token_readback_reaches_index_fifteen_without_restart(self):
        expected = (11, 612, 373, 257, 1310, 2576, 3706, 20037,
                    13, 1375, 6151, 284, 711, 2354, 287, 262)
        device = GenerationDevice(tokens=expected)
        result = self.execute(device, expected=expected)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["tokens"], list(expected))
        self.assertEqual([command & 15 for command in device.commands if command >> 60 == 4],
                         list(range(16)))
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)

    def test_unverified_new_prompt_reads_sixteen_tokens_once(self):
        tokens = tuple(range(100, 116))
        device = GenerationDevice(tokens=tokens)
        result = self.execute(device, expected=None, prompt=(464, 1310, 2576, 20037),
                              generation_steps=16)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["token_check"], "none")
        self.assertEqual(result["tokens"], list(tokens))
        self.assertEqual(device.prompt, [464, 1310, 2576, 20037])
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)
        self.assertEqual([command & 15 for command in device.commands if command >> 60 == 4],
                         list(range(16)))

    def test_unverified_mode_retries_one_transient_zero(self):
        device = GenerationDevice(tokens=tuple(range(16)), zero_status_once=True)
        result = self.execute(device, expected=None, generation_steps=16)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["transient_zero_status_reads"], 1)
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)

    def test_unverified_mode_rejects_persistent_bad_status(self):
        device = GenerationDevice(tokens=tuple(range(16)), bad_status=True)
        result = self.execute(device, expected=None, generation_steps=16)
        self.assertEqual(result["status"], "failed", result)
        self.assertIn("unexpected inference status", result["error"])
        self.assertFalse(any(command >> 60 == 4 for command in device.commands))

    def test_wrong_second_token_fails_after_recording_first(self):
        result = self.execute(GenerationDevice(tokens=(11, 99)))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tokens"], [11, 99])
        self.assertIn("token mismatch at index 1", result["error"])
        self.assertTrue(result["transactions"])

    def test_ignoring_index_cannot_pass_two_token_check(self):
        result = self.execute(GenerationDevice(ignore_index=True))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["tokens"], [11, 11])

    def test_busy_timeout_does_not_reset_or_repeat_start(self):
        device = GenerationDevice(stuck=True)
        result = self.execute(device)
        self.assertEqual(result["status"], "failed")
        self.assertIn("timeout", result["error"])
        self.assertEqual(device.resets, 1)
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)
        self.assertFalse(any(command >> 60 == 4 for command in device.commands))

    def test_bad_prompt_readback_prevents_start(self):
        device = GenerationDevice(bad_prompt=True)
        result = self.execute(device)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(device.started)
        self.assertFalse(any(command >> 60 == 2 for command in device.commands))

    def test_single_zero_completion_capture_is_retried_without_restart(self):
        device = GenerationDevice(zero_status_once=True)
        result = self.execute(device)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["transient_zero_status_reads"], 1)
        self.assertEqual(sum(command >> 60 == 2 for command in device.commands), 1)


if __name__ == "__main__":
    unittest.main()
