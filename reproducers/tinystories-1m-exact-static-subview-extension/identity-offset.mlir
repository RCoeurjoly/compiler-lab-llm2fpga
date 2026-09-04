module {
  func.func @identity_offset(%source: memref<64x64xi64>, %i0: index, %i1: index, %value: i64) -> i64 {
    %view = memref.subview %source[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    memref.store %value, %view[%i0, %i1]
      : memref<64x1xi64, strided<[64, 1]>>
    %loaded = memref.load %view[%i0, %i1]
      : memref<64x1xi64, strided<[64, 1]>>
    return %loaded : i64
  }
}
