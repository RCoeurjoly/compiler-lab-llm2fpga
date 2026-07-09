module {
  func.func @main(%arg0: memref<i8>) {
    %c7_i8 = arith.constant 7 : i8
    memref.store %c7_i8, %arg0[] : memref<i8>
    return
  }
}
