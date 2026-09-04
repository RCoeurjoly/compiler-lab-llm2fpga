module {
  func.func @offset_zero(%source: memref<64x64xi64>, %i: index, %value: i64) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    memref.store %value, %flat[%i] : memref<64xi64, strided<[64]>>
    %loaded = memref.load %flat[%i] : memref<64xi64, strided<[64]>>
    return %loaded : i64
  }
}
