"builtin.module"() ({
  "func.func"() <{function_type = (i64) -> i64, sym_name = "direct_rank1_size1"}> ({
  ^bb0(%arg0: i64):
    %0 = "arith.constant"() <{value = 0 : index}> : () -> index
    %1 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %2 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    "memref.store"(%arg0, %1, %0) : (i64, memref<1xi64>, index) -> ()
    %3 = "memref.load"(%1, %0) : (memref<1xi64>, index) -> i64
    "memref.store"(%3, %2, %0) : (i64, memref<1xi64>, index) -> ()
    %4 = "memref.load"(%2, %0) : (memref<1xi64>, index) -> i64
    "func.return"(%4) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

