module {
  func.func @main(%arg0: memref<4xi8>, %arg1: memref<i8>) {
    %c0 = arith.constant 0 : index
    %view = memref.reinterpret_cast %arg0 to offset: [0], sizes: [2, 2], strides: [2, 1] : memref<4xi8> to memref<2x2xi8>
    %value = memref.load %view[%c0, %c0] : memref<2x2xi8>
    memref.store %value, %arg1[] : memref<i8>
    return
  }
}
