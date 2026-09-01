module {
  func.func @direct_rank1_size1(%arg0: i64) -> i64 {
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %alloc_0 = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %c0 = arith.constant 0 : index
    memref.store %arg0, %alloc[%c0] : memref<1xi64>
    %c0_1 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c1_2 = arith.constant 1 : index
    scf.for %arg1 = %c0_1 to %c1 step %c1_2 {
      %c0_3 = arith.constant 0 : index
      %1 = arith.addi %c0_3, %arg1 : index
      %c0_4 = arith.constant 0 : index
      %2 = arith.addi %c0_4, %arg1 : index
      %3 = memref.load %alloc[%1] : memref<1xi64>
      memref.store %3, %alloc_0[%2] : memref<1xi64>
    }
    %0 = memref.load %alloc_0[%c0] : memref<1xi64>
    return %0 : i64
  }
}

