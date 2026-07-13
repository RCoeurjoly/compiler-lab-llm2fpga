module {
  func.func @pt2e_zero_point(%arg0: tensor<1x1x64xf32>) -> tensor<1x1x64xi32> {
    %zero_point = "tosa.const"() <{values = dense<26> : tensor<1x1x1xi8>}> : () -> tensor<1x1x1xi8>
    %rounded_i8 = tosa.cast %arg0 : (tensor<1x1x64xf32>) -> tensor<1x1x64xi8>
    %quantized_i8 = tosa.add %rounded_i8, %zero_point : (tensor<1x1x64xi8>, tensor<1x1x1xi8>) -> tensor<1x1x64xi8>
    %dequant_input = tosa.cast %quantized_i8 : (tensor<1x1x64xi8>) -> tensor<1x1x64xi32>
    return %dequant_input : tensor<1x1x64xi32>
  }
}
