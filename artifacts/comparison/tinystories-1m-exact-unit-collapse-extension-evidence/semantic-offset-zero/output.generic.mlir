"builtin.module"() ({
  "func.func"() <{function_type = (memref<4096xi64>, index, i64) -> i64, sym_name = "offset_zero"}> ({
  ^bb0(%arg0: memref<4096xi64>, %arg1: index, %arg2: i64):
    %0 = "arith.constant"() <{value = 64 : index}> : () -> index
    %1 = "arith.muli"(%arg1, %0) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
    "memref.store"(%arg2, %arg0, %1) : (i64, memref<4096xi64>, index) -> ()
    %2 = "memref.load"(%arg0, %1) : (memref<4096xi64>, index) -> i64
    "func.return"(%2) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

