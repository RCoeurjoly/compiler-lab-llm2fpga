module {
  func.func @representative(%source: memref<1x1xi64>) {
    %result = memref.reinterpret_cast %source to offset: [0], sizes: [1], strides: [1] : memref<1x1xi64> to memref<1xi64, strided<[1]>>
    return
  }
}
