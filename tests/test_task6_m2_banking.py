"""Behavior and authentication tests for the static M2 word-banking pass."""
import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "third_party/task6-e368449/fpga/rtl/task6_pcie_axil_rowstream_loader_ingress.v"
MODULE = "task6_pcie_axil_rowstream_loader_ingress"


def overlay():
    path = ROOT / "scripts/pipeline/apply_task6_m2_banking_overlay.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("m2_overlay", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def testbench(source, compensation):
    header = source[:source.index("\n);")]
    ports = re.findall(r"\b(input|output)\s+(?:wire|reg)\s+(\[[^\]]+\])?\s*(\w+)\s*[,\n]", header)
    inputs = [(width or "", name) for direction, width, name in ports if direction == "input"]
    outputs = [(width or "", name) for direction, width, name in ports if direction == "output"]
    registers = re.findall(r"^    reg\s+(\[[^\]]+\])?\s*(\w+)\s*(\[0:3\])?;", source, re.M)
    state = [name for _, name in outputs]
    state += [f"{name}[{i}]" if array else name for _, name, array in registers
              if name not in ("m2_full_block_input_raw_next", "read_window_data")
              for i in (range(4) if array else range(1))]
    lines = ["module tb;", "localparam COMMAND_WIDTH=192;", "reg clk=0; always #5 clk=~clk;"]
    lines += [f"reg {width} {name};" for width, name in inputs if name != "clk"]
    connections = ", ".join(f".{name}({name})" for _, name in inputs)
    for variant in ("gold", "gate"):
        lines.append(f"{MODULE}_{variant} #(.M2_INPUT_PCIE7X_ROR64_COMPENSATE({compensation})) {variant} ({connections});")
    lines += ["integer n, word_i, mask_i, bank_i, cycles=0; reg [31:0] address;",
              "task tick; begin @(posedge clk); #1; cycles=cycles+1;"]
    lines += [f'if (gold.{name} !== gate.{name}) $fatal(1,"zero-offset {name} cycle=%0d index=%h mask=%h", cycles,gold.awaddr_q,gold.wstrb_q);' for name in state]
    lines += ["end endtask", "task random_state; begin @(negedge clk);"]
    lines += [f"gold.{name} = {{$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random}}; gate.{name}=gold.{name};" for name in state]
    lines += ["end endtask", "task idle; begin"]
    lines += [f"{name}=0;" for _, name in inputs if name != "clk"]
    lines += ["rst_n=1; s_axi_bready=1; s_axi_rready=1; end endtask",
              "task transaction(input [31:0] addr, input [3:0] mask, input integer order); integer aw_done,w_done,k; begin",
              "@(negedge clk); idle; s_axi_awaddr=addr; s_axi_wdata=$random; s_axi_wstrb=mask;",
              "s_axi_bready=0; s_axi_rready=0; aw_done=0; w_done=0;",
              "for(k=0;k<12;k=k+1) begin",
              "s_axi_awvalid=!aw_done && (order!=1 || k>=2); s_axi_wvalid=!w_done && (order!=0 || k>=2);",
              "s_axi_arvalid=(k==0); s_axi_araddr=addr;",
              "if(s_axi_awvalid && gold.s_axi_awready) aw_done=1;",
              "if(s_axi_wvalid && gold.s_axi_wready) w_done=1;",
              "tick; @(negedge clk); end",
              "if(!gold.s_axi_bvalid || !gold.s_axi_rvalid) $fatal(1,\"transaction did not complete\");",
              "idle; repeat(4) tick; end endtask",
              "initial begin idle; rst_n=0; repeat(2) tick; @(negedge clk); rst_n=1; repeat(3) tick;",
              "for(word_i=0;word_i<1024;word_i=word_i+1) for(mask_i=0;mask_i<16;mask_i=mask_i+1) begin",
              "random_state;"]
    lines += [f"{name}={{$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random,$random}};" for _, name in inputs if name not in ("clk", "rst_n")]
    lines += ["rst_n=1; gold.awaddr_q=($random & 32'hfffff003) | (word_i<<2); gate.awaddr_q=gold.awaddr_q;",
              "gold.wstrb_q=mask_i; gate.wstrb_q=mask_i;",
              "gold.awaddr_valid_q=1; gate.awaddr_valid_q=1; gold.wdata_valid_q=1; gate.wdata_valid_q=1;",
              "gold.s_axi_bvalid=0; gate.s_axi_bvalid=0; gold.read_pending_q=1; gate.read_pending_q=1;",
              "gold.read_word_index_q=word_i; gate.read_word_index_q=word_i; tick;",
              "@(negedge clk); s_axi_bready=0; s_axi_rready=0; tick;",
              "@(negedge clk); rst_n=0; tick; end",
              "@(negedge clk); idle; rst_n=0; repeat(2) tick; @(negedge clk); idle; repeat(3) tick;",
              "for(bank_i=0;bank_i<5;bank_i=bank_i+1) for(word_i=0;word_i<16;word_i=word_i+1) for(mask_i=0;mask_i<16;mask_i=mask_i+1) begin",
              "case(bank_i) 0: address='h080; 1: address='h340; 2: address='h380; 3: address='h540; 4: address='h580; endcase",
              "address=address+word_i*4; transaction(address | 32'habcd0000 | (mask_i & 3),mask_i,mask_i%3); end",
              "for(n=0;n<12;n=n+1) begin @(negedge clk); idle; s_axi_awvalid=1; s_axi_awaddr='h540;",
              "repeat(n) tick; @(negedge clk); s_axi_wvalid=1; s_axi_wdata=$random; s_axi_wstrb=15; s_axi_bready=0; s_axi_arvalid=1; s_axi_araddr='h540; s_axi_rready=0;",
              "repeat(n) tick; @(negedge clk); rst_n=0; tick; @(negedge clk); idle; repeat(4) tick; end",
              "transaction('h50c,15,2); transaction('h50c,15,2); transaction('h53c,0,0); transaction('h5c0,15,1);",
              f'$display("PASS: zero-offset all-state M2 compensation={compensation} cycles=%0d",cycles); $finish; end',
              "initial begin #2000000; $fatal(1,\"watchdog\"); end", "endmodule"]
    return "\n".join(lines)


