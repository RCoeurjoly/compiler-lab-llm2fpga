"""Exercise the evaluated production recipe on the real elaborated compiler core."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(all(os.environ.get(k) for k in
    ('FULL16_SYNTHESIS_COMMAND', 'FULL16_ELABORATION', 'YOSYS')),
    'native compiler checkpoint inputs are supplied by the Nix check')
class Full16BoardFsmEncoding(unittest.TestCase):
    def test_production_prepare_preserves_existing_compiler_encoding(self):
        command = Path(os.environ['FULL16_SYNTHESIS_COMMAND']).read_text()
        # Execute the production preparation, not a separately maintained recipe.
        body = command.split('hierarchy -check -top compiler_ddr3_trace_replay_top\n', 1)[1]
        prepare = body.split('synth_xilinx', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'prepared.json'
            script = f"read_rtlil {os.environ['FULL16_ELABORATION']};\n{prepare}\nselect =*; proc; select -clear; flatten; write_json {output}\n"
            result = subprocess.run([os.environ['YOSYS'], '-Q', '-p', script],
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr)
            main = json.loads(output.read_text())['modules']['main']
            self.assertEqual(main['netnames']['fsm0.out']['attributes'].get('fsm_encoding'),
                             'none', 'production recipe still allows generic FSM extraction')


if __name__ == '__main__':
    unittest.main()
