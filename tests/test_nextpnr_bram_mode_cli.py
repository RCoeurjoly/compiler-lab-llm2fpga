"""Exercise real FASM emission, not source-text matching or a mocked writer.

Missing odd-width mode emission must fail widths 1/9; even widths and RAMB18
must not acquire RAMB36 features. Expectations follow Project X-Ray's
RAMB36-features documentation, independently of nextpnr implementation.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = os.environ.get('NEXTPNR_CHECKPOINT_TOOL')
CHIPDB = os.environ.get('NEXTPNR_CHECKPOINT_CHIPDB')


@unittest.skipUnless(TOOL and CHIPDB, 'requires pinned executable and Kintex chipdb')
class NextpnrBramModeCliTest(unittest.TestCase):
    def emit(self, original, parameter, width):
        site = 'RAMB36_X2Y43' if original == 'RAMB36E1' else 'RAMB18_X2Y86'
        parameters = {name: format(0, '032b') for name in
                      ('READ_WIDTH_A', 'READ_WIDTH_B', 'WRITE_WIDTH_A', 'WRITE_WIDTH_B')}
        parameters[parameter] = format(width, '032b')
        cell = dict(type=f'{original}_{original}', parameters=parameters,
                    attributes={'NEXTPNR_BEL': f'{site}/{original}', 'X_ORIG_TYPE': original},
                    port_directions={}, connections={})
        design = {'modules': {'top': {'attributes': {'top': '1'}, 'ports': {},
                  'settings': {'route': '00000000000000000000000000000001'},
                  'cells': {'weight_rom': cell}, 'netnames': {}}}}
        with tempfile.TemporaryDirectory() as directory:
            source, fasm = Path(directory)/'input.json', Path(directory)/'output.fasm'
            source.write_text(json.dumps(design))
            result = subprocess.run([TOOL, '--chipdb', CHIPDB, '--json', str(source),
                                     '--no-pack', '--no-place', '--no-route', '--fasm', str(fasm)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return {line.strip() for line in fasm.read_text().splitlines() if line.strip()}

    def test_ramb36_odd_width_requires_macro_mode_for_each_port(self):
        for parameter in ('READ_WIDTH_A', 'READ_WIDTH_B', 'WRITE_WIDTH_A', 'WRITE_WIDTH_B'):
            for width, half_width in ((1, 1), (9, 4)):
                with self.subTest(parameter=parameter, width=width):
                    features = self.emit('RAMB36E1', parameter, width)
                    prefix = 'BRAM_L_X26Y215'
                    expected = f'{prefix}.RAMB36.BRAM36_{parameter}_1'
                    self.assertIn(expected, features)
                    self.assertEqual({f for f in features if '.RAMB36.BRAM36_' in f}, {expected})
                    for half in (0, 1):
                        self.assertIn(f'{prefix}.RAMB18_Y{half}.{parameter}_{half_width}', features)

    def test_even_width_and_ramb18_do_not_enable_ramb36_odd_mode(self):
        for original, width in (('RAMB36E1', 0), ('RAMB36E1', 2), ('RAMB36E1', 4),
                                ('RAMB36E1', 18), ('RAMB36E1', 36),
                                ('RAMB18E1', 1), ('RAMB18E1', 9)):
            with self.subTest(original=original, width=width):
                features = self.emit(original, 'READ_WIDTH_A', width)
                self.assertFalse(any('.RAMB36.BRAM36_' in f for f in features))


if __name__ == '__main__':
    unittest.main()