class M2BankingTest(unittest.TestCase):
    def module(self):
        module = overlay()
        self.assertIsNotNone(module, "authenticated M2 banking overlay is missing")
        return module

    def test_authenticated_deterministic_transform(self):
        module = self.module()
        original = ORIGINAL.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), "224b3a384770378a64768aaa900adcba07a3672812dd92d3b70fadf6a88315f1")
        output = module.transform(original)
        self.assertEqual(hashlib.sha256(output).hexdigest(), "d3974d466d6e13c895d888d09fb63d8725a15be72756736dae948d30b4b3acea")
        self.assertEqual(output, module.transform(original))
        with self.assertRaisesRegex(ValueError, "input SHA-256"):
            module.transform(original + b"\n")
        with self.assertRaisesRegex(ValueError, "output SHA-256"):
            module.verify_output(output + b"\n")

    def simulate(self, compensation, mutation=None):
        module = self.module()
        original = ORIGINAL.read_text()
        candidate = module.transform(original.encode()).decode()
        if mutation:
            before, after = mutation
            self.assertIn(before, candidate)
            candidate = candidate.replace(before, after, 1)
        with tempfile.TemporaryDirectory(prefix="m2-banking-") as temp:
            directory = Path(temp)
            gold, gate, bench = [directory / name for name in ("gold.v", "gate.v", "tb.sv")]
            gold.write_text(original.replace("module " + MODULE, "module " + MODULE + "_gold", 1))
            gate.write_text(candidate.replace("module " + MODULE, "module " + MODULE + "_gate", 1))
            bench.write_text(testbench(original, compensation))
            executable = directory / "test.vvp"
            built = subprocess.run(["iverilog", "-g2012", "-s", "tb", "-o", str(executable), str(gold), str(gate), str(bench)], capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            return subprocess.run(["vvp", str(executable)], capture_output=True, text=True, timeout=120)

    def test_all_words_strobes_aliases_reset_backpressure_both_modes(self):
        for mode in (0, 1):
            with self.subTest(compensation=mode):
                result = self.simulate(mode)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS: zero-offset all-state", result.stdout)

    def test_symbolic_arbitrary_equal_state_induction(self):
        module = self.module()
        for mode in (0, 1):
            with self.subTest(compensation=mode), tempfile.TemporaryDirectory(prefix="m2-proof-") as temp:
                directory = Path(temp)
                for name, data in (("gold", ORIGINAL.read_bytes()),
                                   ("gate", module.transform(ORIGINAL.read_bytes()))):
                    source = data.decode().replace("module " + MODULE,
                                                   "module " + name, 1)
                    source = source.replace(
                        "parameter integer M2_INPUT_PCIE7X_ROR64_COMPENSATE = 0",
                        f"parameter integer M2_INPUT_PCIE7X_ROR64_COMPENSATE = {mode}")
                    (directory / (name + ".v")).write_text(source)
                commands = (
                    f"read_verilog -sv {directory}/gold.v {directory}/gate.v; "
                    "proc; memory_map; opt; equiv_make gold gate equiv; "
                    "hierarchy -top equiv; equiv_simple -seq 1; "
                    "equiv_induct -seq 1; equiv_status -assert")
                result = subprocess.run(["yosys", "-Q", "-p", commands],
                                        capture_output=True, text=True, timeout=180)
                self.assertEqual(result.returncode, 0,
                                 (result.stdout + result.stderr)[-8000:])
                self.assertIn("Equivalence successfully proven!", result.stdout)

    def test_functional_mutations_are_detected(self):
        mutations = {
            "wrong_word": (0, ("10'h150: m2_full_block_input_vector_o[0 +: 32]", "10'h151: m2_full_block_input_vector_o[0 +: 32]")),
            "wrong_bit": (0, ("apply_wstrb(m2_full_block_input_vector_o[0 +: 32], wdata_q, wstrb_q)", "apply_wstrb(m2_full_block_input_vector_o[0 +: 32], wdata_q ^ 32'h10, wstrb_q)")),
            "wrong_strobe": (0, ("apply_wstrb(m2_full_block_residual_vector_o[0 +: 32], wdata_q, wstrb_q)", "apply_wstrb(m2_full_block_residual_vector_o[0 +: 32], wdata_q, {wstrb_q[2:0],wstrb_q[3]})")),
            "wrong_compensation": (1, ("if (M2_INPUT_PCIE7X_ROR64_COMPENSATE != 0)", "if (M2_INPUT_PCIE7X_ROR64_COMPENSATE == 0)")),
            "delayed_update": (0, ("m2_full_block_input_vector_o[0 +: 32] <= apply_wstrb", "m2_full_block_input_vector_o[0 +: 32] <= #11 apply_wstrb")),
        }
        for name, (mode, mutation) in mutations.items():
            with self.subTest(mutation=name):
                result = self.simulate(mode, mutation)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("zero-offset", result.stdout)


if __name__ == "__main__":
    unittest.main()
