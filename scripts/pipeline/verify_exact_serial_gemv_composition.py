#!/usr/bin/env python3
"""Write/verify provenance for the compiler-owned 49-callsite Calyx wrapper."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
COMPOSER=ROOT/"scripts/pipeline/compose_exact_serial_gemv_calyx.py"
SSA_OPERATION_RE = re.compile(r'^\s*(?:%[-A-Za-z0-9_.$]+(?:\s*,\s*%[-A-Za-z0-9_.$]+)*)\s*=\s*(?:"([^"]+)"|([A-Za-z_][-A-Za-z0-9_.$]*(?:\.[-A-Za-z0-9_.$]+)*))', re.MULTILINE)
def bind(p):
 d=p.read_bytes();return {"name":p.name,"bytes":len(d),"sha256":hashlib.sha256(d).hexdigest()}
def canonical(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def source_operation_counts(torch_text):
 counts={}
 for match in SSA_OPERATION_RE.finditer(torch_text):
  name=match.group(1) or match.group(2)
  counts[name]=counts.get(name,0)+1
 return dict(sorted(counts.items()))
def coverage_fields(torch_text):
 counts=source_operation_counts(torch_text)
 retained={"llm2fpga.serial_gemv": counts.get("llm2fpga.serial_gemv",0)}
 dropped={name:count for name,count in counts.items() if name not in retained}
 return {"source_operation_counts":counts,"retained_source_operation_counts":retained,
         "dropped_source_operation_counts":dropped,
         "dropped_source_operation_count":sum(dropped.values())}
def verify_map(torch,map_):
 s=importlib.util.spec_from_file_location("exact_serial_composer",COMPOSER);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
 actual=json.loads(map_.read_text());_,expected=m.compose(torch.read_text())
 if actual!=expected:raise ValueError("callsite map does not exactly match authenticated Torch MLIR")
 return actual
def diagnostic(torch,map_,calyx,graph=None):
 m=verify_map(torch,map_);text=calyx.read_text()
 if m.get("callsite_count")!=49 or len(m.get("callsites",[]))!=49:raise ValueError("composition map does not bind 49 callsites")
 if text.count("calyx.invoke @call_")!=49:raise ValueError("composition does not emit 49 ordered invokes")
 if "scf.for" in text or "TinyStories/rtl" in text:raise ValueError("composition scope violation")
 if len(m.get("component_shapes",[]))!=4:raise ValueError("composition must reuse four exact shape components")
 if "call_0_activation" not in text:raise ValueError("expected independent-memory diagnostic evidence absent")
 v={"schema":"llm2fpga-exact-serial-gemv-composition-v1","status":"diagnostic","diagnostic":"49 independent boundary memories do not preserve Torch SSA or non-GEMV dataflow","input_torch":bind(torch),"callsite_map":bind(map_),"calyx":bind(calyx),"callsite_count":49,"invoke_count":49,**coverage_fields(torch.read_text())}
 if graph is not None:
  document=json.loads(graph.read_text()); expected=coverage_fields(torch.read_text())["source_operation_counts"]
  if document.get("operation_counts") != expected: raise ValueError("SSA graph operation counts do not match authenticated Torch MLIR")
  v["ssa_graph"]={**bind(graph),"graph_sha256":document.get("graph_sha256"),"node_count":document.get("node_count"),"edge_count":document.get("edge_count")}
 v["receipt_sha256"]=canonical(v);return v
def build(torch,map_,calyx,sv,yosys,commands=None,tools=None,elapsed=None,graph=None):
 m=verify_map(torch,map_);text=calyx.read_text()
 if m.get("callsite_count")!=49 or len(m.get("callsites",[]))!=49: raise ValueError("composition map does not bind 49 callsites")
 if text.count("calyx.invoke @call_")!=49: raise ValueError("composition does not emit 49 ordered invokes")
 if "scf.for" in text or "TinyStories/rtl" in text: raise ValueError("composition scope violation")
 if len(m.get("component_shapes",[]))!=4: raise ValueError("composition must reuse four exact shape components")
 v={"schema":"llm2fpga-exact-serial-gemv-composition-v1","status":"diagnostic","diagnostic":"49 independent boundary memories do not preserve Torch SSA or non-GEMV dataflow","input_torch":bind(torch),"callsite_map":bind(map_),"calyx":bind(calyx),"sv":bind(sv),"yosys":bind(yosys),"callsite_count":49,"invoke_count":49,**coverage_fields(torch.read_text())}
 if graph is not None:
  document=json.loads(graph.read_text()); expected=coverage_fields(torch.read_text())["source_operation_counts"]
  if document.get("operation_counts") != expected: raise ValueError("SSA graph operation counts do not match authenticated Torch MLIR")
  v["ssa_graph"]={**bind(graph),"graph_sha256":document.get("graph_sha256"),"node_count":document.get("node_count"),"edge_count":document.get("edge_count")}
 if commands is not None: v["commands"]=bind(commands)
 if tools is not None: v["tools"]=bind(tools)
 if elapsed is not None: v["elapsed"]=bind(elapsed)
 v["receipt_sha256"]=canonical(v);return v
def main():
 p=argparse.ArgumentParser();p.add_argument("action",choices=("write","verify","diagnose"));
 for n in ("torch","map","calyx","receipt"):p.add_argument("--"+n,type=Path,required=True)
 for n in ("sv","yosys"):p.add_argument("--"+n,type=Path)
 for n in ("commands","tools","elapsed","graph"):p.add_argument("--"+n,type=Path)
 a=p.parse_args()
 if a.action=="diagnose":v=diagnostic(a.torch,a.map,a.calyx,a.graph);a.receipt.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n")
 else:
  if a.sv is None or a.yosys is None:raise ValueError("write/verify require SV and Yosys inputs")
  v=build(a.torch,a.map,a.calyx,a.sv,a.yosys,a.commands,a.tools,a.elapsed,a.graph)
  if a.action=="write":a.receipt.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n")
 actual=json.loads(a.receipt.read_text())
 if actual!=v:raise ValueError("composition receipt mismatch")
 print(json.dumps({"status":"verified","receipt_sha256":v["receipt_sha256"]}))
if __name__=="__main__":main()
