#!/usr/bin/env python3
"""Materialize the authenticated full-block software oracle from Q/DQ evidence."""
import argparse, hashlib, json
from pathlib import Path

def main():
    p = argparse.ArgumentParser(); p.add_argument('--input', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); source = json.loads(a.input.read_text()); oracle = source.get('candidate_oracle')
    if not isinstance(oracle, dict) or oracle.get('status') != 'runtime_authenticated_not_board_checkpoint_authenticated':
        raise SystemExit('candidate oracle is missing or not runtime-authenticated')
    result = {'schema': 'tinystories-1m-candidate-oracle-v1', 'source_receipt_sha256': hashlib.sha256(a.input.read_bytes()).hexdigest(), 'oracle': oracle, 'claims': {'software_checkpoint_oracle': True, 'board_authenticated': False, 'compiler_equivalence': False}}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')

if __name__ == '__main__': main()
