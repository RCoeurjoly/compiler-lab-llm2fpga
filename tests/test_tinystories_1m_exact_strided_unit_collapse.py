#!/usr/bin/env python3
"""Semantic regressions for exact static strided unit collapses."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPRODUCERS = ROOT / "reproducers/tinystories-1m-exact-strided-unit-collapse"
PIPELINE = (
    "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,"
    "canonicalize,cse)"
)
REVIEWED_PLUGIN = Path(
    "/nix/store/jpbaq3vd25spvvrb90gj5hb3k5ysp3h3-"
    "llm2fpga-mlir-passes-0.1.0/lib/LLM2FPGAMLIRPasses.so"
)

WRONG_RESULT_STRIDE_CONTROL = """module {
  func.func @wrong_result_stride(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[1]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[1]>>
    return %loaded : i64
  }
}
"""

WRONG_RESULT_OFFSET_CONTROL = """module {
  func.func @wrong_result_offset(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 7] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: 7>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded : i64
  }
}
"""

DYNAMIC_CONTROL = """module {
  func.func @dynamic_offset(%source: memref<64x64xi64>, %offset: index, %i: index) -> i64 {
    %sub = memref.subview %source[%offset, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: ?>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: ?>> into memref<64xi64, strided<[64], offset: ?>>
    %loaded = memref.load %flat[%i]
      : memref<64xi64, strided<[64], offset: ?>>
    return %loaded : i64
  }
}
"""

OTHER_REASSOCIATION_CONTROL = """module {
  func.func @other_reassociation(%source: memref<4x64x64xi64>, %i: index, %j: index) -> i64 {
    %sub = memref.subview %source[0, 0, 0] [4, 64, 1] [1, 1, 1]
      : memref<4x64x64xi64> to memref<4x64x1xi64, strided<[4096, 64, 1]>>
    %flat = memref.collapse_shape %sub [[0], [1, 2]]
      : memref<4x64x1xi64, strided<[4096, 64, 1]>> into memref<4x64xi64, strided<[4096, 64]>>
    %loaded = memref.load %flat[%i, %j]
      : memref<4x64xi64, strided<[4096, 64]>>
    return %loaded : i64
  }
}
"""

ZERO_N_CONTROL = """module {
  func.func @zero_n(%source: memref<8x8xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [0, 1] [1, 1]
      : memref<8x8xi64> to memref<0x1xi64, strided<[8, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<0x1xi64, strided<[8, 1]>> into memref<0xi64, strided<[8]>>
    %loaded = memref.load %flat[%i] : memref<0xi64, strided<[8]>>
    return %loaded : i64
  }
}
"""

NONPOSITIVE_STRIDE_CONTROL = """module {
  func.func @nonpositive_stride(%source: memref<8x8xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [8, 8] [1, 1]
      : memref<8x8xi64> to memref<8x8xi64, strided<[8, 1]>>
    %strided = memref.reinterpret_cast %sub to
      offset: [0], sizes: [8, 1], strides: [0, 1]
      : memref<8x8xi64, strided<[8, 1]>> to memref<8x1xi64, strided<[0, 1]>>
    %flat = memref.collapse_shape %strided [[0, 1]]
      : memref<8x1xi64, strided<[0, 1]>> into memref<8xi64, strided<[0]>>
    %loaded = memref.load %flat[%i] : memref<8xi64, strided<[0]>>
    return %loaded : i64
  }
}
"""

MIXED_SIBLING_CONTROL = """module {
  func.func @mixed_sibling(%source: memref<64x64xi64>, %dynamic: index, %i: index) -> i64 {
    %supported_sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %supported_flat = memref.collapse_shape %supported_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %supported_value = memref.load %supported_flat[%i]
      : memref<64xi64, strided<[64]>>
    %unsupported_sub = memref.subview %source[%dynamic, 0] [1, 1] [1, 1]
      : memref<64x64xi64> to memref<1x1xi64, strided<[64, 1], offset: ?>>
    %unsupported_value = memref.load %unsupported_sub[%i, %i]
      : memref<1x1xi64, strided<[64, 1], offset: ?>>
    %sum = arith.addi %supported_value, %unsupported_value : i64
    return %sum : i64
  }
}
"""

DIRECT_DIM_SIBLING_CONTROL = """module {
  func.func @mixed_direct_root_user(%source: memref<64x64xi64>, %i: index) -> (i64, index) {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    %c0 = arith.constant 0 : index
    %dim = memref.dim %source, %c0 : memref<64x64xi64>
    return %loaded, %dim : i64, index
  }
}
"""

DIRECT_TYPED_CALL_SIBLING_CONTROL = """module {
  func.func private @consume_rank_two(memref<64x64xi64>)

  func.func @direct_typed_call(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call @consume_rank_two(%source) : (memref<64x64xi64>) -> ()
    return %loaded : i64
  }
}
"""

DIRECT_RETURN_ESCAPE_CONTROL = """module {
  func.func @direct_return_escape(%source: memref<64x64xi64>, %i: index)
      -> (i64, memref<64x64xi64>) {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded, %source : i64, memref<64x64xi64>
  }
}
"""

TRANSITIVE_TYPED_CALL_CONTROL = """module {
  func.func private @consume_collapsed(memref<64xi64, strided<[64]>>)

  func.func @transitive_typed_call(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call @consume_collapsed(%flat)
      : (memref<64xi64, strided<[64]>>) -> ()
    return %loaded : i64
  }
}
"""

DIRECT_ACCESS_SIBLING_CONTROL = """module {
  func.func @direct_access_sibling(
      %source: memref<64x64xi64>, %i: index, %j: index, %value: i64)
      -> (i64, i64) {
    memref.store %value, %source[%i, %j] : memref<64x64xi64>
    %direct = memref.load %source[%i, %j] : memref<64x64xi64>
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %collapsed = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %direct, %collapsed : i64, i64
  }
}
"""

DIRECT_USER_COPY_DEPENDENCY_CONTROL = """module {
  func.func @direct_user_copy_dependency(
      %source: memref<64x64xi64>, %target: memref<64x64xi64>) -> index {
    %source_sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %source_flat = memref.collapse_shape %source_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %target_sub = memref.subview %target[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %target_flat = memref.collapse_shape %target_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    memref.copy %source_flat, %target_flat
      : memref<64xi64, strided<[64]>> to memref<64xi64, strided<[64]>>
    %c0 = arith.constant 0 : index
    %dim = memref.dim %target, %c0 : memref<64x64xi64>
    return %dim : index
  }
}
"""

INTERNAL_UNUSED_CALLEE_FIRST_CONTROL = """module {
  func.func private @consume_internal(%arg: memref<64x64xi64>) {
    return
  }

  func.func @direct_internal_call(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call @consume_internal(%source) : (memref<64x64xi64>) -> ()
    return %loaded : i64
  }
}
"""

INTERNAL_SAFE_CALLEE_LAST_CONTROL = """module {
  func.func @call_safely_used_internal(
      %source: memref<64x64xi64>, %i: index) -> (i64, i64) {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    %callee_value = func.call @safely_used_internal(%source, %i)
      : (memref<64x64xi64>, index) -> i64
    return %loaded, %callee_value : i64, i64
  }

  func.func private @safely_used_internal(
      %arg: memref<64x64xi64>, %i: index) -> i64 {
    %value = memref.load %arg[%i, %i] : memref<64x64xi64>
    return %value : i64
  }
}
"""

MULTI_CALLER_INTERNAL_CONTROL = """module {
  func.func @first_internal_caller(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call @shared_internal(%source) : (memref<64x64xi64>) -> ()
    return %loaded : i64
  }

  func.func private @shared_internal(%arg: memref<64x64xi64>) {
    return
  }

  func.func @second_internal_caller(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call @shared_internal(%source) : (memref<64x64xi64>) -> ()
    return %loaded : i64
  }
}
"""

RECURSIVE_INTERNAL_CONTROL = """module {
  func.func private @recursive_internal(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    %recursive = func.call @recursive_internal(%source, %i)
      : (memref<64x64xi64>, index) -> i64
    %sum = arith.addi %loaded, %recursive : i64
    return %sum : i64
  }
}
"""

INDIRECT_INTERNAL_CONTROL = """module {
  func.func private @indirect_internal(%arg: memref<64x64xi64>) {
    return
  }

  func.func @indirect_internal_caller(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %callee = func.constant @indirect_internal
      : (memref<64x64xi64>) -> ()
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call_indirect %callee(%source) : (memref<64x64xi64>) -> ()
    return %loaded : i64
  }
}
"""

CALLED_AND_UNCALLED_CONTROL = """module {
  func.func private @called_boundary(%arg: memref<64x64xi64>) {
    return
  }

  func.func @boundary_caller(%source: memref<64x64xi64>) {
    func.call @called_boundary(%source) : (memref<64x64xi64>) -> ()
    return
  }

  func.func @uncalled_exact(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded : i64
  }
}
"""

NESTED_DIRECT_CALLEE_FIRST_CONTROL = """module {
  module @nested_scope {
    func.func private @consume_nested(%arg: memref<64x64xi64>) {
      return
    }

    func.func @call_nested(
        %source: memref<64x64xi64>, %i: index) -> i64 {
      %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
        : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
      %flat = memref.collapse_shape %sub [[0, 1]]
        : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
      %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
      func.call @consume_nested(%source) : (memref<64x64xi64>) -> ()
      return %loaded : i64
    }
  }
}
"""

NESTED_DIRECT_CALLER_FIRST_CONTROL = """module {
  module @reverse_nested_scope {
    func.func @call_nested_reverse(
        %source: memref<64x64xi64>, %i: index) -> (i64, i64) {
      %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
        : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
      %flat = memref.collapse_shape %sub [[0, 1]]
        : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
      %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
      %callee_value = func.call @consume_nested_reverse(%source, %i)
        : (memref<64x64xi64>, index) -> i64
      return %loaded, %callee_value : i64, i64
    }

    func.func private @consume_nested_reverse(
        %arg: memref<64x64xi64>, %i: index) -> i64 {
      %value = memref.load %arg[%i, %i] : memref<64x64xi64>
      return %value : i64
    }
  }
}
"""

NESTED_INDIRECT_CONSTANT_CONTROL = """module {
  module @indirect_nested_scope {
    func.func private @consume_nested_indirect(%arg: memref<64x64xi64>) {
      return
    }

    func.func @call_nested_indirect(
        %source: memref<64x64xi64>, %i: index) -> i64 {
      %callee = func.constant @consume_nested_indirect
        : (memref<64x64xi64>) -> ()
      %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
        : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
      %flat = memref.collapse_shape %sub [[0, 1]]
        : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
      %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
      func.call_indirect %callee(%source) : (memref<64x64xi64>) -> ()
      return %loaded : i64
    }
  }
}
"""

SHADOWED_OUTER_FIRST_CONTROL = """module {
  func.func @shadowed(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded : i64
  }

  module @shadowing_scope {
    func.func private @shadowed(%arg: memref<64x64xi64>) {
      return
    }

    func.func @call_shadowed(
        %source: memref<64x64xi64>, %i: index) -> i64 {
      %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
        : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
      %flat = memref.collapse_shape %sub [[0, 1]]
        : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
      %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
      func.call @shadowed(%source) : (memref<64x64xi64>) -> ()
      return %loaded : i64
    }
  }
}
"""

SHADOWED_NESTED_FIRST_CONTROL = """module {
  module @reverse_shadowing_scope {
    func.func private @shadowed(%arg: memref<64x64xi64>) {
      return
    }

    func.func @call_shadowed_reverse(
        %source: memref<64x64xi64>, %i: index) -> i64 {
      %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
        : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
      %flat = memref.collapse_shape %sub [[0, 1]]
        : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
      %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
      func.call @shadowed(%source) : (memref<64x64xi64>) -> ()
      return %loaded : i64
    }
  }

  func.func @shadowed(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded : i64
  }
}
"""

QUALIFIED_FUNC_CALL_CONTROL = """module {
  module @qualified_scope {
    func.func @qualified_callee(%arg: memref<64x64xi64>)
  }

  func.func @qualified_caller(%source: memref<64x64xi64>) {
    func.call @qualified_scope::@qualified_callee(%source)
      : (memref<64x64xi64>) -> ()
    return
  }
}
"""

UNRESOLVED_FUNC_CALL_CONTROL = """module {
  func.func @unresolved_call(
      %source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    func.call @missing_callee(%source) : (memref<64x64xi64>) -> ()
    return %loaded : i64
  }
}
"""

UNRESOLVED_FUNC_CONSTANT_CONTROL = """module {
  func.func @unresolved_constant(%source: memref<64x64xi64>) {
    %callee = func.constant @missing_constant
      : (memref<64x64xi64>) -> ()
    func.call_indirect %callee(%source) : (memref<64x64xi64>) -> ()
    return
  }
}
"""

COLLAPSED_COPY_CONTROL = """module {
  func.func @collapsed_copy(%source: memref<64x64xi64>, %target: memref<64x64xi64>) {
    %source_sub = memref.subview %source[0, 7] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
    %source_flat = memref.collapse_shape %source_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: 7>> into memref<64xi64, strided<[64], offset: 7>>
    %target_sub = memref.subview %target[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %target_flat = memref.collapse_shape %target_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    memref.copy %source_flat, %target_flat
      : memref<64xi64, strided<[64], offset: 7>> to memref<64xi64, strided<[64]>>
    return
  }
}
"""

IDENTITY_COLLAPSE_CONTROL = """module {
  func.func @identity_collapse(%source: memref<8x8xi64>, %i: index) -> i64 {
    %flat = memref.collapse_shape %source [[0, 1]]
      : memref<8x8xi64> into memref<64xi64>
    %loaded = memref.load %flat[%i] : memref<64xi64>
    return %loaded : i64
  }
}
"""


@dataclass(frozen=True)
class AffineExpr:
    offset: int
    coefficients: tuple[int, ...]

    def add(self, other: "AffineExpr") -> "AffineExpr":
        return AffineExpr(
            self.offset + other.offset,
            tuple(
                left + right
                for left, right in zip(self.coefficients, other.coefficients)
            ),
        )

    def scale(self, factor: int) -> "AffineExpr":
        return AffineExpr(
            self.offset * factor,
            tuple(coefficient * factor for coefficient in self.coefficients),
        )

    def constant_value(self) -> int | None:
        if any(self.coefficients):
            return None
        return self.offset


def resolve_plugin() -> Path:
    candidates = []
    if configured := os.environ.get("LLM2FPGA_MLIR_PASS_PLUGIN"):
        candidates.append(Path(configured))
    candidates.extend([ROOT / "result/lib/LLM2FPGAMLIRPasses.so", REVIEWED_PLUGIN])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(
        "no pass plugin found; run `nix build .#llm2fpgaMlirPasses` or set "
        "LLM2FPGA_MLIR_PASS_PLUGIN"
    )


def resolve_mlir_opt() -> Path:
    configured = os.environ.get("MLIR_OPT")
    discovered = configured or shutil.which("mlir-opt")
    if not discovered:
        raise RuntimeError("mlir-opt is absent; run the test through `nix develop`")
    return Path(discovered).resolve()


def run_pass(input_path: Path) -> tuple[subprocess.CompletedProcess[bytes], str]:
    mlir_opt = resolve_mlir_opt()
    plugin = resolve_plugin()
    with tempfile.TemporaryDirectory(prefix="exact-strided-unit-collapse-") as raw:
        output_path = Path(raw) / "output.mlir"
        completed = subprocess.run(
            [
                str(mlir_opt),
                str(input_path),
                f"--load-pass-plugin={plugin}",
                f"--pass-pipeline={PIPELINE}",
                "-mlir-print-op-generic",
                "-o",
                str(output_path),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        if completed.returncode == 0:
            parsed = subprocess.run(
                [str(mlir_opt), str(output_path), "-o", "/dev/null"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if parsed.returncode != 0:
                raise AssertionError(
                    "post-pass output did not parse:\n"
                    + parsed.stderr.decode(errors="replace")
                )
        return completed, output


def run_text(source: str) -> tuple[subprocess.CompletedProcess[bytes], str]:
    with tempfile.TemporaryDirectory(prefix="exact-strided-unit-control-") as raw:
        input_path = Path(raw) / "input.mlir"
        input_path.write_text(source, encoding="utf-8")
        return run_pass(input_path)


def _entry_arguments(generic_ir: str) -> list[str]:
    match = re.search(r"^\s*\^bb0\(([^)]*)\):", generic_ir, re.MULTILINE)
    if not match:
        raise AssertionError("generic post-pass IR has no entry block arguments")
    return re.findall(r"(%[A-Za-z0-9_]+)\s*:", match.group(1))


def _function_type(generic_ir: str, symbol: str) -> str:
    match = re.search(
        rf'function_type = (.*?), sym_name = "{re.escape(symbol)}"',
        generic_ir,
    )
    if not match:
        raise AssertionError(f"missing generic function type for @{symbol}")
    return match.group(1)


def _function_types(generic_ir: str, symbol: str) -> list[str]:
    matches = re.findall(
        rf'function_type = (.*?), sym_name = "{re.escape(symbol)}"',
        generic_ir,
    )
    if not matches:
        raise AssertionError(f"missing generic function types for @{symbol}")
    return matches


def _affine_accesses(
    generic_ir: str,
    *,
    variable_names: list[str],
    domains: list[dict[str, int | str]],
) -> list[dict[str, object]]:
    if len(variable_names) != len(domains):
        raise AssertionError("symbolic variables and domains differ in length")
    entry_arguments = _entry_arguments(generic_ir)
    variable_count = len(variable_names)
    expressions: dict[str, AffineExpr] = {
        variable_name: AffineExpr(
            0,
            tuple(
                1 if index == variable_index else 0
                for index in range(variable_count)
            ),
        )
        for variable_index, variable_name in enumerate(variable_names)
    }
    constant = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) '
        r'<\{value = (-?[0-9]+) : index\}>'
    )
    binary = re.compile(
        r'^\s*(%[A-Za-z0-9_]+) = "arith\.(addi|muli)"\('
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    load = re.compile(
        r'^\s*%[A-Za-z0-9_]+ = "memref\.load"\('
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    store = re.compile(
        r'^\s*"memref\.store"\(%[A-Za-z0-9_]+, '
        r'(%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+)\)'
    )
    accesses = []
    for line in generic_ir.splitlines():
        if match := constant.match(line):
            expressions[match.group(1)] = AffineExpr(
                int(match.group(2)), tuple(0 for _ in range(variable_count))
            )
            continue
        if match := binary.match(line):
            result, operation, left_name, right_name = match.groups()
            if left_name not in expressions or right_name not in expressions:
                raise AssertionError(f"unresolved affine operands in `{line.strip()}`")
            left = expressions[left_name]
            right = expressions[right_name]
            if operation == "addi":
                expressions[result] = left.add(right)
            else:
                left_constant = left.constant_value()
                right_constant = right.constant_value()
                if left_constant is not None:
                    expressions[result] = right.scale(left_constant)
                elif right_constant is not None:
                    expressions[result] = left.scale(right_constant)
                else:
                    raise AssertionError(f"non-affine multiply in `{line.strip()}`")
            continue

        role = None
        operation = None
        match = load.match(line)
        if match:
            role = "source"
            operation = "memref.load"
        else:
            match = store.match(line)
            if match:
                role = "target"
                operation = "memref.store"
        if not match:
            continue
        base, index = match.groups()
        if index not in expressions:
            raise AssertionError(f"unresolved access index in `{line.strip()}`")
        if base not in entry_arguments:
            raise AssertionError(f"access base is not an entry argument in `{line.strip()}`")
        expression = expressions[index]
        accesses.append(
            {
                "operation": operation,
                "base_argument": entry_arguments.index(base),
                "base_role": role,
                "variables": [
                    {**domain, "ssa": variable_name}
                    for domain, variable_name in zip(domains, variable_names)
                ],
                "offset": expression.offset,
                "coefficients": list(expression.coefficients),
            }
        )
    return accesses


def _single_loop_domain(generic_ir: str) -> tuple[str, dict[str, int | str]]:
    constants = {
        name: int(value)
        for name, value in re.findall(
            r'^\s*(%[A-Za-z0-9_]+) = "arith\.constant"\(\) '
            r'<\{value = (-?[0-9]+) : index\}>',
            generic_ir,
            re.MULTILINE,
        )
    }
    loops = re.findall(
        r'"scf\.for"\((%[A-Za-z0-9_]+), (%[A-Za-z0-9_]+), '
        r'(%[A-Za-z0-9_]+)\) \(\{\s*\^bb[0-9]+\('
        r'(%[A-Za-z0-9_]+): index\)',
        generic_ir,
        re.DOTALL,
    )
    if len(loops) != 1:
        raise AssertionError(f"expected one copy loop, found {len(loops)}")
    lower, upper, step, induction = loops[0]
    if any(name not in constants for name in (lower, upper, step)):
        raise AssertionError("copy loop bounds are not literal index constants")
    if constants[step] != 1:
        raise AssertionError(f"copy loop step is {constants[step]}, not 1")
    return induction, {
        "name": "i",
        "lower": constants[lower],
        "upper_exclusive": constants[upper],
    }


class ExactStridedUnitCollapseTest(unittest.TestCase):
    maxDiff = None

    def assert_passes(self, source: str | Path) -> str:
        if isinstance(source, Path):
            completed, output = run_pass(source)
        else:
            completed, output = run_text(source)
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )
        return output

    def assert_verifier_rejected(self, source: str, diagnostic: str) -> None:
        completed, output = run_text(source)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(output, "")
        self.assertIn(diagnostic, completed.stderr.decode(errors="replace"))

    def assert_supported_mapping(self, fixture: str, *, offset: int) -> None:
        output = self.assert_passes(REPRODUCERS / fixture)
        self.assertNotIn("memref.subview", output)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertIn("memref<4096xi64>", output)
        variable = _entry_arguments(output)[1]
        domain = {"name": "i", "lower": 0, "upper_exclusive": 64}
        expected = [
            {
                "operation": operation,
                "base_argument": 0,
                "base_role": role,
                "variables": [{**domain, "ssa": variable}],
                "offset": offset,
                "coefficients": [64],
            }
            for operation, role in (
                ("memref.store", "target"),
                ("memref.load", "source"),
            )
        ]
        self.assertCountEqual(
            _affine_accesses(
                output,
                variable_names=[variable],
                domains=[domain],
            ),
            expected,
        )

    def assert_explicit_or_verifier_rejected(
        self,
        source: str | Path,
        *,
        ranked_root: str,
        flattened_root: str,
        required_views: tuple[str, ...] = ("memref.subview", "memref.collapse_shape"),
    ) -> None:
        if isinstance(source, Path):
            completed, output = run_pass(source)
        else:
            completed, output = run_text(source)
        if completed.returncode != 0:
            self.assertIn("error:", completed.stderr.decode(errors="replace"))
            self.assertEqual(output, "")
            return
        for view in required_views:
            self.assertIn(view, output)
        self.assertIn(ranked_root, output)
        self.assertNotIn(flattened_root, output)

    def test_offset_zero_proves_64_i_over_the_complete_domain(self) -> None:
        self.assert_supported_mapping("offset-zero.mlir", offset=0)

    def test_offset_seven_proves_7_plus_64_i_over_the_complete_domain(self) -> None:
        self.assert_supported_mapping("offset-nonzero.mlir", offset=7)

    def test_collapsed_copy_lowers_both_roles_with_exact_maps(self) -> None:
        output = self.assert_passes(COLLAPSED_COPY_CONTROL)
        self.assertNotIn("memref.subview", output)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertNotIn("memref.copy", output)
        self.assertEqual(output.count("memref<4096xi64>"), 6)
        induction, domain = _single_loop_domain(output)
        self.assertCountEqual(
            _affine_accesses(
                output,
                variable_names=[induction],
                domains=[domain],
            ),
            [
                {
                    "operation": "memref.load",
                    "base_argument": 0,
                    "base_role": "source",
                    "variables": [{**domain, "ssa": induction}],
                    "offset": 7,
                    "coefficients": [64],
                },
                {
                    "operation": "memref.store",
                    "base_argument": 1,
                    "base_role": "target",
                    "variables": [{**domain, "ssa": induction}],
                    "offset": 0,
                    "coefficients": [64],
                },
            ],
        )

    def test_identity_collapse_behavior_is_retained(self) -> None:
        output = self.assert_passes(IDENTITY_COLLAPSE_CONTROL)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertIn("memref<64xi64>", output)
        variable = _entry_arguments(output)[1]
        domain = {"name": "i", "lower": 0, "upper_exclusive": 64}
        self.assertEqual(
            _affine_accesses(
                output,
                variable_names=[variable],
                domains=[domain],
            ),
            [
                {
                    "operation": "memref.load",
                    "base_argument": 0,
                    "base_role": "source",
                    "variables": [{**domain, "ssa": variable}],
                    "offset": 0,
                    "coefficients": [1],
                }
            ],
        )

    def test_nonunit_trailing_dimension_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            REPRODUCERS / "unsupported-nonunit.mlir",
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_wrong_result_stride_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            WRONG_RESULT_STRIDE_CONTROL,
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_wrong_result_offset_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            WRONG_RESULT_OFFSET_CONTROL,
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_dynamic_metadata_remains_explicit_with_ranked_root(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            DYNAMIC_CONTROL,
            ranked_root="memref<64x64xi64>",
            flattened_root="memref<4096xi64>",
        )

    def test_other_reassociation_remains_explicit_with_ranked_root(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            OTHER_REASSOCIATION_CONTROL,
            ranked_root="memref<4x64x64xi64>",
            flattened_root="memref<16384xi64>",
        )

    def test_zero_leading_dimension_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            ZERO_N_CONTROL,
            ranked_root="memref<8x8xi64>",
            flattened_root="memref<64xi64>",
        )

    def test_nonpositive_leading_stride_fails_closed(self) -> None:
        self.assert_explicit_or_verifier_rejected(
            NONPOSITIVE_STRIDE_CONTROL,
            ranked_root="memref<8x8xi64>",
            flattened_root="memref<64xi64>",
            required_views=(
                "memref.reinterpret_cast",
                "memref.collapse_shape",
            ),
        )

    def test_mixed_supported_and_unsupported_siblings_protect_root(self) -> None:
        output = self.assert_passes(MIXED_SIBLING_CONTROL)
        self.assertEqual(output.count('"memref.subview"'), 2)
        self.assertIn("memref.collapse_shape", output)
        self.assertIn("memref<64x64xi64>", output)
        self.assertNotIn("memref<4096xi64>", output)

    def assert_rank_two_root_and_chain_remain_explicit(self, source: str) -> str:
        output = self.assert_passes(source)
        self.assertIn("memref<64x64xi64>", output)
        self.assertNotIn("memref<4096xi64>", output)
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)
        return output

    def test_direct_dim_sibling_preserves_original_dimension(self) -> None:
        output = self.assert_rank_two_root_and_chain_remain_explicit(
            DIRECT_DIM_SIBLING_CONTROL
        )
        self.assertIn("value = 64 : index", output)
        self.assertNotIn("value = 4096 : index", output)

    def test_direct_typed_call_sibling_protects_root(self) -> None:
        output = self.assert_rank_two_root_and_chain_remain_explicit(
            DIRECT_TYPED_CALL_SIBLING_CONTROL
        )
        self.assertIn("func.call", output)

    def test_direct_return_escape_protects_root(self) -> None:
        output = self.assert_rank_two_root_and_chain_remain_explicit(
            DIRECT_RETURN_ESCAPE_CONTROL
        )
        self.assertIn(
            "(memref<64x64xi64>, index) -> (i64, memref<64x64xi64>)",
            output,
        )

    def test_transitive_typed_call_protects_root(self) -> None:
        output = self.assert_rank_two_root_and_chain_remain_explicit(
            TRANSITIVE_TYPED_CALL_CONTROL
        )
        self.assertIn("func.call", output)

    def test_direct_load_store_sibling_remains_rewriteable(self) -> None:
        output = self.assert_passes(DIRECT_ACCESS_SIBLING_CONTROL)
        self.assertNotIn("memref.subview", output)
        self.assertNotIn("memref.collapse_shape", output)
        self.assertIn("memref<4096xi64>", output)
        arguments = _entry_arguments(output)
        variables = arguments[1:3]
        domains = [
            {"name": "i", "lower": 0, "upper_exclusive": 64},
            {"name": "j", "lower": 0, "upper_exclusive": 64},
        ]
        expected_variables = [
            {**domain, "ssa": variable}
            for domain, variable in zip(domains, variables)
        ]
        self.assertCountEqual(
            _affine_accesses(
                output,
                variable_names=variables,
                domains=domains,
            ),
            [
                {
                    "operation": "memref.store",
                    "base_argument": 0,
                    "base_role": "target",
                    "variables": expected_variables,
                    "offset": 0,
                    "coefficients": [64, 1],
                },
                {
                    "operation": "memref.load",
                    "base_argument": 0,
                    "base_role": "source",
                    "variables": expected_variables,
                    "offset": 0,
                    "coefficients": [64, 1],
                },
                {
                    "operation": "memref.load",
                    "base_argument": 0,
                    "base_role": "source",
                    "variables": expected_variables,
                    "offset": 0,
                    "coefficients": [64, 0],
                },
            ],
        )

    def test_direct_user_protection_propagates_across_collapsed_copy(self) -> None:
        output = self.assert_passes(DIRECT_USER_COPY_DEPENDENCY_CONTROL)
        self.assertEqual(output.count('"memref.subview"'), 2)
        self.assertEqual(output.count('"memref.collapse_shape"'), 2)
        self.assertIn("memref.copy", output)
        self.assertIn("memref<64x64xi64>", output)
        self.assertNotIn("memref<4096xi64>", output)
        self.assertIn("value = 64 : index", output)
        self.assertNotIn("value = 4096 : index", output)

    def test_internal_unused_callee_before_caller_retains_ranked_boundary(
        self,
    ) -> None:
        output = self.assert_passes(INTERNAL_UNUSED_CALLEE_FIRST_CONTROL)
        self.assertEqual(
            _function_type(output, "consume_internal"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(
            _function_type(output, "direct_internal_call"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_internal_safely_used_callee_after_caller_retains_ranked_boundary(
        self,
    ) -> None:
        output = self.assert_passes(INTERNAL_SAFE_CALLEE_LAST_CONTROL)
        self.assertEqual(
            _function_type(output, "safely_used_internal"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertEqual(
            _function_type(output, "call_safely_used_internal"),
            "(memref<64x64xi64>, index) -> (i64, i64)",
        )
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_multiple_internal_callers_retain_one_ranked_callee_boundary(
        self,
    ) -> None:
        output = self.assert_passes(MULTI_CALLER_INTERNAL_CONTROL)
        for symbol in (
            "first_internal_caller",
            "second_internal_caller",
        ):
            self.assertEqual(
                _function_type(output, symbol),
                "(memref<64x64xi64>, index) -> i64",
            )
        self.assertEqual(
            _function_type(output, "shared_internal"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(output.count('"func.call"'), 2)
        self.assertEqual(output.count('"memref.subview"'), 2)
        self.assertEqual(output.count('"memref.collapse_shape"'), 2)

    def test_recursive_internal_function_retains_ranked_boundary(self) -> None:
        output = self.assert_passes(RECURSIVE_INTERNAL_CONTROL)
        self.assertEqual(
            _function_type(output, "recursive_internal"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertIn("func.call", output)
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_indirect_internal_symbol_use_retains_ranked_boundary(self) -> None:
        output = self.assert_passes(INDIRECT_INTERNAL_CONTROL)
        self.assertEqual(
            _function_type(output, "indirect_internal"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(
            _function_type(output, "indirect_internal_caller"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_unreferenced_function_remains_eligible_in_module_with_calls(
        self,
    ) -> None:
        output = self.assert_passes(CALLED_AND_UNCALLED_CONTROL)
        self.assertEqual(
            _function_type(output, "called_boundary"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(
            _function_type(output, "boundary_caller"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(
            _function_type(output, "uncalled_exact"),
            "(memref<4096xi64>, index) -> i64",
        )
        self.assertEqual(output.count('"memref.subview"'), 0)
        self.assertEqual(output.count('"memref.collapse_shape"'), 0)

    def test_nested_direct_callee_before_caller_uses_nearest_symbol_table(
        self,
    ) -> None:
        output = self.assert_passes(NESTED_DIRECT_CALLEE_FIRST_CONTROL)
        self.assertEqual(
            _function_type(output, "consume_nested"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(
            _function_type(output, "call_nested"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_nested_direct_caller_before_callee_is_order_independent(
        self,
    ) -> None:
        output = self.assert_passes(NESTED_DIRECT_CALLER_FIRST_CONTROL)
        self.assertEqual(
            _function_type(output, "consume_nested_reverse"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertEqual(
            _function_type(output, "call_nested_reverse"),
            "(memref<64x64xi64>, index) -> (i64, i64)",
        )
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_nested_indirect_constant_uses_nearest_symbol_table(self) -> None:
        output = self.assert_passes(NESTED_INDIRECT_CONSTANT_CONTROL)
        self.assertEqual(
            _function_type(output, "consume_nested_indirect"),
            "(memref<64x64xi64>) -> ()",
        )
        self.assertEqual(
            _function_type(output, "call_nested_indirect"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertIn("memref.subview", output)
        self.assertIn("memref.collapse_shape", output)

    def test_shadowed_outer_first_protects_only_resolved_nested_callee(
        self,
    ) -> None:
        output = self.assert_passes(SHADOWED_OUTER_FIRST_CONTROL)
        self.assertEqual(
            _function_types(output, "shadowed"),
            [
                "(memref<4096xi64>, index) -> i64",
                "(memref<64x64xi64>) -> ()",
            ],
        )
        self.assertEqual(
            _function_type(output, "call_shadowed"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertEqual(output.count('"memref.subview"'), 1)
        self.assertEqual(output.count('"memref.collapse_shape"'), 1)

    def test_shadowed_nested_first_protects_only_resolved_nested_callee(
        self,
    ) -> None:
        output = self.assert_passes(SHADOWED_NESTED_FIRST_CONTROL)
        self.assertEqual(
            _function_types(output, "shadowed"),
            [
                "(memref<64x64xi64>) -> ()",
                "(memref<4096xi64>, index) -> i64",
            ],
        )
        self.assertEqual(
            _function_type(output, "call_shadowed_reverse"),
            "(memref<64x64xi64>, index) -> i64",
        )
        self.assertEqual(output.count('"memref.subview"'), 1)
        self.assertEqual(output.count('"memref.collapse_shape"'), 1)

    def test_qualified_func_call_is_rejected_before_the_pass(self) -> None:
        self.assert_verifier_rejected(
            QUALIFIED_FUNC_CALL_CONTROL,
            "invalid kind of attribute specified",
        )

    def test_unresolved_func_call_fails_closed_before_the_pass(self) -> None:
        self.assert_verifier_rejected(
            UNRESOLVED_FUNC_CALL_CONTROL,
            "'missing_callee' does not reference a valid function",
        )

    def test_unresolved_func_constant_fails_closed_before_the_pass(self) -> None:
        self.assert_verifier_rejected(
            UNRESOLVED_FUNC_CONSTANT_CONTROL,
            "reference to undefined function 'missing_constant'",
        )


if __name__ == "__main__":
    unittest.main()
