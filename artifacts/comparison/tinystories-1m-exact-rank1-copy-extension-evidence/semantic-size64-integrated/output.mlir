module {
  func.func @direct_rank1_size64(%arg0: i64) -> i64 {
    %c1 = arith.constant 1 : index
    %c64 = arith.constant 64 : index
    %c0 = arith.constant 0 : index
    %c63 = arith.constant 63 : index
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<64xi64>
    %alloc_0 = memref.alloc() {alignment = 64 : i64} : memref<64xi64>
    memref.store %arg0, %alloc[%c63] : memref<64xi64>
    scf.for %arg1 = %c0 to %c64 step %c1 {
      %1 = memref.load %alloc[%arg1] : memref<64xi64>
      memref.store %1, %alloc_0[%arg1] : memref<64xi64>
    }
    %0 = memref.load %alloc_0[%c63] : memref<64xi64>
    return %0 : i64
  }
}

