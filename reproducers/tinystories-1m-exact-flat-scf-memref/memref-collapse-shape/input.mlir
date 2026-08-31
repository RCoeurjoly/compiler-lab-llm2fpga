module {
  func.func @representative(%source: memref<1x4x256xi64>) {
    %result = memref.collapse_shape %source [[0, 1], [2]] : memref<1x4x256xi64> into memref<4x256xi64>
    return
  }
}
