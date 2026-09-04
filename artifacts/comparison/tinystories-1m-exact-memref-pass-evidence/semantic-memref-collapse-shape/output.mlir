module {
  func.func @probe(%arg0: memref<1024xi64>, %arg1: index, %arg2: index) -> i64 {
    %c256 = arith.constant 256 : index
    %0 = arith.muli %arg1, %c256 : index
    %1 = arith.addi %0, %arg2 : index
    %2 = memref.load %arg0[%1] : memref<1024xi64>
    memref.store %2, %arg0[%1] : memref<1024xi64>
    return %2 : i64
  }
}

