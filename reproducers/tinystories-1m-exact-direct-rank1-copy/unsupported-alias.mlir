module {
  func.func @unsupported_alias_through_view(%value: i64) -> i64 {
    %buffer = memref.alloc() : memref<4xi64>
    %view = memref.cast %buffer
      : memref<4xi64> to memref<4xi64, strided<[?], offset: ?>>
    %c0 = arith.constant 0 : index
    memref.store %value, %buffer[%c0] : memref<4xi64>
    memref.copy %buffer, %view
      : memref<4xi64> to memref<4xi64, strided<[?], offset: ?>>
    %observed = memref.load %view[%c0]
      : memref<4xi64, strided<[?], offset: ?>>
    return %observed : i64
  }
}
