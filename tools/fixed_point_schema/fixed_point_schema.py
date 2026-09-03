#!/usr/bin/env python3
"""Out-of-tree structural generic-MLIR fixed-point schema pass plugin."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
from typing import Any
import torch

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from TinyStories.model_adapter_exact_package import Q_SCALE,Q_VALUE,activation_qdq,round_shift_signed,serial_gemv
PASS_NAME="llm2fpga-fixed-point-gemv-requantize-schema";SCHEMA="llm2fpga-fixed-point-gemv-requantize-schema-v3"
TEMPLATE='''module {\n  %activation = "fixed.fixture_input"() : () -> tensor<4x64xi64>\n  %input_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>\n  %weight = "fixed.fixture_weight"() : () -> tensor<64x64xi64>\n  %weight_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>\n}'''
NEEDED=("%activation = \"fixed.fixture_input\"","%input_scale = \"fixed.fixture_scale\"","%weight = \"fixed.fixture_weight\"","%weight_scale = \"fixed.fixture_scale\"")
RAW=("activation_codes_i8","input_scale_q8_24","activation_q16_16","weight_codes_i8","weight_scale_q8_24","gemv_accumulator_i64","output_scale_q8_24","requantized_codes_i8","requantized_q16_16")

def canonical(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _capture():
 p=ROOT/"TinyStories/capture_fixed_point_gemv_requantize_slice.py";s=importlib.util.spec_from_file_location("slice_capture",p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def fixture(p):
 c=_capture();c.verify_fixture(p);c.verify_eager_replay(p);return json.loads(p.read_text())
def tensor(v,n): return torch.tensor(v["tensors"][n]["values"],dtype=torch.int64)
def raw(v): return {n:{k:v["tensors"][n][k] for k in ("little_endian_int64_sha256","bytes")} for n in RAW}
def outputs(v): return {n:raw(v)[n] for n in ("gemv_accumulator_i64","requantized_codes_i8","requantized_q16_16")}
def attrs(v): return {"fixture_sha256":v["receipt_sha256"],"scale_sha256":v["tensors"]["output_scale_q8_24"]["little_endian_int64_sha256"],"rounding":"nearest_ties_away_from_zero","signedness":"signed","saturation":[-128,127],"width":8}
def contract(v): return {"pass":PASS_NAME,"fixture":v["receipt_sha256"],"raw":raw(v),"requantize":attrs(v),"logical_ssa":["%activation","%input_scale","%weight","%weight_scale","%acc","%output_scale","%result"]}
def validate_input(text):
 if not all(x in text for x in NEEDED): raise ValueError("incoming MLIR lacks required logical SSA fixture operands")
 if "fixed.requantize" in text: raise ValueError("incoming MLIR must not pre-contain fixed.requantize")
def producer(v,ssa,name,op,typ):
 r=v["tensors"][name]
 return f'  {ssa} = "{op}"() {{fixture_sha256 = "{v["receipt_sha256"]}", tensor = "{name}", raw_sha256 = "{r["little_endian_int64_sha256"]}", raw_bytes = {r["bytes"]} : i64}} : () -> {typ}'
def emit(v,incoming):
 validate_input(incoming);a=attrs(v);h=canonical(contract(v))
 lines=["module {",producer(v,"%activation","activation_q16_16","fixed.fixture_input","tensor<4x64xi64>"),producer(v,"%input_scale","input_scale_q8_24","fixed.fixture_scale","tensor<64xi64>"),producer(v,"%weight","weight_codes_i8","fixed.fixture_weight","tensor<64x64xi64>"),producer(v,"%weight_scale","weight_scale_q8_24","fixed.fixture_scale","tensor<64xi64>"),'  %acc = "fixed.gemv"(%activation, %input_scale, %weight, %weight_scale) {rows = 4 : i64, inputs = 64 : i64, outputs = 64 : i64, accumulator = "signed_i64_twos_complement_wrap"} : (tensor<4x64xi64>, tensor<64xi64>, tensor<64x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>',producer(v,"%output_scale","output_scale_q8_24","fixed.fixture_scale","tensor<64xi64>")]
 lines.append(f'  %result = "fixed.requantize"(%acc, %output_scale) {{fixture_sha256 = "{a["fixture_sha256"]}", scale_sha256 = "{a["scale_sha256"]}", rounding = "{a["rounding"]}", signedness = "{a["signedness"]}", saturation = [-128, 127], width = 8 : i64, contract_sha256 = "{h}"}} : (tensor<4x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>');return "\n".join(lines+["}",""])

# A small structural parser for this supported one-line generic MLIR subset.
def _split_attrs(text):
 out=[];depth=0;quoted=False;start=0
 for i,ch in enumerate(text):
  if ch=='"': quoted=not quoted
  elif not quoted and ch=='[': depth+=1
  elif not quoted and ch==']': depth-=1
  elif ch==',' and not quoted and depth==0: out.append(text[start:i].strip());start=i+1
 out.append(text[start:].strip());return out
def _atom(value):
 value=value.strip()
 if value.startswith('"') and value.endswith('"'): return value[1:-1]
 if value.startswith('[') and value.endswith(']'): return [int(x.strip()) for x in value[1:-1].split(',')]
 return int(value.split()[0])
def parse_mlir(text):
 ops={}
 for line in text.splitlines():
  line=line.strip()
  if not line.startswith('%'): continue
  if ' = "' not in line: raise ValueError("unsupported generic MLIR operation form")
  result,rhs=line.split(' = ',1);op_end=rhs.find('"',1)
  if not rhs.startswith('"') or op_end<1: raise ValueError("generic MLIR operation name malformed")
  op=rhs[1:op_end];open_paren=rhs.find('(',op_end);close_paren=rhs.find(')',open_paren)
  if open_paren<0 or close_paren<0: raise ValueError("generic MLIR operand list malformed")
  operands=[x.strip() for x in rhs[open_paren+1:close_paren].split(',') if x.strip()]
  attrs={};brace=rhs.find('{',close_paren)
  if brace>=0:
   end=rhs.find('}',brace)
   if end<0: raise ValueError("generic MLIR attribute dictionary malformed")
   for item in _split_attrs(rhs[brace+1:end]):
    if ' = ' not in item: raise ValueError("generic MLIR attribute malformed")
    key,value=item.split(' = ',1);attrs[key.strip()]=_atom(value)
  ops[result]={"op":op,"operands":operands,"attrs":attrs}
 return ops
def _check_producer(ops,ssa,name,v):
 op=ops.get(ssa);want=v["tensors"][name]
 if not op or op["op"] not in ("fixed.fixture_input","fixed.fixture_scale","fixed.fixture_weight"): raise ValueError("fixture producer definition missing")
 expected={"fixture_sha256":v["receipt_sha256"],"tensor":name,"raw_sha256":want["little_endian_int64_sha256"],"raw_bytes":want["bytes"]}
 if op["attrs"]!=expected: raise ValueError("fixture producer binding mismatch")

def evaluate_schema(schema,p):
 v=fixture(p);codes,_=activation_qdq(tensor(v,"activation_q16_16"),tensor(v,"input_scale_q8_24"));acc=serial_gemv(codes*tensor(v,"input_scale_q8_24"),tensor(v,"weight_codes_i8"));real=round_shift_signed(acc*tensor(v,"weight_scale_q8_24"),2*Q_SCALE-Q_VALUE);out,q16=activation_qdq(real,tensor(v,"output_scale_q8_24"))
 def h(x):
  b=x.contiguous().to(torch.int64).numpy().astype("<i8",copy=False).tobytes();return {"little_endian_int64_sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b)}
 return {"gemv_accumulator_i64":h(acc),"requantized_codes_i8":h(out),"requantized_q16_16":h(q16)}
def fixture_output_hashes(p): return outputs(fixture(p))
def build_schema(p,incoming=TEMPLATE):
 v=fixture(p);mlir=emit(v,incoming);x={"schema":SCHEMA,"pass_name":PASS_NAME,"fixture_receipt_sha256":v["receipt_sha256"],"raw_tensor_hashes":raw(v),"requantize":attrs(v),"mlir":mlir,"expected_output_hashes":outputs(v)};x["receipt_sha256"]=canonical(x);return x
def verify_schema(x,p):
 v=fixture(p);ops=parse_mlir(x.get("mlir",""));rq=ops.get("%result")
 if not rq or rq["op"]!="fixed.requantize" or rq["operands"]!=["%acc","%output_scale"]: raise ValueError("requantize logical operand trace mismatch")
 for ssa,name in (("%activation","activation_q16_16"),("%input_scale","input_scale_q8_24"),("%weight","weight_codes_i8"),("%weight_scale","weight_scale_q8_24"),("%output_scale","output_scale_q8_24")): _check_producer(ops,ssa,name,v)
 if x.get("schema")!=SCHEMA or x.get("pass_name")!=PASS_NAME or x.get("fixture_receipt_sha256")!=v["receipt_sha256"]: raise ValueError("schema fixture authority mismatch")
 if x.get("requantize")!=attrs(v) or {k:rq["attrs"].get(k) for k in attrs(v)}!=attrs(v): raise ValueError("requantize attributes mismatch")
 if rq["attrs"].get("contract_sha256")!=canonical(contract(v)): raise ValueError("recomputed self-hash attribute mismatch")
 if x.get("receipt_sha256")!=canonical({k:y for k,y in x.items() if k!="receipt_sha256"}): raise ValueError("schema self-hash mismatch")
 if x.get("raw_tensor_hashes")!=raw(v) or evaluate_schema(x,p)!=outputs(v): raise ValueError("raw tensor/schema evaluation hash mismatch")
def main():
 q=argparse.ArgumentParser();q.add_argument("--fixture",type=Path,required=True);q.add_argument("--input",type=Path,required=True);q.add_argument("--output",type=Path,required=True);q.add_argument("--receipt",type=Path,required=True);q.add_argument("--verify",action="store_true");a=q.parse_args()
 if a.verify: verify_schema(json.loads(a.receipt.read_text()),a.fixture)
 else:
  x=build_schema(a.fixture,a.input.read_text());a.output.write_text(x["mlir"]);a.receipt.write_text(json.dumps(x,indent=2,sort_keys=True)+"\n")
if __name__=="__main__": main()
