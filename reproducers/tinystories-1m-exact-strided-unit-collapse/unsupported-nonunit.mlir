module {
  func.func @unsupported_nonunit(%source: memref<64x64xi64>, %i: index) -> i64 {
    %sub = memref.subview %source[0, 0] [64, 2] [1, 1]
      : memref<64x64xi64> to memref<64x2xi64, strided<[64, 1]>>
    %flat = memref.collapse_shape %sub [[0, 1]]
      : memref<64x2xi64, strided<[64, 1]>> into memref<128xi64, strided<[1]>>
    %loaded = memref.load %flat[%i] : memref<128xi64, strided<[1]>>
    return %loaded : i64
  }
}
