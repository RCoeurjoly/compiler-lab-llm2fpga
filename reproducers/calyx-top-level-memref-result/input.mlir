module {
  func.func @kernel(%memory: memref<4xi32>) -> i32 {
    %c0 = arith.constant 0 : index
    %value = memref.load %memory[%c0] : memref<4xi32>
    return %value : i32
  }
}
