module {
  func.func @main(%lhs_mem: memref<1xf32>, %rhs_mem: memref<1xf32>, %output: memref<1xi1>) {
    %c0 = arith.constant 0 : index
    %lhs = memref.load %lhs_mem[%c0] : memref<1xf32>
    %rhs = memref.load %rhs_mem[%c0] : memref<1xf32>
    %result = arith.cmpf ugt, %lhs, %rhs : f32
    memref.store %result, %output[%c0] : memref<1xi1>
    return
  }
}
