module {
  %activation = "fixed.fixture_input"() : () -> tensor<4x64xi64>
  %input_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %weight = "fixed.fixture_weight"() : () -> tensor<64x64xi64>
  %weight_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %acc = "fixed.gemv"(%activation, %input_scale, %weight, %weight_scale) {rows = 4 : i64, inputs = 64 : i64, outputs = 64 : i64, accumulator = "signed_i64_twos_complement_wrap"} : (tensor<4x64xi64>, tensor<64xi64>, tensor<64x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>
  %output_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %result = "fixed.requantize"(%acc, %output_scale) {fixture_sha256 = "d30d469ecc0c7a679c097577affd12afe9cb2fc250a252caeaba141cdeb55771", scale_sha256 = "5f03987f540507d246c4ab94e3e2176d254e68e06049aa0cdfe3466519c9b7f8", rounding = "nearest_ties_away_from_zero", signedness = "signed", saturation = [-128, 127], width = 8 : i64, contract_sha256 = "8a9c0fb3230ab64d08f84d270b4a1cc669011db2f5180ec9c77df50ec86b9eed"} : (tensor<4x64xi64>, tensor<64xi64>) -> tensor<4x64xi64>
}
