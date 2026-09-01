module {
  func.func @direct_rank1_size1(%arg0: i64) -> i64 {
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %alloc_0 = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    memref.store %arg0, %alloc[%c0] : memref<1xi64>
    %0 = memref.load %alloc[%c0] : memref<1xi64>
    memref.store %0, %alloc_0[%c0] : memref<1xi64>
    %1 = memref.load %alloc_0[%c0] : memref<1xi64>
    return %1 : i64
  }
}

