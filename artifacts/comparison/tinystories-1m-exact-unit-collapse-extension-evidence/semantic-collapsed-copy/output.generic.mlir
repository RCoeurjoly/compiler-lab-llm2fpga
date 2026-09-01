"builtin.module"() ({
  "func.func"() <{function_type = (memref<4096xi64>, memref<4096xi64>) -> (), sym_name = "collapsed_copy"}> ({
  ^bb0(%arg0: memref<4096xi64>, %arg1: memref<4096xi64>):
    %0 = "arith.constant"() <{value = 7 : index}> : () -> index
    %1 = "arith.constant"() <{value = 0 : index}> : () -> index
    %2 = "arith.constant"() <{value = 64 : index}> : () -> index
    %3 = "arith.constant"() <{value = 1 : index}> : () -> index
    "scf.for"(%1, %2, %3) ({
    ^bb0(%arg2: index):
      %4 = "arith.muli"(%arg2, %2) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
      %5 = "arith.addi"(%4, %0) <{overflowFlags = #arith.overflow<none>}> : (index, index) -> index
      %6 = "memref.load"(%arg0, %5) : (memref<4096xi64>, index) -> i64
      "memref.store"(%6, %arg1, %4) : (i64, memref<4096xi64>, index) -> ()
      "scf.yield"() : () -> ()
    }) : (index, index, index) -> ()
    "func.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

