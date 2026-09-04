module {
  func.func @probe(%source: memref<1xi64>, %target: memref<1xi64>) -> i64 {
    %c0 = arith.constant 0 : index
    memref.copy %source, %target : memref<1xi64> to memref<1xi64>
    %value = memref.load %target[%c0] : memref<1xi64>
    memref.store %value, %target[%c0] : memref<1xi64>
    return %value : i64
  }
}
