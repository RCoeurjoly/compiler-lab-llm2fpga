module {
  %activation = "fixed.fixture_input"() : () -> tensor<4x64xi64>
  %input_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %weight = "fixed.fixture_weight"() : () -> tensor<64x64xi64>
  %weight_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %acc = "fixed.gemv"(%activation, %input_scale, %weight, %weight_scale) {accumulator = "signed_i64_twos_complement_wrap", rows = 4 : i64, inputs = 64 : i64, outputs = 64 : i64} : (tensor<4x64xi64>, tensor<64xi64>, tensor<64x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>
  %result = "fixed.requantize"(%acc) {scale = "PER_CHANNEL_Q8_24", rounding = "nearest_ties_away_from_zero", signedness = "signed", saturation = [-128, 127], width = 8 : i64} : (tensor<4x64xi64>) -> tensor<4x64xi64>
}
