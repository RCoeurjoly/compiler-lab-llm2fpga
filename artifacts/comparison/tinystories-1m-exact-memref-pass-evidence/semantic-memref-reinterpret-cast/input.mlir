module {
  func.func @probe(%source: memref<1x1xi64>) -> i64 {
    %c0 = arith.constant 0 : index
    %view = memref.reinterpret_cast %source to offset: [0], sizes: [1], strides: [1] : memref<1x1xi64> to memref<1xi64, strided<[1]>>
    %value = memref.load %view[%c0] : memref<1xi64, strided<[1]>>
    memref.store %value, %view[%c0] : memref<1xi64, strided<[1]>>
    return %value : i64
  }
}
