module {
  func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %c3_i64 = arith.constant 3 : i64
    %value = memref.load %input[%c0] : memref<1xf32>
    %result = math.fpowi %value, %c3_i64 : f32, i64
    memref.store %result, %output[%c0] : memref<1xf32>
    return
  }
}
