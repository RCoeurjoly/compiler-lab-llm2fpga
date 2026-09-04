module {
  // @main is deliberately memory-backed for the bounded SCF-to-Calyx probe.
  func.func @main(%input: memref<1xi64>, %output: memref<1xi64>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xi64>
    %absolute = math.absi %value : i64
    memref.store %absolute, %output[%c0] : memref<1xi64>
    return
  }

  // These are exact-match negative controls and must remain math.absi.
  func.func private @scalar_i32(%input: memref<1xi32>, %output: memref<1xi32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xi32>
    %absolute = math.absi %value : i32
    memref.store %absolute, %output[%c0] : memref<1xi32>
    return
  }

  func.func private @vector_i64(%input: memref<1xvector<2xi64>>, %output: memref<1xvector<2xi64>>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xvector<2xi64>>
    %absolute = math.absi %value : vector<2xi64>
    memref.store %absolute, %output[%c0] : memref<1xvector<2xi64>>
    return
  }
}
