module {
  func.func @main(%arg0: memref<i8>) {
    %true = arith.constant true
    cf.assert %true, "valid input contract"
    %c7_i8 = arith.constant 7 : i8
    memref.store %c7_i8, %arg0[] : memref<i8>
    return
  }
}
