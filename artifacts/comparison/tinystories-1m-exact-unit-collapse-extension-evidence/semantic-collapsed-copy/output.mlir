module {
  func.func @collapsed_copy(%arg0: memref<4096xi64>, %arg1: memref<4096xi64>) {
    %c7 = arith.constant 7 : index
    %c0 = arith.constant 0 : index
    %c64 = arith.constant 64 : index
    %c1 = arith.constant 1 : index
    scf.for %arg2 = %c0 to %c64 step %c1 {
      %0 = arith.muli %arg2, %c64 : index
      %1 = arith.addi %0, %c7 : index
      %2 = memref.load %arg0[%1] : memref<4096xi64>
      memref.store %2, %arg1[%0] : memref<4096xi64>
    }
    return
  }
}

