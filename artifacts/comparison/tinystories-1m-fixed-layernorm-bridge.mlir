module {
  func.func @tinystories_1m_block0_ln1_token3(%input: tensor<64xi32>, %gamma: tensor<64xi32>, %beta: tensor<64xi32>) -> tensor<64xi32> {
    %0 = "llm2fpga.fixed_layer_norm_q16_16"(%input, %gamma, %beta) <{affine_shift = 16 : i64, delta_width = 33 : i64, division = "signed_truncation_toward_zero", epsilon_q32 = 42950 : i64, input_fraction_bits = 16 : i64, input_width = 32 : i64, mean_accumulator_width = 64 : i64, normalized_width = 64 : i64, output_overflow = "twos_complement_wrap", output_width = 32 : i64, parameter_fraction_bits = 16 : i64, parameter_width = 32 : i64, reduction_order = "ascending_index_0_to_63", sqrt = "floor_integer_restoring", square_width = 66 : i64, token_index = 3 : i64, variance_sum_width = 72 : i64, variance_width = 64 : i64}> : (tensor<64xi32>, tensor<64xi32>, tensor<64xi32>) -> tensor<64xi32>
    return %0 : tensor<64xi32>
  }
}
