module {
  func.func @representative(%source: memref<64x64xi64>) {
    %result = memref.subview %source[0, 0] [64, 1] [1, 1] : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    return
  }
}
