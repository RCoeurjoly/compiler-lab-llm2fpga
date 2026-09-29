"""Reject real-netlist mutations that would corrupt the compatibility mapping."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('FULL16_RAW_JSON') and os.environ.get('FULL16_MAPPED_JSON'),
                     'real production netlists are supplied by the Nix build')
class Full16DramCompatAudit(unittest.TestCase):
    def test_real_netlist_passes_and_semantic_mutations_are_rejected(self):
        before = Path(os.environ['FULL16_RAW_JSON'])
        after = Path(os.environ['FULL16_MAPPED_JSON'])
        audit = Path(__file__).resolve().parents[1] / 'scripts/analysis/verify_full16_dram_compat.py'
        audit = Path(os.environ.get('FULL16_AUDIT', audit))
        def run(path):
            return subprocess.run([sys.executable, str(audit), str(before), str(path)],
                                  capture_output=True, text=True, timeout=90)
        good = run(after)
        self.assertEqual(good.returncode, 0, good.stderr)
        original = json.loads(after.read_text())
        module = next(m for m, v in original['modules'].items()
                      if any(c['type'] == 'RAM64X1D' for c in v['cells'].values())
                      and not int(v.get('attributes', {}).get('blackbox', '0'), 2))
        name = next(n for n, c in original['modules'][module]['cells'].items()
                    if c['type'] == 'RAM64X1D')
        with tempfile.TemporaryDirectory() as directory:
            for fault in ('init', 'write-enable', 'address', 'output', 'extra-module'):
                with self.subTest(fault=fault):
                    changed = copy.deepcopy(original)
                    cell = changed['modules'][module]['cells'][name]
                    if fault == 'extra-module':
                        changed['modules']['unexpected_active_logic'] = {
                            'attributes': {}, 'ports': {}, 'netnames': {}, 'cells': {}}
                    elif fault == 'init':
                        value = cell['parameters']['INIT']
                        cell['parameters']['INIT'] = ('1' if value[0] == '0' else '0') + value[1:]
                    else:
                        port = {'write-enable': 'WE', 'address': 'A0', 'output': 'SPO'}[fault]
                        bit = cell['connections'][port][0]
                        cell['connections'][port] = ['0' if bit != '0' else '1']
                    path = Path(directory) / 'fault.json'
                    path.write_text(json.dumps(changed))
                    bad = run(path)
                    self.assertNotEqual(bad.returncode, 0, fault)
                    self.assertIn('AssertionError', bad.stderr, bad.stderr)


if __name__ == '__main__':
    unittest.main()
