module {
  func.func @main(%arg0: !torch.vtensor<[4,64],si64>) -> !torch.vtensor<[4,64],si64> {
    %int16 = torch.constant.int 16
    %0 = torch.operator "torch.aten.bitwise_left_shift.Tensor_Scalar"(%arg0, %int16) : (!torch.vtensor<[4,64],si64>, !torch.int) -> !torch.vtensor<[4,64],si64>
    return %0 : !torch.vtensor<[4,64],si64>
  }
}
