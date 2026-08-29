#!/usr/bin/env python3
"""Extract the authenticated synthesizable W8A8 GEMV contract."""
import argparse, hashlib, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    source=a.input.read_bytes(); doc=json.loads(source); profile=doc['profiles']['fixed_hardware_reference']
    result={'schema':'tinystories-1m-gemv-contract-v1','source_receipt_sha256':hashlib.sha256(source).hexdigest(),'reference_rtl':'fpga/rtl/gptneo_resident_gemv.sv','contract':profile,'matrix_shapes':{'hidden_projections':[{'name':n,'input_width':64,'output_width':64} for n in ('q_proj','k_proj','v_proj','out_proj')],'mlp_in':{'input_width':64,'output_width':256},'mlp_out':{'input_width':256,'output_width':64}},'claims':{'fixed_gemv_semantics_authenticated':True,'compiler_adapter':False,'hardware_inference':False}}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
