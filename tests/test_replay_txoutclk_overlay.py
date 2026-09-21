"""A single reference BUFG lock must not silently widen into a clock/reset ECO."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import subprocess
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CELL = 'pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i.txoutclk0_i'
BEL = 'BUFGCTRL_X0Y27/BUFGCTRL'


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Cell:
    def __init__(self, kind='BUFGCTRL', attrs=None):
        self.type = kind; self.attrs = attrs or {}; self.params = {'unchanged': 42}
    def setAttr(self, key, value): self.attrs[key] = value


class TxoutclkOverlayTest(unittest.TestCase):
    def test_real_retained_nextpnr_python_binding_accepts_overlay(self):
        """The retained IdCellMap is iterable but deliberately has no dict.items()."""
        nextpnr = '/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2/bin/nextpnr-xilinx'
        chipdb = '/nix/store/8s95bdz7d69facix9k7h99dfw2chah45-nextpnr-xilinx-chipdb-0.8.2/xc7k480tffg1156.bin'
        source = ('import runpy\n' + f'ctx.createCell({CELL!r}, "BUFGCTRL")\n' +
                  f'runpy.run_path({str(ROOT / "scripts/pipeline/replay_txoutclk_bufg27.py")!r}, init_globals={{"ctx":ctx}})\n' +
                  f'assert str(ctx.cells[{CELL!r}].attrs["BEL"]) == {BEL!r}\n')
        result = subprocess.run([nextpnr, '--chipdb', chipdb, '--run', '/dev/stdin'],
                                input=source, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_only_exact_reference_bufg_attribute_changes(self):
        """Changing another cell/parameter or accepting a missing target breaks scope."""
        path = ROOT / 'scripts/pipeline/replay_txoutclk_bufg27.py'
        self.assertTrue(path.exists(), 'missing one-cell constraint overlay')
        module = load(path)
        for fault in (None, 'missing', 'type', 'occupied', 'conflict'):
            cells = {CELL: Cell(), 'pipe_mux': Cell(attrs={'BEL': 'BUFGCTRL_X0Y22/BUFGCTRL'}),
                     'ddr': Cell('PLLE2_ADV'), 'reset': Cell('FDRE')}
            if fault == 'missing': del cells[CELL]
            if fault == 'type': cells[CELL].type = 'FDRE'
            if fault == 'occupied': cells['pipe_mux'].attrs['BEL'] = BEL
            if fault == 'conflict': cells[CELL].attrs['BEL'] = 'BUFGCTRL_X0Y20/BUFGCTRL'
            before = copy.deepcopy({n: vars(c) for n,c in cells.items()})
            ctx = SimpleNamespace(cells=cells)
            with self.subTest(fault=fault):
                if fault:
                    with self.assertRaises(RuntimeError): module.apply(ctx)
                    self.assertEqual({n: vars(c) for n,c in cells.items()}, before)
                else:
                    module.apply(ctx)
                    before[CELL]['attrs']['BEL'] = BEL
                    self.assertEqual({n: vars(c) for n,c in cells.items()}, before)

    def test_authenticated_preflight_preserves_route_contract_and_blocks_low_disk(self):
        """An occupied site, wrong source or insufficient capacity cannot launch P&R."""
        path = ROOT / 'scripts/analysis/check_replay_txoutclk_candidate.py'
        self.assertTrue(path.exists(), 'missing authenticated candidate preflight')
        module = load(path)
        result = module.preflight()
        self.assertEqual(result['cell'], CELL)
        self.assertEqual(result['bel'], BEL)
        self.assertEqual(result['net_connections'], {'I': [38070], 'O': [38072]})
        argv = module.route_command(Path('/tmp/unused-output'))
        self.assertEqual(argv[argv.index('--seed') + 1], '15')
        self.assertEqual(argv[argv.index('--pre-pack') + 1],
            '/nix/store/rlw4yzrqhavc7la9hrdng2l1khwklrfn-task6-board-shell-m2-production-source-closure/llm2fpga/scripts/task6/nextpnr_ypcb_uberddr3_two_lane_clock_constraints.py')
        self.assertNotIn('--freq', argv)
        with patch.object(module.shutil, 'disk_usage', return_value=SimpleNamespace(free=143 << 20)):
            with self.assertRaisesRegex(RuntimeError, '150994944'): module.admit_disk(ROOT)
        with patch.object(module.shutil, 'disk_usage', return_value=SimpleNamespace(free=144 << 20)):
            self.assertEqual(module.admit_disk(ROOT)['minimum_bytes'], 150994944)
        with patch.object(module, 'EXPECTED_CELL', 'wrong'):
            with self.assertRaises(ValueError): module.preflight()

    def test_comparison_rejects_collateral_logic_or_clock_changes(self):
        """A timing-PASS candidate with changed non-target logic must remain rejected."""
        path = ROOT / 'scripts/analysis/check_replay_txoutclk_candidate.py'
        self.assertTrue(path.exists(), 'missing collateral FASM gate')
        module = load(path)
        prefix = 'CLK_BUFG_TOP_R_X155Y209.'
        before = prefix + 'BUFGCTRL.BUFGCTRL_X0Y4.IN_USE\n\nCLB_X1Y1.LUT.INIT = 1\n'
        after = prefix + 'BUFGCTRL.BUFGCTRL_X0Y11.IN_USE\n\nCLB_X1Y1.LUT.INIT = 1\n'
        good = module.compare_fasm(before, after)
        self.assertEqual(good['collateral_changed_blocks'], 0)
        self.assertTrue(good['target_site_realized'])
        for bad in (after.replace('INIT = 1', 'INIT = 0'),
                    after + '\nOTHER.INT.A.B\n', before,
                    after.replace('IN_USE\n', 'IN_USE\n' + prefix + 'BUFGCTRL.BUFGCTRL_X0Y11.IS_S0_INVERTED\n'),
                    after + '\n' + prefix + 'BUFGCTRL.BUFGCTRL_X0Y6.IN_USE\n'):
            result = module.compare_fasm(before, bad)
            self.assertFalse(result['candidate_accepted'])


if __name__ == '__main__': unittest.main()
