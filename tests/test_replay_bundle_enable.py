"""Zero-offset core equivalence and response-independent bundle CE gates."""
import hashlib
from itertools import product
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.analysis.check_replay_bundle_enable import check_bundle_enable

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "rtl/diagnostics/compiler_ddr3_trace_replay.sv"
REFERENCE = ROOT / "tests/rtl/compiler_ddr3_trace_replay_reference.sv"
TB = ROOT / "tests/rtl/compiler_ddr3_trace_replay_equivalence_tb.sv"


class ReplayBundleEnableTest(unittest.TestCase):
    def test_exhaustive_boolean_load_identity(self):
        # Independent seven control clauses; 4 states x 2^16 Boolean inputs.
        # No reachability assumption: active/pending/state can be inconsistent.
        checked = 0
        for state in range(4):
            for values in product((False, True), repeat=16):
                active, nonempty, pending, stall, ack, err, mismatch, calib, replay_reset, *controls = values
                cycle = state == 1 and active and calib and not replay_reset
                accept = cycle and not pending and not stall
                response = cycle and (pending or accept) and (ack or err)
                control_failure = state != 3 and any(controls)
                failure = control_failure or (state != 3 and response and (err or mismatch))
                qualifier = state == 1 and not active and nonempty
                self.assertEqual(qualifier and not failure, qualifier and not control_failure)
                checked += 1
        self.assertEqual(checked, 262144)

    def test_frozen_oracle_matches_authenticated_task3b_core(self):
        original = "\n".join(REFERENCE.read_text().splitlines()[2:]) + "\n"
        original = original.replace("module compiler_ddr3_trace_replay_reference (",
                                    "module compiler_ddr3_trace_replay (")
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),
                         "af68f882caca3fffba21d7259937f46a0f8370fb356bcfbda3a6ef1ee9a4cc8a")

    def run_tool(self, command, timeout=60):
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)

    def source_variant(self, directory, mutation):
        if mutation is None:
            return CORE
        source = CORE.read_text()
        old, new = mutation
        self.assertEqual(source.count(old), 1, "mutation must hit exactly one production predicate")
        changed = Path(directory) / CORE.name
        changed.write_text(source.replace(old, new))
        return changed

    def netlist(self, source, directory, mapped=False):
        output = Path(directory) / "core.json"
        commands = (f"read_verilog -sv {source}; hierarchy -check -top compiler_ddr3_trace_replay; "
                    + ("synth_xilinx -top compiler_ddr3_trace_replay -noiopad -nosrl; " if mapped
                       else "proc; opt; ") + f"write_json {output}")
        result = self.run_tool(["yosys", "-Q", "-p", commands])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(output.read_text())

    def simulate(self, mutation=None):
        with tempfile.TemporaryDirectory(prefix="replay-bundle-equivalence-") as directory:
            source = self.source_variant(directory, mutation)
            output = Path(directory) / "test.vvp"
            result = self.run_tool(["iverilog", "-g2012", "-s", "compiler_ddr3_trace_replay_equivalence_tb",
                                    "-o", str(output), str(source), str(REFERENCE), str(TB)])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return self.run_tool(["vvp", str(output)])

    def test_zero_offset_all_state_and_fifo_equivalence(self):
        result = self.simulate()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: zero-offset replay equivalence", result.stdout)

    def test_symbolic_all_register_equivalence(self):
        # Match all state/FIFO bits, then one-step induction proves the cores
        # cannot diverge from equal state. This quantifies over control/ACK/ERR/
        # data, including inactive bundle contents. Simulation checks reset sync.
        result = self.run_tool(["yosys", "-Q", "-p",
            f"read_verilog -sv {REFERENCE} {CORE}; proc; memory_map; opt; "
            "equiv_make compiler_ddr3_trace_replay_reference compiler_ddr3_trace_replay equiv; "
            "hierarchy -top equiv; equiv_simple -seq 1; equiv_induct -seq 1; equiv_status -assert"])
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-6000:])
        self.assertIn("Equivalence successfully proven!", result.stdout)

    def test_elaborated_bundle_enable_has_no_response_dependency(self):
        # An equivalent but slow enclosing full-failure guard must fail here.
        with tempfile.TemporaryDirectory(prefix="replay-bundle-cone-") as directory:
            result = check_bundle_enable(self.netlist(CORE, directory))
            self.assertEqual(result["bundle_bits"], 160)
            self.assertTrue(result["response_independent"])

    def test_restored_slow_guard_is_killed_after_mapping(self):
        # Functional equivalence cannot catch this mutation; structural mapping must.
        mutation = ("control_failure==0 && state==RUN", "failure==0 && state==RUN")
        with tempfile.TemporaryDirectory(prefix="replay-slow-guard-") as directory:
            source = self.source_variant(directory, mutation)
            with self.assertRaisesRegex(AssertionError, "response-dependent bundle enable"):
                check_bundle_enable(self.netlist(source, directory, mapped=True))

    def test_mapped_bundle_enable_has_no_response_dependency(self):
        with tempfile.TemporaryDirectory(prefix="replay-mapped-cone-") as directory:
            self.assertEqual(check_bundle_enable(self.netlist(CORE, directory, mapped=True))["bundle_bits"], 160)

    def test_authenticated_task3b_board_cone_is_rejected(self):
        baseline = Path("/nix/store/h4hdb0rwxg8ckh6wh7f2rs3li1yclscy-compiler-ddr3-trace-replay-synthesis-screen/replay.json")
        with self.assertRaisesRegex(AssertionError, "response-dependent bundle enable"):
            check_bundle_enable(json.loads(baseline.read_text()))

    def test_dropped_control_guard_is_killed_functionally(self):
        result = self.simulate(("control_failure==0 && state==RUN", "state==RUN"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("zero-offset active_address", result.stdout)

    def test_dropped_calibration_guard_is_killed_functionally(self):
        result = self.simulate(("control_failure==0 && state==RUN",
                               "(control_failure==0 || control_failure==32'h04) && state==RUN"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("zero-offset active_address", result.stdout)


if __name__ == "__main__":
    unittest.main()
