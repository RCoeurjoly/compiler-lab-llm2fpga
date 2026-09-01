"builtin.module"() ({
  "func.func"() <{function_type = (i64) -> i64, sym_name = "direct_rank1_size64"}> ({
  ^bb0(%arg0: i64):
    %0 = "arith.constant"() <{value = 1 : index}> : () -> index
    %1 = "arith.constant"() <{value = 64 : index}> : () -> index
    %2 = "arith.constant"() <{value = 0 : index}> : () -> index
    %3 = "arith.constant"() <{value = 63 : index}> : () -> index
    %4 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<64xi64>
    %5 = "memref.alloc"() <{alignment = 64 : i64, operandSegmentSizes = array<i32: 0, 0>}> : () -> memref<64xi64>
    "memref.store"(%arg0, %4, %3) : (i64, memref<64xi64>, index) -> ()
    "scf.for"(%2, %1, %0) ({
    ^bb0(%arg1: index):
      %7 = "memref.load"(%4, %arg1) : (memref<64xi64>, index) -> i64
      "memref.store"(%7, %5, %arg1) : (i64, memref<64xi64>, index) -> ()
      "scf.yield"() : () -> ()
    }) : (index, index, index) -> ()
    %6 = "memref.load"(%5, %3) : (memref<64xi64>, index) -> i64
    "func.return"(%6) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

