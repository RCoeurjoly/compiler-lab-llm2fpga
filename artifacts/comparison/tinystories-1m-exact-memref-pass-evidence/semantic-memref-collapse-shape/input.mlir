module {
  func.func @probe(%source: memref<1x4x256xi64>) -> i64 {
    %c2 = arith.constant 2 : index
    %c3 = arith.constant 3 : index
    %view = memref.collapse_shape %source [[0, 1], [2]] : memref<1x4x256xi64> into memref<4x256xi64>
    %value = memref.load %view[%c2, %c3] : memref<4x256xi64>
    memref.store %value, %view[%c2, %c3] : memref<4x256xi64>
    return %value : i64
  }
}
