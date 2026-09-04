module {
  func.func @probe(%source: memref<1xi64>) -> i64 {
    %c0 = arith.constant 0 : index
    %view = memref.expand_shape %source [[0, 1]] output_shape [1, 1] : memref<1xi64> into memref<1x1xi64>
    %value = memref.load %view[%c0, %c0] : memref<1x1xi64>
    memref.store %value, %view[%c0, %c0] : memref<1x1xi64>
    return %value : i64
  }
}
