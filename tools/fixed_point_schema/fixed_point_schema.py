#!/usr/bin/env python3
"""Out-of-tree textual generic-MLIR fixed-point schema pass plugin."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path
from typing import Any
import torch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from TinyStories.model_adapter_exact_package import Q_SCALE,Q_VALUE,activation_qdq,round_shift_signed,serial_gemv
PASS_NAME="llm2fpga-fixed-point-gemv-requantize-schema";SCHEMA="llm2fpga-fixed-point-gemv-requantize-schema-v2"
TEMPLATE='''module {\n  %activation = "fixed.fixture_input"() : () -> tensor<4x64xi64>\n  %input_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>\n  %weight = "fixed.fixture_weight"() : () -> tensor<64x64xi64>\n  %weight_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>\n}'''
NEEDED=("%activation = \"fixed.fixture_input\"","%input_scale = \"fixed.fixture_scale\"","%weight = \"fixed.fixture_weight\"","%weight_scale = \"fixed.fixture_scale\"")
RAW=("activation_codes_i8","input_scale_q8_24","activation_q16_16","weight_codes_i8","weight_scale_q8_24","gemv_accumulator_i64","output_scale_q8_24","requantized_codes_i8","requantized_q16_16")
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def capture():
 p=ROOT/"TinyStories/capture_fixed_point_gemv_requantize_slice.py";s=importlib.util.spec_from_file_location("slice_capture",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def fixture(p):
 c=capture();c.verify_fixture(p);c.verify_eager_replay(p);return json.loads(p.read_text())
def tensor(v,n):return torch.tensor(v["tensors"][n]["values"],dtype=torch.int64)
def raw(v):return {n:{k:v["tensors"][n][k] for k in ("little_endian_int64_sha256","bytes")} for n in RAW}
def outputs(v):return {n:raw(v)[n] for n in ("gemv_accumulator_i64","requantized_codes_i8","requantized_q16_16")}
def attrs(v):return {"fixture_sha256":v["receipt_sha256"],"scale_sha256":v["tensors"]["output_scale_q8_24"]["little_endian_int64_sha256"],"rounding":"nearest_ties_away_from_zero","signedness":"signed","saturation":[-128,127],"width":8}
def contract(v):return {"pass":PASS_NAME,"fixture":v["receipt_sha256"],"raw":raw(v),"requantize":attrs(v),"logical_ssa":["%activation","%input_scale","%weight","%weight_scale","%acc","%output_scale","%result"]}
def validate_input(s):
 if not all(x in s for x in NEEDED):raise ValueError("incoming MLIR lacks required logical SSA fixture operands")
 if "fixed.requantize" in s:raise ValueError("incoming MLIR must not pre-contain fixed.requantize")
def emit(v,incoming):
 validate_input(incoming);a=attrs(v);h=canonical(contract(v))
 return incoming.rstrip()[:-1]+f'''  %acc = "fixed.gemv"(%activation, %input_scale, %weight, %weight_scale) {{rows = 4 : i64, inputs = 64 : i64, outputs = 64 : i64, accumulator = "signed_i64_twos_complement_wrap"}} : (tensor<4x64xi64>, tensor<64xi64>, tensor<64x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>
  %output_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %result = "fixed.requantize"(%acc, %output_scale) {{fixture_sha256 = "{a['fixture_sha256']}", scale_sha256 = "{a['scale_sha256']}", rounding = "{a['rounding']}", signedness = "{a['signedness']}", saturation = [-128, 127], width = 8 : i64, contract_sha256 = "{h}"}} : (tensor<4x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>
}}\n'''
def parse(mlir):
 m=re.search(r'"fixed\.requantize"\(%acc, %output_scale\) \{(.*?)\}',mlir,re.S)
 if not m:raise ValueError("emitted MLIR lacks fixed.requantize logical scale operand")
 a=m.group(1);get=lambda n:re.search(rf'\b{n} = "([0-9a-z_\-]+)"',a)
 vals=[get(n) for n in ("fixture_sha256","scale_sha256","rounding","signedness","contract_sha256")];w=re.search(r'\bwidth = (\d+) : i64',a);sat=re.search(r'\bsaturation = \[(-?\d+), (-?\d+)\]',a)
 if not all(vals) or not w or not sat:raise ValueError("fixed.requantize attributes missing")
 return {"fixture_sha256":vals[0].group(1),"scale_sha256":vals[1].group(1),"rounding":vals[2].group(1),"signedness":vals[3].group(1),"saturation":[int(sat.group(1)),int(sat.group(2))],"width":int(w.group(1)),"contract_sha256":vals[4].group(1)}
def evaluate_schema(schema,fixture_path):
 v=fixture(fixture_path);codes,_=activation_qdq(tensor(v,"activation_q16_16"),tensor(v,"input_scale_q8_24"));acc=serial_gemv(codes*tensor(v,"input_scale_q8_24"),tensor(v,"weight_codes_i8"));real=round_shift_signed(acc*tensor(v,"weight_scale_q8_24"),2*Q_SCALE-Q_VALUE);out,q16=activation_qdq(real,tensor(v,"output_scale_q8_24"))
 def h(x):
  b=x.contiguous().to(torch.int64).numpy().astype("<i8",copy=False).tobytes();return {"little_endian_int64_sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b)}
 return {"gemv_accumulator_i64":h(acc),"requantized_codes_i8":h(out),"requantized_q16_16":h(q16)}
def fixture_output_hashes(p):return outputs(fixture(p))
def build_schema(p,incoming=TEMPLATE):
 v=fixture(p);mlir=emit(v,incoming);x={"schema":SCHEMA,"pass_name":PASS_NAME,"fixture_receipt_sha256":v["receipt_sha256"],"raw_tensor_hashes":raw(v),"requantize":attrs(v),"mlir":mlir,"expected_output_hashes":outputs(v)};x["receipt_sha256"]=canonical(x);return x
def verify_schema(x,p):
 v=fixture(p);a=parse(x.get("mlir",""));need=attrs(v)
 if x.get("schema")!=SCHEMA or x.get("pass_name")!=PASS_NAME or x.get("fixture_receipt_sha256")!=v["receipt_sha256"]:raise ValueError("schema fixture authority mismatch")
 if x.get("requantize")!=need or {k:a[k] for k in need}!=need:raise ValueError("requantize attributes mismatch")
 if a["contract_sha256"]!=canonical(contract(v)):raise ValueError("recomputed self-hash attribute mismatch")
 if x.get("receipt_sha256")!=canonical({k:y for k,y in x.items() if k!="receipt_sha256"}):raise ValueError("schema self-hash mismatch")
 if x.get("raw_tensor_hashes")!=raw(v) or evaluate_schema(x,p)!=outputs(v):raise ValueError("raw tensor/schema evaluation hash mismatch")
def main():
 q=argparse.ArgumentParser();q.add_argument("--fixture",type=Path,required=True);q.add_argument("--input",type=Path,required=True);q.add_argument("--output",type=Path,required=True);q.add_argument("--receipt",type=Path,required=True);q.add_argument("--verify",action="store_true");a=q.parse_args()
 if a.verify:verify_schema(json.loads(a.receipt.read_text()),a.fixture)
 else:
  x=build_schema(a.fixture,a.input.read_text());a.output.write_text(x["mlir"]);a.receipt.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
