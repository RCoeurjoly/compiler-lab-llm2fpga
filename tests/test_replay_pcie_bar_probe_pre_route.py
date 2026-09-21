import ast
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/pipeline/replay_pcie_bar_probe_pre_route.py"


class ReplayPcieBarProbePreRouteTest(unittest.TestCase):
    def test_hook_authenticates_exact_consumers_and_reconnects_after_placement(self):
        text = HOOK.read_text()
        tree = ast.parse(text)
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
        users = values["EXPECTED_USERS"]
        digest = hashlib.sha256(
            json.dumps(sorted(users), separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(len(users), 14)
        self.assertEqual(digest, values["EXPECTED_SIGNATURE"])
        self.assertIn("ctx.disconnectPort(cell, port)", text)
        self.assertIn("ctx.connectPort(SOURCE_NET, cell, port)", text)
        self.assertIn("if old.users:", text)

    def test_nix_runs_probe_only_at_pre_route(self):
        text = (ROOT / "nix/task6-board-shell.nix").read_text()
        observer = text[text.index('replayBarObserverRoute ='):text.index('prjxray =')]
        self.assertIn("--pre-route", observer)
        self.assertIn("replay_pcie_bar_probe_pre_route.py", observer)
        self.assertIn("${replayResetPatched}/replay.json", observer)
        self.assertNotIn("${replayBarObserverResetPatched}/replay.json", observer)


if __name__ == "__main__":
    unittest.main()
