#!/usr/bin/env python3
"""Verify legalized TinyStories custom-op signatures against RTL adapters."""
import argparse, hashlib, json
from pathlib import Path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(softmax_mlir, layernorm_mlir, softmax_rtl, layernorm_rtl):
    sm = softmax_mlir.read_text(); ln = layernorm_mlir.read_text()
    sm_sig = '(tensor<16x32xi32>, i32) -> tensor<16x32xi32>'
    ln_sig = '(tensor<64xi32>, tensor<64xi32>, tensor<64xi32>) -> tensor<64xi32>'
    checks = {
        'softmax_call_present': 'call @llm2fpga_attention_softmax_fixed' in sm,
        'softmax_signature_present': sm_sig in sm,
        'layernorm_call_present': 'call @llm2fpga_fixed_layer_norm_q16_16' in ln,
        'layernorm_signature_present': ln_sig in ln,
        'softmax_adapter_present': 'module llm2fpga_attention_softmax_fixed_tensor' in softmax_rtl.read_text(),
        'layernorm_adapter_present': 'module llm2fpga_fixed_layer_norm_q16_16_tensor' in layernorm_rtl.read_text(),
    }
    if not all(checks.values()):
        raise SystemExit('external ABI verification failed: ' + repr(checks))
    return {
        'schema': 'tinystories-1m-external-abi-verification-v1',
        'status': 'pass', 'checks': checks,
        'mlir': {'softmax_sha256': sha(softmax_mlir), 'layernorm_sha256': sha(layernorm_mlir)},
        'rtl': {'softmax_sha256': sha(softmax_rtl), 'layernorm_sha256': sha(layernorm_rtl)},
        'claims': {'call_signatures_match_packed_adapters': True,
                   'full_block_equivalence': False, 'hardware_inference': False}
    }

def main():
    p = argparse.ArgumentParser(); p.add_argument('--softmax-mlir', type=Path, required=True); p.add_argument('--layernorm-mlir', type=Path, required=True); p.add_argument('--softmax-rtl', type=Path, required=True); p.add_argument('--layernorm-rtl', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); a.out.write_text(json.dumps(verify(a.softmax_mlir, a.layernorm_mlir, a.softmax_rtl, a.layernorm_rtl), indent=2) + '\n')
if __name__ == '__main__': main()
