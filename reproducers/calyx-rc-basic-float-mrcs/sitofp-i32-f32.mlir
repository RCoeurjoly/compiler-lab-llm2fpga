module {
  func.func @main(%input: memref<1xi32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xi32>
    %result = arith.sitofp %value : i32 to f32
    memref.store %result, %output[%c0] : memref<1xf32>
    return
  }
}
