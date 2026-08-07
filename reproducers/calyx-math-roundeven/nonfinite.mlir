module {
  func.func @round_q4_12_overflow() -> f32 {
    %negative_max = arith.constant -3.40282347E+38 : f32
    %q4_12_scale = arith.constant 2.44140625E-4 : f32
    %overflow = arith.divf %negative_max, %q4_12_scale : f32
    %rounded = math.roundeven %overflow : f32
    return %rounded : f32
  }
}
