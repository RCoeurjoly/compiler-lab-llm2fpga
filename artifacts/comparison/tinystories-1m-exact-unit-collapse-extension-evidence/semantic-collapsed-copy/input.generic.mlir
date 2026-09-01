"builtin.module"() ({
  "func.func"() <{function_type = (memref<64x64xi64>, memref<64x64xi64>) -> (), sym_name = "collapsed_copy"}> ({
  ^bb0(%arg0: memref<64x64xi64>, %arg1: memref<64x64xi64>):
    %0 = "memref.subview"(%arg0) <{operandSegmentSizes = array<i32: 1, 0, 0, 0>, static_offsets = array<i64: 0, 7>, static_sizes = array<i64: 64, 1>, static_strides = array<i64: 1, 1>}> : (memref<64x64xi64>) -> memref<64x1xi64, strided<[64, 1], offset: 7>>
    %1 = "memref.collapse_shape"(%0) <{reassociation = [[0, 1]]}> : (memref<64x1xi64, strided<[64, 1], offset: 7>>) -> memref<64xi64, strided<[64], offset: 7>>
    %2 = "memref.subview"(%arg1) <{operandSegmentSizes = array<i32: 1, 0, 0, 0>, static_offsets = array<i64: 0, 0>, static_sizes = array<i64: 64, 1>, static_strides = array<i64: 1, 1>}> : (memref<64x64xi64>) -> memref<64x1xi64, strided<[64, 1]>>
    %3 = "memref.collapse_shape"(%2) <{reassociation = [[0, 1]]}> : (memref<64x1xi64, strided<[64, 1]>>) -> memref<64xi64, strided<[64]>>
    "memref.copy"(%1, %3) : (memref<64xi64, strided<[64], offset: 7>>, memref<64xi64, strided<[64]>>) -> ()
    "func.return"() : () -> ()
  }) : () -> ()
}) : () -> ()

