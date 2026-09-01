module {
  func.func @direct_rank1_size1(%value: i64) -> i64 {
    %source = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %target = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %c0 = arith.constant 0 : index
    memref.store %value, %source[%c0] : memref<1xi64>
    memref.copy %source, %target : memref<1xi64> to memref<1xi64>
    %observed = memref.load %target[%c0] : memref<1xi64>
    return %observed : i64
  }
}
