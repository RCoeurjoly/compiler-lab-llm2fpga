"""Tests for the fail-closed YPCB Thunderbolt programming isolation helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/host/ypcb/ypcb_thunderbolt_isolate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ypcb_thunderbolt_isolate", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IsolateForProgrammingTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.thunderbolt = self.root / "thunderbolt"
        self.pci = self.root / "pci"
        domain = self.thunderbolt / "domain1"
        device = self.thunderbolt / "1-1"
        endpoint = self.pci / "0000:42:00.0"
        domain.mkdir(parents=True)
        device.mkdir()
        endpoint.mkdir(parents=True)
        (domain / "security").write_text("user\n")
        (domain / "deauthorization").write_text("1\n")
        (device / "device_name").write_text("Helios 5S\n")
        (device / "unique_id").write_text("c4148780-0010-1ed9-ffff-ffffffffffff\n")
        (device / "authorized").write_text("1\n")
        (endpoint / "vendor").write_text("0x10ee\n")
        (endpoint / "device").write_text("0x0480\n")

    def tearDown(self):
        self.temporary.cleanup()

    def controller(self):
        return self.module.Controller(
            thunderbolt_root=self.thunderbolt,
            pci_root=self.pci,
            geteuid=lambda: 0,
            sleep=lambda _seconds: self._remove_endpoint(),
            timeout_s=0.1,
        )

    def _remove_endpoint(self):
        endpoint = self.pci / "0000:42:00.0"
        if endpoint.exists():
            for child in endpoint.iterdir():
                child.unlink()
            endpoint.rmdir()

    def test_deauthorizes_exact_chassis_and_waits_for_endpoint_absence(self):
        result = self.controller().isolate()

        self.assertEqual((self.thunderbolt / "1-1/authorized").read_text(), "0\n")
        self.assertEqual(result["status"], "isolated_for_programming")
        self.assertEqual(result["endpoint"], "absent")
        self.assertEqual(result["authorization"], "deauthorized")

    def test_is_idempotent_when_already_isolated(self):
        (self.thunderbolt / "1-1/authorized").write_text("0\n")
        self._remove_endpoint()

        result = self.controller().isolate()

        self.assertEqual(result["authorization"], "already_deauthorized")
        self.assertEqual(result["endpoint"], "absent")

    def test_rejects_wrong_chassis_without_writing_authorization(self):
        auth = self.thunderbolt / "1-1/authorized"
        (self.thunderbolt / "1-1/unique_id").write_text("wrong\n")

        with self.assertRaisesRegex(self.module.IsolationError, "UUID"):
            self.controller().isolate()

        self.assertEqual(auth.read_text(), "1\n")

    def test_rejects_unexpected_device_at_pinned_bdf(self):
        (self.pci / "0000:42:00.0/device").write_text("0x9999\n")

        with self.assertRaisesRegex(self.module.IsolationError, "unexpected PCI device"):
            self.controller().isolate()

        self.assertEqual((self.thunderbolt / "1-1/authorized").read_text(), "1\n")

    def test_rejects_matching_endpoint_at_an_unexpected_bdf(self):
        other = self.pci / "0000:43:00.0"
        other.mkdir()
        (other / "vendor").write_text("0x10ee\n")
        (other / "device").write_text("0x0480\n")

        with self.assertRaisesRegex(self.module.IsolationError, "multiple or relocated"):
            self.controller().isolate()

    def test_requires_root(self):
        controller = self.module.Controller(
            thunderbolt_root=self.thunderbolt,
            pci_root=self.pci,
            geteuid=lambda: 1000,
        )
        with self.assertRaisesRegex(self.module.IsolationError, "must run as root"):
            controller.isolate()

    def test_cli_rejects_arguments(self):
        with self.assertRaises(SystemExit) as raised:
            self.module.main(["unexpected"])
        self.assertEqual(raised.exception.code, 2)

    def test_receipt_is_json_serializable(self):
        self._remove_endpoint()
        receipt = self.controller().isolate()
        self.assertEqual(json.loads(json.dumps(receipt)), receipt)


if __name__ == "__main__":
    unittest.main()
