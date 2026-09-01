"builtin.module"() ({
  "func.func"() <{function_type = (i64) -> i64, sym_name = "direct_rank1_size1"}> ({
  ^bb0(%arg0: i64):
    %0 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %1 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %2 = "arith.constant"() <{value = 0 : index}> : () -> index
    "memref.store"(%arg0, %0, %2) : (i64, memref<1xi64>, index) -> ()
    %3 = "arith.constant"() <{value = 0 : index}> : () -> index
    %4 = "arith.constant"() <{value = 1 : index}> : () -> index
    %5 = "arith.constant"() <{value = 1 : index}> : () -> index
    "scf.for"(%3, %4, %5) ({
    ^bb0(%arg1: index):
      %7 = "arith.constant"() <{value = 0 : index}> : () -> index
      %8 = "arith.addi"(%7, %arg1) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
      %9 = "arith.constant"() <{value = 0 : index}> : () -> index
      %10 = "arith.addi"(%9, %arg1) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
      %11 = "memref.load"(%0, %8) : (memref<1xi64>, index) -> i64
      "memref.store"(%11, %1, %10) : (i64, memref<1xi64>, index) -> ()
      "scf.yield"() : () -> ()
    }) : (index, index, index) -> ()
    %6 = "memref.load"(%1, %2) : (memref<1xi64>, index) -> i64
    "func.return"(%6) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

