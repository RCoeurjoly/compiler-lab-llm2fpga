module {
  func.func @representative(%source: memref<1xi64>) {
    %result = memref.expand_shape %source [[0, 1]] output_shape [1, 1] : memref<1xi64> into memref<1x1xi64>
    return
  }
}
