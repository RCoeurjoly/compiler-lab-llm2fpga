"builtin.module"() ({
  "func.func"() <{function_type = (memref<64x64xi64>, index, i64) -> i64, sym_name = "offset_nonzero"}> ({
  ^bb0(%arg0: memref<64x64xi64>, %arg1: index, %arg2: i64):
    %0 = "memref.subview"(%arg0) <{operandSegmentSizes = array<i32: 1, 0, 0, 0>, static_offsets = array<i64: 0, 7>, static_sizes = array<i64: 64, 1>, static_strides = array<i64: 1, 1>}> : (memref<64x64xi64>) -> memref<64x1xi64, strided<[64, 1], offset: 7>>
    %1 = "memref.collapse_shape"(%0) <{reassociation = [[0, 1]]}> : (memref<64x1xi64, strided<[64, 1], offset: 7>>) -> memref<64xi64, strided<[64], offset: 7>>
    "memref.store"(%arg2, %1, %arg1) : (i64, memref<64xi64, strided<[64], offset: 7>>, index) -> ()
    %2 = "memref.load"(%1, %arg1) : (memref<64xi64, strided<[64], offset: 7>>, index) -> i64
    "func.return"(%2) : (i64) -> ()
  }) : () -> ()
}) : () -> ()

