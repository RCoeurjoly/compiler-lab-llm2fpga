module {
  func.func @nonzero_offset_stride(%arg0: memref<4096xi64>, %arg1: index, %arg2: index, %arg3: i64) -> i64 {
    %c2 = arith.constant 2 : index
    %c64 = arith.constant 64 : index
    %c128 = arith.constant 128 : index
    %0 = arith.muli %arg1, %c128 : index
    %1 = arith.addi %0, %c64 : index
    %2 = arith.muli %arg2, %c2 : index
    %3 = arith.addi %1, %2 : index
    memref.store %arg3, %arg0[%3] : memref<4096xi64>
    %4 = memref.load %arg0[%3] : memref<4096xi64>
    return %4 : i64
  }
}

