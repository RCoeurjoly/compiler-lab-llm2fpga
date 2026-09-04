module {
  func.func @nonzero_offset_stride(%source: memref<64x64xi64>, %i0: index, %i1: index, %value: i64) -> i64 {
    %view = memref.subview %source[1, 0] [16, 8] [2, 2]
      : memref<64x64xi64> to memref<16x8xi64, strided<[128, 2], offset: 64>>
    memref.store %value, %view[%i0, %i1]
      : memref<16x8xi64, strided<[128, 2], offset: 64>>
    %loaded = memref.load %view[%i0, %i1]
      : memref<16x8xi64, strided<[128, 2], offset: 64>>
    return %loaded : i64
  }
}
