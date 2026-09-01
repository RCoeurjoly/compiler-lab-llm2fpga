"builtin.module"() ({
  "func.func"() <{function_type = () -> i64, sym_name = "representative"}> ({
    %0 = "arith.constant"() <{value = 0 : i64}> : () -> i64
    %1 = "arith.constant"() <{value = 0 : index}> : () -> index
    %2 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    %3 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<1xi64>
    "memref.store"(%0, %2, %1) : (i64, memref<1xi64>, index) -> ()
    "memref.copy"(%2, %3) : (memref<1xi64>, memref<1xi64>) -> ()
    %4 = "memref.load"(%3, %1) : (memref<1xi64>, index) -> i64
    "func.return"(%4) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

