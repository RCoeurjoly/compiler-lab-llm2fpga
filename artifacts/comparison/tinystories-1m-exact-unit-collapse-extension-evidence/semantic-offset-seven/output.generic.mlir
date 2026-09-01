"builtin.module"() ({
  "func.func"() <{function_type = (memref<4096xi64>, index, i64) -> i64, sym_name = "offset_nonzero"}> ({
  ^bb0(%arg0: memref<4096xi64>, %arg1: index, %arg2: i64):
    %0 = "arith.constant"() <{value = 7 : index}> : () -> index
    %1 = "arith.constant"() <{value = 64 : index}> : () -> index
    %2 = "arith.muli"(%arg1, %1) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
    %3 = "arith.addi"(%2, %0) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
    "memref.store"(%arg2, %arg0, %3) : (i64, memref<4096xi64>, index) -> ()
    %4 = "memref.load"(%arg0, %3) : (memref<4096xi64>, index) -> i64
    "func.return"(%4) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

