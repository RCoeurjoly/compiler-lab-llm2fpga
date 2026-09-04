module {
  func.func @probe(%arg0: memref<1xi64>, %arg1: memref<1xi64>) -> i64 {
    %c0 = arith.constant 0 : index
    memref.copy %arg0, %arg1 : memref<1xi64> to memref<1xi64>
    %0 = memref.load %arg1[%c0] : memref<1xi64>
    memref.store %0, %arg1[%c0] : memref<1xi64>
    return %0 : i64
  }
}

