module {
  func.func @representative(%arg0: memref<1xi64>, %arg1: memref<1xi64>) {
    memref.copy %arg0, %arg1 : memref<1xi64> to memref<1xi64>
    return
  }
}

