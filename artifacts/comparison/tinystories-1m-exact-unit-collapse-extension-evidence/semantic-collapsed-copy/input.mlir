module {
  func.func @collapsed_copy(%source: memref<64x64xi64>, %target: memref<64x64xi64>) {
    %source_sub = memref.subview %source[0, 7] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1], offset: 7>>
    %source_flat = memref.collapse_shape %source_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1], offset: 7>> into memref<64xi64, strided<[64], offset: 7>>
    %target_sub = memref.subview %target[0, 0] [64, 1] [1, 1]
      : memref<64x64xi64> to memref<64x1xi64, strided<[64, 1]>>
    %target_flat = memref.collapse_shape %target_sub [[0, 1]]
      : memref<64x1xi64, strided<[64, 1]>> into memref<64xi64, strided<[64]>>
    memref.copy %source_flat, %target_flat
      : memref<64xi64, strided<[64], offset: 7>> to memref<64xi64, strided<[64]>>
    return
  }
}
