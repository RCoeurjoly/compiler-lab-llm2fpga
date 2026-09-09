import importlib.util
from pathlib import Path
import unittest

from tests.test_tinystories_user1_check import Device

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline/infer_tinystories_first_token_jtag.py"


class InferenceDevice(Device):
    def __init__(self, token=11, stuck=False, bad_prompt=False, status_captures=None):
        super().__init__()
        self.started = False
        self.polls = 0
        self.token = token
        self.stuck = stuck
        self.bad_prompt = bad_prompt
        self.now = 0
        self.status_captures = status_captures or {}

    def delay(self, seconds):
        self.now += seconds

    def shift(self, tms, tdi):
        command = sum(bit << i for i, bit in enumerate(tdi))
        op = command >> 60
        if op in (2, 4) or (op == 3 and self.started):
            captured = [(self.response >> i) & 1 for i in range(64)]
            if op == 3 and self.polls in self.status_captures:
                # Model core_done clearing response_word between UPDATE and
                # the next CAPTURE, without altering the command being sent.
                value = self.status_captures[self.polls]
                captured = [(value >> i) & 1 for i in range(64)]
            self.commands.append(command)
            if op == 2:
                self.started = True
                self.response = 0x1000000000000000
            elif op == 4:
                self.response = self.token
            else:
                self.polls += 1
                self.response = (0x2a00000000000000 if self.stuck or self.polls < 3 else 0x2c00000000000000) | self.prompt[0]
            return captured
        result = super().shift(tms, tdi)
        if op == 6 and self.bad_prompt:
            self.response = 99
        return result


class FirstTokenJtagTest(unittest.TestCase):
    def execute(self, device):
        self.assertTrue(SCRIPT.is_file(), "missing first-token inference checker")
        spec = importlib.util.spec_from_file_location("first_token_jtag", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.infer(device, clock_tms=lambda *_: None,
                            reset_tap=device.reset, shift_ir=lambda *_: None,
                            prompt=(7454, 2402, 257, 640), expected_token=11,
                            timeout=0.5, delay=device.delay, monotonic=lambda: device.now)

    def test_exact_prompt_one_start_and_token_without_tap_reset(self):
        device = InferenceDevice()
        result = self.execute(device)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["token"], 11)
        self.assertEqual(device.prompt, [7454, 2402, 257, 640])
        self.assertEqual(device.resets, 1)
        self.assertEqual(sum(c >> 60 == 2 for c in device.commands), 1)

    def test_prompt_mismatch_prevents_start(self):
        device = InferenceDevice(bad_prompt=True)
        result = self.execute(device)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(device.started)
        self.assertTrue(result["transactions"])

    def test_completion_zero_is_reread_without_reset_or_restart(self):
        device = InferenceDevice(status_captures={1: 0})
        result = self.execute(device)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["token"], 11)
        self.assertEqual(result["transient_zero_status_reads"], 1)
        self.assertEqual(device.resets, 1)
        self.assertEqual(sum(c >> 60 == 2 for c in device.commands), 1)

    def test_repeated_zero_is_not_accepted_as_completion(self):
        result = self.execute(InferenceDevice(status_captures={1: 0, 3: 0}))
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("token", result)

    def test_other_invalid_status_is_not_retried(self):
        result = self.execute(InferenceDevice(status_captures={1: 0xdead}))
        self.assertEqual(result["status"], "failed")
        self.assertIn("unexpected inference status", result["error"])
        self.assertNotIn("token", result)

    def test_completion_zero_does_not_mask_wrong_token(self):
        result = self.execute(InferenceDevice(token=99, status_captures={1: 0}))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result.get("token"), 99, result)
        self.assertIn("token mismatch", result["error"])

    def test_wrong_token_preserves_trace(self):
        result = self.execute(InferenceDevice(token=99))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["token"], 99)
        self.assertTrue(result["transactions"])

    def test_busy_timeout_does_not_retry_start(self):
        device = InferenceDevice(stuck=True)
        result = self.execute(device)
        self.assertEqual(result["status"], "failed")
        self.assertIn("timeout", result["error"])
        self.assertEqual(sum(c >> 60 == 2 for c in device.commands), 1)
