#!/usr/bin/env python3
"""Write/verify provenance for the compiler-owned 49-callsite Calyx wrapper."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
def bind(p):
 d=p.read_bytes();return {"name":p.name,"bytes":len(d),"sha256":hashlib.sha256(d).hexdigest()}
def canonical(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def build(torch,map_,calyx,sv,yosys):
 m=json.loads(map_.read_text()); text=calyx.read_text()
 if m.get("callsite_count")!=49 or len(m.get("callsites",[]))!=49: raise ValueError("composition map does not bind 49 callsites")
 if text.count("calyx.invoke @call_")!=49: raise ValueError("composition does not emit 49 ordered invokes")
 if "scf.for" in text or "TinyStories/rtl" in text: raise ValueError("composition scope violation")
 if len(m.get("component_shapes",[]))!=4: raise ValueError("composition must reuse four exact shape components")
 v={"schema":"llm2fpga-exact-serial-gemv-composition-v1","input_torch":bind(torch),"callsite_map":bind(map_),"calyx":bind(calyx),"sv":bind(sv),"yosys":bind(yosys),"callsite_count":49,"invoke_count":49}
 v["receipt_sha256"]=canonical(v);return v
def main():
 p=argparse.ArgumentParser();p.add_argument("action",choices=("write","verify"));
 for n in ("torch","map","calyx","sv","yosys","receipt"):p.add_argument("--"+n,type=Path,required=True)
 a=p.parse_args();v=build(a.torch,a.map,a.calyx,a.sv,a.yosys)
 if a.action=="write":a.receipt.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n")
 actual=json.loads(a.receipt.read_text())
 if actual!=v:raise ValueError("composition receipt mismatch")
 print(json.dumps({"status":"verified","receipt_sha256":v["receipt_sha256"]}))
if __name__=="__main__":main()
