module {
  func.func @direct_rank1_size64(%arg0: i64) -> i64 {
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<64xi64>
    %alloc_0 = memref.alloc() {alignment = 64 : i64} : memref<64xi64>
    %c63 = arith.constant 63 : index
    memref.store %arg0, %alloc[%c63] : memref<64xi64>
    %c0 = arith.constant 0 : index
    %c64 = arith.constant 64 : index
    %c1 = arith.constant 1 : index
    scf.for %arg1 = %c0 to %c64 step %c1 {
      %c0_1 = arith.constant 0 : index
      %1 = arith.addi %c0_1, %arg1 : index
      %c0_2 = arith.constant 0 : index
      %2 = arith.addi %c0_2, %arg1 : index
      %3 = memref.load %alloc[%1] : memref<64xi64>
      memref.store %3, %alloc_0[%2] : memref<64xi64>
    }
    %0 = memref.load %alloc_0[%c63] : memref<64xi64>
    return %0 : i64
  }
}

