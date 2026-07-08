module {
  func.func @main() {
    %c0 = arith.constant 0 : index
    %cst64 = arith.constant 1.000000e-05 : f64
    %value = arith.truncf %cst64 : f64 to f32
    %out = memref.alloc() : memref<1xf32>
    memref.store %value, %out[%c0] : memref<1xf32>
    return
  }
}
