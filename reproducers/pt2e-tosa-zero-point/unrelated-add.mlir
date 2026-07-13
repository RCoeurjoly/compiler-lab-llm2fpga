module {
  func.func @unrelated_add(
      %lhs: tensor<1x1x64xi8>,
      %rhs: tensor<1x1x64xi8>) -> tensor<1x1x64xi8> {
    %sum = tosa.add %lhs, %rhs : (tensor<1x1x64xi8>, tensor<1x1x64xi8>) -> tensor<1x1x64xi8>
    return %sum : tensor<1x1x64xi8>
  }
}
