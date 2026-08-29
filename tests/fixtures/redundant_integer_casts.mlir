module {
  func.func @identity(%arg0: i32, %arg1: i8) -> (i32, i8) {
    %a = arith.extsi %arg0 : i32 to i64
    %b = arith.trunci %a : i64 to i32
    %c = arith.extui %arg1 : i8 to i16
    %d = arith.trunci %c : i16 to i8
    %e = arith.extsi %arg1 : i8 to i32
    %f = arith.trunci %e : i32 to i16
    return %b, %d : i32, i8
  }
}
