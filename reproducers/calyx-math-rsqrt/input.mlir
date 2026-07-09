module {
  func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf32>
    %inv = math.rsqrt %value : f32
    memref.store %inv, %output[%c0] : memref<1xf32>
    return
  }
}
