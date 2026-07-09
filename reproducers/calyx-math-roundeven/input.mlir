module {
  func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf32>
    %rounded = math.roundeven %value : f32
    memref.store %rounded, %output[%c0] : memref<1xf32>
    return
  }
}
