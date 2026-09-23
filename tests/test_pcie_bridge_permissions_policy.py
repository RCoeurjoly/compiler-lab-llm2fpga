from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "scripts/host/ypcb"


class PcieBridgePermissionsPolicyTests(unittest.TestCase):
    def test_helper_is_fail_closed_and_only_enables_memory_space(self):
        text = (HOST / "ypcb-pcie-bridge-permissions").read_text()
        for required in (
            'BRIDGE_BDF="0000:41:00.0"',
            '0x8086',
            '0x5786',
            '0x2222',
            '0x1111',
            '0x0002',
            'setpci',
            'rescan',
        ):
            self.assertIn(required, text)
        self.assertNotIn("reset_subordinate", text)
        self.assertNotIn("authorized=", text)

    def test_rule_triggers_bridge_and_endpoint_helpers(self):
        text = (HOST / "60-task6-ypcb-pcie.rules").read_text()
        self.assertIn("KERNEL==\"0000:41:00.0\"", text)
        self.assertIn("task6-pcie-bridge-permissions", text)
        self.assertIn("KERNEL==\"0000:42:00.0\"", text)
        self.assertIn("task6-pcie-pci-permissions", text)

    def test_installer_reloads_rules_and_installs_root_helper(self):
        text = (HOST / "install-pcie-lifecycle-policy").read_text()
        self.assertIn("udevadm control --reload-rules", text)
        self.assertIn("/usr/local/libexec/task6-pcie/task6-pcie-bridge-permissions", text)
        self.assertIn("/etc/udev/rules.d/60-task6-ypcb-pcie.rules", text)

    def test_endpoint_helper_is_fixed_identity_and_decode_only(self):
        text = (HOST / "ypcb-pcie-pci-permissions").read_text()
        for required in (
            'ENDPOINT_BDF="0000:42:00.0"',
            '0x10ee',
            '0x0480',
            '0xabcd',
            '0x0006',
            'setpci',
            'resource0',
            'plugdev',
            'chmod',
            'setfacl',
        ):
            self.assertIn(required, text)
        self.assertNotIn("reset_subordinate", text)
        self.assertNotIn("authorized=", text)


if __name__ == "__main__":
    unittest.main()
