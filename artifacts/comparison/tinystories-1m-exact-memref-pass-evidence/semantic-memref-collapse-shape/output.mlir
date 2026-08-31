module {
  func.func @probe(%arg0: memref<1024xi64>) -> i64 {
    %c515 = arith.constant 515 : index
    %0 = memref.load %arg0[%c515] : memref<1024xi64>
    memref.store %0, %arg0[%c515] : memref<1024xi64>
    return %0 : i64
  }
}

