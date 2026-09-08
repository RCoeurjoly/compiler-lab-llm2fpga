"""Execute the first-LayerNorm stale-read regression through Calyx and SV."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from scripts.pipeline import run_bram_production_sv as runner

ROOT = Path(__file__).resolve().parents[1]


class ProductionMemoryLatencyTest(unittest.TestCase):
    def test_declared_latency_matches_staged_memory_execution(self):
        self.assertTrue(hasattr(runner, "prepare_production_library"), "missing production latency declaration")
        install = Path(subprocess.check_output(
            ["nix", "build", "--no-link", "--print-out-paths", ".#calyx"],
            cwd=ROOT, text=True, timeout=120).strip())
        iverilog = os.environ.get("IVERILOG", shutil.which("iverilog"))
        vvp = os.environ.get("VVP", shutil.which("vvp"))
        self.assertTrue(iverilog and vvp, "Icarus required for memory latency regression")
        original = (install / "share/calyx/primitives/memories/seq.futil").read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            aligned = runner.prepare_production_library(install, directory / "library")
            for name, library, expected_success in (
                ("legacy", install / "share/calyx", False),
                ("aligned", aligned, True),
            ):
                with self.subTest(name=name):
                    compiled = subprocess.run([
                        str(install / "bin/calyx"), str(ROOT / "tests/rtl/tinystories_memory_latency.futil"),
                        "-l", str(library), "-d", "cell-share", "-b", "verilog", "--synthesis", "--nested",
                    ], check=True, capture_output=True, text=True, timeout=30)
                    sv = directory / (name + ".sv")
                    sv.write_text(runner.annotate_bram_memories(compiled.stdout))
                    executable = directory / name
                    subprocess.run([iverilog, "-g2012", "-s", "tb", "-o", str(executable),
                                    str(sv), str(ROOT / "tests/rtl/tinystories_memory_latency_tb.sv")],
                                   check=True, capture_output=True, timeout=30)
                    result = subprocess.run([vvp, str(executable)], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode == 0, expected_success, result.stdout + result.stderr)
                    if expected_success:
                        self.assertIn("sum=-4243", result.stdout)
            receipt = json.loads((aligned / "production-memory-latency.json").read_text())
            self.assertEqual(receipt["seq_mem_d1_schedule_cycles"], 2)
        self.assertEqual((install / "share/calyx/primitives/memories/seq.futil").read_bytes(), original)
