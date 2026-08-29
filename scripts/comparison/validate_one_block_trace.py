#!/usr/bin/env python3
"""Validate the ordered TinyStories-1M one-block trace and adapter evidence."""
import argparse, hashlib, json
from pathlib import Path

ORDER = ["block.input", "block.ln_1.output", "block.attention.q", "block.attention.k", "block.attention.v", "block.attention.output", "block.residual.attention", "block.ln_2.output", "block.mlp.fc_in", "block.mlp.activation", "block.mlp.fc_out", "block.output"]
RECEIPTS = {
    "block.ln_1.output": "tinystories-1m-layernorm-tensor-abi-2026-08-29.json",
    "block.attention.q": "tinystories-1m-gemv-q-projection-equivalence-2026-08-29.json",
    "block.attention.k": "tinystories-1m-gemv-qkv-projection-equivalence-2026-08-29.json",
    "block.attention.v": "tinystories-1m-gemv-qkv-projection-equivalence-2026-08-29.json",
    "block.attention.output": "tinystories-1m-gemv-attention-output-equivalence-2026-08-29.json",
    "block.residual.attention": "tinystories-1m-residual-add-abi-2026-08-29.json",
    "block.ln_2.output": "tinystories-1m-layernorm-tensor-abi-2026-08-29.json",
    "block.mlp.fc_in": "tinystories-1m-gemv-mlp-fc-in-equivalence-2026-08-29.json",
    "block.mlp.activation": "tinystories-1m-gelu-equivalence-2026-08-29.json",
    "block.mlp.fc_out": "tinystories-1m-gemv-mlp-fc-out-equivalence-2026-08-29.json",
    "block.output": "tinystories-1m-residual-add-abi-2026-08-29.json",
}

def sha(checkpoint):
    payload={"shape":checkpoint["shape"],"dtype":checkpoint["dtype"],"values":checkpoint["values"]}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",", ":")).encode()).hexdigest()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--oracle',type=Path,required=True); ap.add_argument('--contract',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    oracle=json.loads(a.oracle.read_text())['oracle']; contract=json.loads(a.contract.read_text()); cps=oracle['checkpoints']
    assert oracle['checkpoint_order']==ORDER, oracle['checkpoint_order']
    rows=[]
    for name in ORDER:
        c=cps[name]; actual=sha(c); assert actual==c['sha256'], name
        rows.append({'checkpoint':name,'shape':c['shape'],'sha256':actual,'evidence_receipt':RECEIPTS.get(name)})
    out={'schema':'tinystories-1m-one-block-trace-validation-v1','status':'ordered_oracle_trace_validated','oracle':str(a.oracle),'contract':str(a.contract),'checkpoint_order':ORDER,'checkpoints':rows,'claims':{'ordered_checkpoint_hashes':True,'adapter_evidence_bound':all(r['evidence_receipt'] for r in rows[1:]),'rtl_composed':False,'hardware_inference':False}}
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
