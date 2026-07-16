// Reduced ABI transcription of the exact RC flat-SCF @main entrypoint.
// The source artifact and its hash are documented in README.md.
module {
  func.func @main(%arg0: memref<2x2xi8>, %arg1: memref<2x2xi8>, %arg2: memref<2x2xi8>, %arg3: memref<2x2xi8>, %arg4: memref<8x2xi8>, %arg5: memref<2x8xi8>, %arg6: memref<2x2xi8>, %arg7: memref<2x2xi8>, %arg8: memref<2x2xi8>, %arg9: memref<2x2xi8>, %arg10: memref<8x2xi8>, %arg11: memref<2x8xi8>, %arg12: memref<6x2xi8>, %arg13: memref<i8>, %arg14: memref<i8>, %arg15: memref<i8>, %arg16: memref<i8>, %arg17: memref<i8>, %arg18: memref<i8>, %arg19: memref<i8>, %arg20: memref<i8>, %arg21: memref<1x1x9x9xi1>, %arg22: memref<f32>, %arg23: memref<1x1x9x9xi1>, %arg24: memref<f32>, %arg25: memref<1x8xi64>, %arg26: memref<1x8x6xi8>) {
    %source = memref.alloc() : memref<1x8x6xi8>
    memref.copy %source, %arg26 : memref<1x8x6xi8> to memref<1x8x6xi8>
    return
  }
}
