module {
  func.func @offset_nonzero(%source: memref<64x64xi64>, %i: index, %value: i64) -> i64 {
    %sub = memref.subview %source[0, 7] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: 7>> into memref<64xi64, strided<[64], offset: 7>>
    memref.store %value, %flat[%i]
      : memref<64xi64, strided<[64], offset: 7>>
    %loaded = memref.load %flat[%i]
      : memref<64xi64, strided<[64], offset: 7>>
    return %loaded : i64
  }
}
