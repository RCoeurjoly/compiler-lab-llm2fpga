module {
  func.func @probe(%source: memref<1x4x256xi64>, %i0: index, %i1: index) -> i64 {
    %view = memref.collapse_shape %source [[0, 1], [2]] : memref<1x4x256xi64> into memref<4x256xi64>
    %value = memref.load %view[%i0, %i1] : memref<4x256xi64>
    memref.store %value, %view[%i0, %i1] : memref<4x256xi64>
    return %value : i64
  }
}
