module {
  func.func @unsupported_rank_reducing(%source: memref<64x64xi64>, %i0: index) -> i64 {
    %view = memref.subview %source[0, 0] [1, 64] [1, 1]
      : memref<64x64xi64> to memref<64xi64>
    %loaded = memref.load %view[%i0] : memref<64xi64>
    return %loaded : i64
  }
}
