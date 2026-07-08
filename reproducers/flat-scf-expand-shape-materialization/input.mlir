module {
  func.func @main() {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %cst = arith.constant 0.000000e+00 : f32
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<1x1x2xf32>
    scf.for %i = %c0 to %c2 step %c1 {
      memref.store %cst, %alloc[%c0, %c0, %i] : memref<1x1x2xf32>
    }
    %expanded = memref.expand_shape %alloc [[0], [1], [2, 3]] output_shape [1, 1, 1, 2] : memref<1x1x2xf32> into memref<1x1x1x2xf32>
    %value = memref.load %expanded[%c0, %c0, %c0, %c0] : memref<1x1x1x2xf32>
    memref.store %value, %expanded[%c0, %c0, %c0, %c0] : memref<1x1x1x2xf32>
    return
  }
}
