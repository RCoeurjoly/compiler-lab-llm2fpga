module {
  func.func @identity_offset(%arg0: memref<4096xi64>, %arg1: index, %arg2: index, %arg3: i64) -> i64 {
    %c64 = arith.constant 64 : index
    %0 = arith.muli %arg1, %c64 : index
    %1 = arith.addi %0, %arg2 : index
    memref.store %arg3, %arg0[%1] : memref<4096xi64>
    %2 = memref.load %arg0[%1] : memref<4096xi64>
    return %2 : i64
  }
}

