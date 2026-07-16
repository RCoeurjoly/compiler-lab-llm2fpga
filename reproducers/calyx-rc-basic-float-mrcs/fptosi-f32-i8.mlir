module {
  func.func @main(%input: memref<1xf32>, %output: memref<1xi8>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf32>
    %result = arith.fptosi %value : f32 to i8
    memref.store %result, %output[%c0] : memref<1xi8>
    return
  }
}
