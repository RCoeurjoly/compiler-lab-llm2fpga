module {
  func.func @main(%arg0: memref<4xi8>, %arg1: memref<i8>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %arg0[%c0] : memref<4xi8>
    memref.store %value, %arg1[] : memref<i8>
    return
  }
}
