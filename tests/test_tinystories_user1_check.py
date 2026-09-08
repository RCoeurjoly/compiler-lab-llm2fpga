import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pipeline/check_tinystories_user1.py"
spec = importlib.util.spec_from_file_location("user1_check", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Device:
    def __init__(self):
        self.resets = 0
        self.commands = []
        self.response = 0
        self.prompt = [0] * 4

    def reset(self, client):
        self.resets += 1
        self.response = 0
        self.prompt = [0] * 4

    def shift(self, tms, tdi):
        assert tms == [0] * 63 + [1]
        result = [(self.response >> i) & 1 for i in range(64)]
        command = sum(bit << i for i, bit in enumerate(tdi))
        self.commands.append(command)
        op = command >> 60
        if op == 3:
            self.response = 0x2800000000000000 | self.prompt[0]
        elif op == 5:
            self.prompt = [0] * 4
            self.response = 0
        elif op == 1:
            self.prompt[(command >> 4) & 3] = command & 65535
            self.response = command & 65535
        else:
            raise AssertionError("unexpected command, including inference START")
        return result


class User1CheckTest(unittest.TestCase):
    def run_check(self, device):
        ir = []
        report = module.check(device, clock_tms=lambda *_: None,
                              reset_tap=device.reset,
                              shift_ir=lambda client, opcode, bits: ir.append((opcode, bits)),
                              delay=lambda _: None)
        self.assertEqual(ir, [(2, 6)] * 3)
        return report

    def test_response_pipeline_without_intervening_tap_reset(self):
        device = Device()
        report = self.run_check(device)
        self.assertEqual(device.resets, 3)
        self.assertEqual(len(device.commands), 54)
        self.assertEqual({command >> 60 for command in device.commands}, {1, 3, 5})
        self.assertEqual(device.prompt, [0] * 4)
        self.assertEqual(report["status"], "passed")
        self.assertFalse(report["inference_started"])

    def test_zero_status_is_failure(self):
        device = Device()
        device.shift = lambda *_: [0] * 64
        with self.assertRaisesRegex(RuntimeError, "expected 2800000000000000"):
            self.run_check(device)

    def test_short_response_is_failure(self):
        device = Device()
        device.shift = lambda *_: [0] * 63
        with self.assertRaisesRegex(RuntimeError, "short JTAG response"):
            self.run_check(device)


if __name__ == "__main__":
    unittest.main()
