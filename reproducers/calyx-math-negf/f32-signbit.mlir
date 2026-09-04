module {
  // @main is deliberately memory-backed so the transformed scalar f32 path
  // can be probed by SCF-to-Calyx without involving the full model.
  func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf32>
    %negated = arith.negf %value : f32
    memref.store %negated, %output[%c0] : memref<1xf32>
    return
  }

  // These negative controls are intentionally outside the scalar f32
  // legalization boundary and must remain arith.negf operations.
  func.func private @scalar_f64(%input: memref<1xf64>, %output: memref<1xf64>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf64>
    %negated = arith.negf %value : f64
    memref.store %negated, %output[%c0] : memref<1xf64>
    return
  }

  func.func private @vector_f32(%input: memref<1xvector<2xf32>>, %output: memref<1xvector<2xf32>>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xvector<2xf32>>
    %negated = arith.negf %value : vector<2xf32>
    memref.store %negated, %output[%c0] : memref<1xvector<2xf32>>
    return
  }
}
