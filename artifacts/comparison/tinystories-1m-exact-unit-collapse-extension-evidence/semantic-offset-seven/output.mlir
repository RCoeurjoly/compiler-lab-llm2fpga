module {
  func.func @offset_nonzero(%arg0: memref<4096xi64>, %arg1: index, %arg2: i64) -> i64 {
    %c7 = arith.constant 7 : index
    %c64 = arith.constant 64 : index
    %0 = arith.muli %arg1, %c64 : index
    %1 = arith.addi %0, %c7 : index
    memref.store %arg2, %arg0[%1] : memref<4096xi64>
    %2 = memref.load %arg0[%1] : memref<4096xi64>
    return %2 : i64
  }
}

