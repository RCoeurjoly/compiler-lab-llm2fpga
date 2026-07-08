module {
  func.func @main() {
    %c0 = arith.constant 0 : index
    %value = arith.constant 1.000000e-05 : f32
    %out = memref.alloc() : memref<1xf32>
    memref.store %value, %out[%c0] : memref<1xf32>
    return
  }
}
