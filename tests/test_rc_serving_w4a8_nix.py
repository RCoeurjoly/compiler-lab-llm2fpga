import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KEY = "tinystories-w4a8-rc-serving-mask10-vocab6-width2"


class RcServingW4A8NixTest(unittest.TestCase):
    def test_w4a8_system_is_dedicated_and_exported(self) -> None:
        system = (ROOT / "nix/rc-serving-w4a8-system.nix").read_text()
        flake = (ROOT / "flake.nix").read_text()
        self.assertIn("schema_version = 1", system)
        self.assertIn('--out-dir "$out"', system)
        self.assertIn("materialize_rc_serving_w4a8.py", system)
        for suffix in (
            "frozen-bundle",
            "prefill-8-pytorch-exported",
            "decode-8-pytorch-exported",
            "decode-9-pytorch-exported",
        ):
            self.assertIn(f'"{KEY}-{suffix}"', flake)

    def test_bundle_is_rebuilt_twice_and_compared(self) -> None:
        system = (ROOT / "nix/rc-serving-w4a8-system.nix").read_text()
        self.assertNotIn("mkdir -p repeat", system)
        self.assertIn('cmp "$out/manifest.json" repeat/manifest.json', system)
        self.assertIn('cmp "$out/frozen/weights.bin" repeat/frozen/weights.bin', system)


if __name__ == "__main__":
    unittest.main()
