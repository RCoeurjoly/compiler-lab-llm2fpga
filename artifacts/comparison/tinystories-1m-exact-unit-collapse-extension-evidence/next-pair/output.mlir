module {
  func.func @representative() -> i64 {
    %c0_i64 = arith.constant 0 : i64
    %c0 = arith.constant 0 : index
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %alloc_0 = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    memref.store %c0_i64, %alloc[%c0] : memref<1xi64>
    memref.copy %alloc, %alloc_0 : memref<1xi64> to memref<1xi64>
    %0 = memref.load %alloc_0[%c0] : memref<1xi64>
    return %0 : i64
  }
}

