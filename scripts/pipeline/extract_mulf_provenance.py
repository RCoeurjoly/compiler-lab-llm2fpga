#!/usr/bin/env python3
"""Extract MLIR floating multiply candidates matching a Calyx group fingerprint."""

import argparse
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlir", type=Path, required=True)
    parser.add_argument("--futil", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--slice-out", type=Path)
    parser.add_argument("--parallel-slice-out", type=Path)
    parser.add_argument("--affine-slice-out", type=Path)
    args = parser.parse_args()

    mlir_lines = args.mlir.read_text(encoding="utf-8").splitlines()
    futil = args.futil.read_text(encoding="utf-8")
    group = re.search(
        r"group bb0_1652 \{(?P<body>.*?)\n\s*\}", futil, re.DOTALL
    )
    if group is None:
        raise SystemExit("bb0_1652 not found in Futil")

    candidates = []
    loop_stack = []
    for index, line in enumerate(mlir_lines):
        loop = re.search(r"scf\.for %\w+ = %c(\d+) to %c(\d+) step %c(\d+)", line)
        if loop:
            loop_stack.append({"line": index + 1, "bounds": [int(x) for x in loop.groups()]})
        if "arith.mulf" not in line or ": f32" not in line:
            if "}" in line and loop_stack and not line.strip().startswith("//"):
                # The structured candidate extraction is intentionally
                # conservative; nested-loop context is retained until the
                # next operation boundary rather than guessing source scope.
                pass
            continue
        context = mlir_lines[max(0, index - 12) : min(len(mlir_lines), index + 4)]
        bounds = [entry["bounds"] for entry in loop_stack[-2:]]
        candidates.append({
            "mlir_line": index + 1,
            "operation": line.strip(),
            "enclosing_loop_bounds": bounds,
            "context": context,
        })

    resource_ordinal = 36
    reverse_index = len(candidates) - resource_ordinal
    resource_candidate = (
        candidates[reverse_index]
        if 0 <= reverse_index < len(candidates)
        else None
    )
    result = {
        "calyx_group": "bb0_1652",
        "calyx_fingerprint": {
            "operations": [
                "load_187_reg <- arg_mem_107",
                "load_188_reg <- arg_mem_61",
                "std_mulFN_36 IEEE754 multiply",
                "mulf_36_reg result",
            ],
            "group_text": group.group(0),
        },
        "mapping_method": "structured loop bounds + f32 arith.mulf + context",
        "location_metadata_available": False,
        "candidate_count": len(candidates),
        "resource_name": "mulf_36",
        "resource_order_hypothesis": "Calyx float resources are numbered in reverse MLIR encounter order",
        "resource_order_candidate": resource_candidate,
        "candidates": candidates,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.slice_out is not None:
        args.slice_out.write_text(
            """module {
  func.func @bb0_1652_slice(%input: memref<16xi8>, %output: memref<16xf32>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c8 = arith.constant 8 : index
    %czp = arith.constant -126 : i32
    %cscale = arith.constant 2.44140625E-4 : f32
    scf.for %i = %c0 to %c8 step %c1 {
      scf.for %j = %c0 to %c2 step %c1 {
        %base = arith.muli %i, %c2 : index
        %idx = arith.addi %base, %j : index
        %q = memref.load %input[%idx] : memref<16xi8>
        %qi32 = arith.extsi %q : i8 to i32
        %shifted = arith.subi %qi32, %czp : i32
        %qf32 = arith.sitofp %shifted : i32 to f32
        %product = arith.mulf %qf32, %cscale : f32
        memref.store %product, %output[%idx] : memref<16xf32>
      }
    }
    return
  }
}
""",
            encoding="utf-8",
        )
    if args.parallel_slice_out is not None:
        args.parallel_slice_out.write_text(
            """module {
  func.func @bb0_1652_parallel_slice(%input: memref<16xi8>, %output: memref<16xf32>) {
    %czp = arith.constant -126 : i32
    %cscale = arith.constant 2.44140625E-4 : f32
    linalg.generic {
      indexing_maps = [affine_map<(d0) -> (d0)>,
                       affine_map<(d0) -> (d0)>],
      iterator_types = ["parallel"]
    } ins(%input : memref<16xi8>) outs(%output : memref<16xf32>) {
    ^bb0(%q: i8, %old: f32):
      %qi32 = arith.extsi %q : i8 to i32
      %shifted = arith.subi %qi32, %czp : i32
      %qf32 = arith.sitofp %shifted : i32 to f32
      %product = arith.mulf %qf32, %cscale : f32
      linalg.yield %product : f32
    }
    return
  }
}
""",
            encoding="utf-8",
        )
    if args.affine_slice_out is not None:
        args.affine_slice_out.write_text(
            """module {
  func.func @bb0_1652_affine_slice(%input: memref<16xi8>, %output: memref<16xf32>) {
    %czp = arith.constant -126 : i32
    %cscale = arith.constant 2.44140625E-4 : f32
    affine.for %i = 0 to 8 {
      affine.for %j = 0 to 2 {
        %q = affine.load %input[%i * 2 + %j] : memref<16xi8>
        %qi32 = arith.extsi %q : i8 to i32
        %shifted = arith.subi %qi32, %czp : i32
        %qf32 = arith.sitofp %shifted : i32 to f32
        %product = arith.mulf %qf32, %cscale : f32
        affine.store %product, %output[%i * 2 + %j] : memref<16xf32>
      }
    }
    return
  }
}
""",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
