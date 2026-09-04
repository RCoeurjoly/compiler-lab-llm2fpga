module {
  func.func @offset_zero(%arg0: memref<4096xi64>, %arg1: index, %arg2: i64) -> i64 {
    %c64 = arith.constant 64 : index
    %0 = arith.muli %arg1, %c64 : index
    memref.store %arg2, %arg0[%0] : memref<4096xi64>
    %1 = memref.load %arg0[%0] : memref<4096xi64>
    return %1 : i64
  }
}

