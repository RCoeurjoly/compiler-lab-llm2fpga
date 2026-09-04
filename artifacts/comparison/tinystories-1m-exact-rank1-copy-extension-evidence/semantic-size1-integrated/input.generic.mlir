"builtin.module"() ({
  "func.func"() <{function_type = (i64) -> i64, sym_name = "direct_rank1_size1"}> ({
  ^bb0(%arg0: i64):
    %0 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %1 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %2 = "arith.constant"() <{value = 0 : index}> : () -> index
    "memref.store"(%arg0, %0, %2) : (i64, memref<1xi64>, index) -> ()
    "memref.copy"(%0, %1) : (memref<1xi64>, memref<1xi64>) -> ()
    %3 = "memref.load"(%1, %2) : (memref<1xi64>, index) -> i64
    "func.return"(%3) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

