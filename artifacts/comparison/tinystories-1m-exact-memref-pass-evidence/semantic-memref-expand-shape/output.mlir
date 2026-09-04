module {
  func.func @probe(%arg0: memref<1xi64>) -> i64 {
    %c0 = arith.constant 0 : index
    %0 = memref.load %arg0[%c0] : memref<1xi64>
    memref.store %0, %arg0[%c0] : memref<1xi64>
    return %0 : i64
  }
}

