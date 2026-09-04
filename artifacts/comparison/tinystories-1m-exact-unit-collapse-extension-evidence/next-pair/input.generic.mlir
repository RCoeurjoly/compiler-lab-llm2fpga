"builtin.module"() ({
  "func.func"() <{function_type = () -> i64, sym_name = "representative"}> ({
    %0 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %1 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %2 = "arith.constant"() <{value = 0 : index}> : () -> index
    %3 = "arith.constant"() <{value = 0 : i64}> : () -> i64
    "memref.store"(%3, %0, %2) : (i64, memref<1xi64>, index) -> ()
    "memref.copy"(%0, %1) : (memref<1xi64>, memref<1xi64>) -> ()
    %4 = "memref.load"(%1, %2) : (memref<1xi64>, index) -> i64
    "func.return"(%4) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

