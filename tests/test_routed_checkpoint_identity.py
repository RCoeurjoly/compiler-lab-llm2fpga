import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/diagnostics/check_routed_checkpoint_identity.py"
spec = importlib.util.spec_from_file_location("checkpoint_identity", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class RoutedCheckpointIdentityTest(unittest.TestCase):
    def test_route_order_does_not_matter(self):
        self.assertEqual(checker.route_digest("wire1;pip1;1;wire2;;2"),
                         checker.route_digest("wire2;;2;wire1;pip1;1"))

    def test_pip_wire_strength_or_duplicate_change_is_detected(self):
        baseline = checker.route_digest("wire1;pip1;1")
        for changed in ("wire2;pip1;1", "wire1;pip2;1", "wire1;pip1;2",
                        "wire1;pip1;1;wire1;pip1;1"):
            with self.subTest(changed=changed):
                self.assertNotEqual(baseline, checker.route_digest(changed))

    def test_malformed_route_is_rejected(self):
        with self.assertRaises(ValueError):
            checker.route_digest("wire;pip")

    def test_identity_includes_placement_and_parameters(self):
        design = {"modules": {"top": {
            "cells": {"driver": {"type": "SLICE_LUTX", "attributes": {"NEXTPNR_BEL": "site/bel"},
                                  "parameters": {"LUT_INIT": "0010"}}},
            "netnames": {"signal": {"attributes": {"ROUTING": "wire;pip;1"}}}}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "route.json"
            path.write_text(json.dumps(design))
            cells, nets = checker.identity(path)
            self.assertEqual(cells["driver"], ("SLICE_LUTX", "site/bel", {"LUT_INIT": "0010"}))
            self.assertEqual(nets["signal"], checker.route_digest("wire;pip;1"))


if __name__ == "__main__":
    unittest.main()
