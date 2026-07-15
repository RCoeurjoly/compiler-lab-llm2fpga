module {
  func.func @nonmatching(%wide: i8, %predicate: i1) -> (f32, f64) {
    %wide_float = arith.uitofp %wide : i8 to f32
    %wide_result = arith.uitofp %predicate : i1 to f64
    return %wide_float, %wide_result : f32, f64
  }
}
