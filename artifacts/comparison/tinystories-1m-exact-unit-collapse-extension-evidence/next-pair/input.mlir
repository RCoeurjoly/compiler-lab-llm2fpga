module {
  func.func @representative() -> i64 {
    %alloc_379 = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %alloc_381 = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    %c0 = arith.constant 0 : index
    %value = arith.constant 0 : i64
    memref.store %value, %alloc_379[%c0] : memref<1xi64>
    memref.copy %alloc_379, %alloc_381 : memref<1xi64> to memref<1xi64>
    %loaded = memref.load %alloc_381[%c0] : memref<1xi64>
    return %loaded : i64
  }
}
