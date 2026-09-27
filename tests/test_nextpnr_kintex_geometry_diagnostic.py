"""The Kintex placement experiment must use a separate Nix tool output."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NextpnrKintexGeometryDiagnosticTest(unittest.TestCase):
    def test_overrides_do_not_reuse_generic_heap_settings(self) -> None:
        patch = (ROOT / "patches/nextpnr-xilinx/0038-allow-kintex-heap-geometry-diagnostic-overrides.patch").read_text()
        self.assertIn('setting<float>("kintexHeap/alpha", 0.08f)', patch)
        self.assertIn('setting<float>("kintexHeap/beta", 0.4f)', patch)
        self.assertNotIn('setting<float>("placerHeap/alpha"', patch)
        self.assertNotIn('setting<float>("placerHeap/beta"', patch)

    def test_route_control_preserves_recorded_two_token_build_settings(self) -> None:
        evaluated = subprocess.run(
            ["nix", "eval", "--raw", ".#nextpnr-kintex-route-control.drvPath"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(evaluated.returncode, 0, evaluated.stderr)
        derivation = subprocess.run(
            ["nix", "derivation", "show", evaluated.stdout],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(derivation.returncode, 0, derivation.stderr)
        record = next(iter(json.loads(derivation.stdout)["derivations"].values()))
        environment = record["env"]
        self.assertEqual(environment["src"], "/nix/store/rzmrkc8aff649333zc7rfc6pdzmsimqy-source")
        self.assertEqual(environment["patches"], "")
        self.assertIn("substituteInPlace common/placer1.cc", environment["postPatch"])
        self.assertIn("timing_analysis(ctx, true, true, true, false);", environment["postPatch"])
        self.assertEqual(
            environment["cmakeFlags"],
            "-DCURRENT_GIT_VERSION=stable-backports -DARCH=xilinx -DBUILD_GUI=OFF -DBUILD_TESTS=OFF -DUSE_OPENMP=ON -Wno-deprecated",
        )

    def test_diagnostic_tool_is_a_separate_nix_package(self) -> None:
        result = subprocess.run(
            ["nix", "eval", "--raw", ".#nextpnr-kintex-geometry-diagnostic.drvPath"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("nextpnr-xilinx-kintex-geometry-diagnostic", result.stdout)


if __name__ == "__main__":
    unittest.main()
