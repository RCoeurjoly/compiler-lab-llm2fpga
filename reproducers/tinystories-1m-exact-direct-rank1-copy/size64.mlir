module {
  func.func @direct_rank1_size64(%value: i64) -> i64 {
    %source = memref.alloc() {alignment = 64 : i64} : memref<64xi64>
    %target = memref.alloc() {alignment = 64 : i64} : memref<64xi64>
    %c63 = arith.constant 63 : index
    memref.store %value, %source[%c63] : memref<64xi64>
    memref.copy %source, %target : memref<64xi64> to memref<64xi64>
    %observed = memref.load %target[%c63] : memref<64xi64>
    return %observed : i64
  }
}
