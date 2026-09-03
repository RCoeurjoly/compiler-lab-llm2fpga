from __future__ import annotations
import importlib.util, json, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/pipeline/compose_exact_serial_gemv_calyx.py"
VERIFIER=ROOT/"scripts/pipeline/verify_exact_serial_gemv_composition.py"
TORCH=Path("/nix/store/dww9gbfpcyp3pfm6ajn2miv38g03jjgz-tiny-stories-1m-kev-gpt-exact-serial-gemv-successor-torch.mlir")
def load():
 s=importlib.util.spec_from_file_location("compose_exact",SCRIPT); m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def load_verifier():
 s=importlib.util.spec_from_file_location("verify_composition",VERIFIER); m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
class CompositionTest(unittest.TestCase):
 def test_exact_49_callsite_map_and_invokes(self):
  if not TORCH.is_file(): self.skipTest("portable Torch artifact unavailable")
  mlir,mapping=load().compose(TORCH.read_text())
  self.assertEqual(mapping["callsite_count"],49);self.assertEqual(mlir.count("calyx.invoke @call_"),49)
  self.assertEqual({(x["outputs"],x["inputs"]) for x in mapping["component_shapes"]},{(64,64),(256,64),(64,256),(50257,64)})
  self.assertNotIn("scf.for",mlir);self.assertNotIn("TinyStories/rtl",mlir)
 def test_missing_or_mutated_boundary_is_rejected(self):
  if not TORCH.is_file(): self.skipTest("portable Torch artifact unavailable")
  text=TORCH.read_text();m=load()
  with self.assertRaisesRegex(ValueError,"expected 49"):
   m.compose(text.replace('"llm2fpga.serial_gemv"','"llm2fpga.not_gemv"',1))
 def test_four_gate_map_cannot_claim_49_torch_composition(self):
  if not TORCH.is_file(): self.skipTest("portable Torch artifact unavailable")
  mlir,mapping=load().compose(TORCH.read_text())
  mapping["callsite_count"]=4
  with tempfile.TemporaryDirectory() as directory:
   directory=Path(directory); map_=directory/"callsites.json"; calyx=directory/"model.mlir"
   sv=directory/"model.sv"; yosys=directory/"yosys.txt"
   map_.write_text(json.dumps(mapping));calyx.write_text(mlir);sv.write_text("module top; endmodule\n");yosys.write_text("ok\n")
   with self.assertRaisesRegex(ValueError,"49 callsites"):
    load_verifier().build(TORCH,map_,calyx,sv,yosys)
if __name__=="__main__":unittest.main()
