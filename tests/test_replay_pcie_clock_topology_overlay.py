"""The replay PCIe clock candidate must match the proven smoke BUFG sites."""

import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "scripts/pipeline/replay_pcie_clock_topology.py"


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Cell:
    def __init__(self, kind, attrs=None):
        self.type = kind
        self.attrs = attrs or {}

    def setAttr(self, key, value):
        self.attrs[key] = value


class ReplayPcieClockTopologyTest(unittest.TestCase):
    def test_real_retained_nextpnr_binding_accepts_both_targets(self):
        module = load(OVERLAY)
        nextpnr = "/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2/bin/nextpnr-xilinx"
        chipdb = "/nix/store/8s95bdz7d69facix9k7h99dfw2chah45-nextpnr-xilinx-chipdb-0.8.2/xc7k480tffg1156.bin"
        source = "import runpy\n"
        for name, (kind, _) in module.TARGETS.items():
            source += f"ctx.createCell({name!r}, {kind!r})\n"
        source += (f"runpy.run_path({str(OVERLAY)!r}, init_globals={{'ctx':ctx}})\n")
        completed = subprocess.run(
            [nextpnr, "--chipdb", chipdb, "--run", "/dev/stdin"],
            input=source, capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_only_two_authenticated_clock_cells_receive_smoke_bels(self):
        module = load(OVERLAY)
        cells = {name: Cell(kind) for name, (kind, _) in module.TARGETS.items()}
        cells["unrelated"] = Cell("BUFGCTRL", {"BEL": "BUFGCTRL_X0Y30/BUFGCTRL"})
        before = copy.deepcopy({name: vars(cell) for name, cell in cells.items()})
        module.apply(SimpleNamespace(cells=cells))
        for name, (_, bel) in module.TARGETS.items():
            before[name]["attrs"]["BEL"] = bel
        self.assertEqual({name: vars(cell) for name, cell in cells.items()}, before)

    def test_missing_wrong_conflicting_or_occupied_target_fails_closed(self):
        module = load(OVERLAY)
        for fault in ("missing", "type", "conflict", "occupied"):
            cells = {name: Cell(kind) for name, (kind, _) in module.TARGETS.items()}
            first = next(iter(module.TARGETS))
            if fault == "missing":
                del cells[first]
            elif fault == "type":
                cells[first].type = "FDRE"
            elif fault == "conflict":
                cells[first].attrs["BEL"] = "BUFGCTRL_X0Y31/BUFGCTRL"
            else:
                cells["unrelated"] = Cell("BUFGCTRL", {"BEL": module.TARGETS[first][1]})
            before = copy.deepcopy({name: vars(cell) for name, cell in cells.items()})
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                module.apply(SimpleNamespace(cells=cells))
            self.assertEqual({name: vars(cell) for name, cell in cells.items()}, before)

    def test_targets_are_exact_known_good_allocation(self):
        module = load(OVERLAY)
        self.assertEqual(set(module.TARGETS.values()), {
            ("BUFGCTRL", "BUFGCTRL_X0Y23/BUFGCTRL"),
            ("BUFGCTRL", "BUFGCTRL_X0Y27/BUFGCTRL"),
        })


if __name__ == "__main__":
    unittest.main()
