module {
  func.func @representative(%source: memref<1xi64>, %target: memref<1xi64>) {
    memref.copy %source, %target : memref<1xi64> to memref<1xi64>
    return
  }
}
