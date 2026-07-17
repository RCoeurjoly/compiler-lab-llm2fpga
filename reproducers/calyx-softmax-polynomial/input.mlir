module {
  func.func @main(%input: memref<1xf32>, %output: memref<1xf32>) {
    %c0 = arith.constant 0 : index
    %x = memref.load %input[%c0] : memref<1xf32>
    %x2 = arith.mulf %x, %x : f32
    %x3 = arith.mulf %x2, %x : f32
    %x4 = arith.mulf %x3, %x : f32
    %x5 = arith.mulf %x4, %x : f32
    %c1 = arith.constant 1.0 : f32
    %c2 = arith.constant 0.5 : f32
    %c6 = arith.constant 0.16666666666666666 : f32
    %c24 = arith.constant 0.041666666666666664 : f32
    %c120 = arith.constant 0.008333333333333333 : f32
    %t2 = arith.mulf %x2, %c2 : f32
    %t3 = arith.mulf %x3, %c6 : f32
    %t4 = arith.mulf %x4, %c24 : f32
    %t5 = arith.mulf %x5, %c120 : f32
    %a = arith.addf %c1, %x : f32
    %b = arith.addf %a, %t2 : f32
    %c = arith.addf %b, %t3 : f32
    %d = arith.addf %c, %t4 : f32
    %result = arith.addf %d, %t5 : f32
    memref.store %result, %output[%c0] : memref<1xf32>
    return
  }
}
