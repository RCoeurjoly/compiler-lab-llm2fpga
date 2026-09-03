module {
  %activation = "fixed.fixture_input"() : () -> tensor<4x64xi64>
  %input_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
  %weight = "fixed.fixture_weight"() : () -> tensor<64x64xi64>
  %weight_scale = "fixed.fixture_scale"() : () -> tensor<64xi64>
}
