"""Reject incomplete, illegal, or clock-weakened route evidence."""
import importlib.util
import unittest
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RouteTest(unittest.TestCase):
    def test_nix_database_overlay_preserves_base_and_all_other_files(self):
        base = Path("/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2/share/nextpnr/external/prjxray-db")
        output = subprocess.run(["nix", "build", ".#compiler-ddr3-trace-replay-database", "--impure",
                                 "--no-link", "--print-out-paths"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(output.returncode, 0, output.stderr)
        target = Path(output.stdout.strip())
        modified = Path("kintex7/segbits_lioi3_tbytesrc.db")
        self.assertEqual(hashlib.sha256((base / modified).read_bytes()).hexdigest(),
                         "d74bb512c56af57510ce89b351f1bf666e96196e20c8b1bc18e8521fe45bdd61")
        self.assertEqual(hashlib.sha256((target / modified).read_bytes()).hexdigest(),
                         "7108c7c92097d591e404852ce5eb18a6ed1851352d399eb29c1bd7eed3ffd710")
        base_files = {p.relative_to(base) for p in base.rglob("*") if p.is_file()}
        target_files = {p.relative_to(target) for p in target.rglob("*") if p.is_file()}
        self.assertEqual(target_files, base_files)
        for relative in base_files - {modified}:
            self.assertEqual((target / relative).resolve(), (base / relative).resolve())

    def test_authenticated_database_patch_adds_only_required_encoding(self):
        patch = ROOT / "patches/prjxray-db/0001-kintex7-add-lioi3-tbytesrc-oclkm-imux31.patch"
        self.assertTrue(patch.exists(), "authenticated conversion database patch is missing")
        self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(),
                         "197e2f126a6f3917c1ceca62394acd957397679538df077f7119de97c28e05bc")
        source = Path("/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2/share/nextpnr/external/prjxray-db/kintex7/segbits_lioi3_tbytesrc.db")
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         "d74bb512c56af57510ce89b351f1bf666e96196e20c8b1bc18e8521fe45bdd61")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "kintex7/segbits_lioi3_tbytesrc.db"
            target.parent.mkdir()
            shutil.copyfile(source, target)
            subprocess.run(["patch", "-p1", "-i", str(patch)], cwd=temporary, check=True, capture_output=True)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),
                             "7108c7c92097d591e404852ce5eb18a6ed1851352d399eb29c1bd7eed3ffd710")
            self.assertEqual(set(target.read_text().splitlines()) - set(source.read_text().splitlines()),
                             {"LIOI3_TBYTESRC.IOI_OCLKM_0.IOI_IMUX31_1 30_94 31_83 31_93"})

    def test_requires_legal_route_and_both_final_fixed_clock_reports(self):
        path = ROOT / "scripts/analysis/check_compiler_replay_route.py"
        self.assertTrue(path.exists(), "route acceptance checker is missing")
        spec = importlib.util.spec_from_file_location("route_gate", path)
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        log = """Info: Max frequency for clock 'rowstream_clk': 60.68 MHz (FAIL at 83.33 MHz)
Info: iter=8 wires=721183 overused=0 overuse=0 archfail=0
Info: Running router1 to check that route is legal...
Info: Routing 0 arcs.
Info: Routing complete.
Info: Max frequency for clock 'rowstream_clk': 88.13 MHz (PASS at 83.33 MHz)
Info: Max frequency for clock 'pcie_user_clk': 89.03 MHz (PASS at 62.50 MHz)
Info: Running post-routing legalisation...
30 warnings, 0 errors
"""
        result = gate.qualify(log)
        self.assertEqual(result["clocks"]["rowstream_clk"]["fmax_mhz"], 88.13)
        mutations = [
            ("Routing complete.", "route interrupted"),
            ("archfail=0", "archfail=1"),
            ("Routing 0 arcs.", "Routing 2 arcs."),
            ("88.13 MHz (PASS", "80.00 MHz (FAIL"),
            ("at 83.33 MHz", "at 50.00 MHz"),
            ("at 62.50 MHz", "at 50.00 MHz"),
            ("'pcie_user_clk'", "'other'"),
            ("30 warnings, 0 errors", "30 warnings, 1 errors"),
        ]
        for before, after in mutations:
            with self.subTest(after=after), self.assertRaises(ValueError):
                gate.qualify(log.replace(before, after))


if __name__ == "__main__":
    unittest.main()
