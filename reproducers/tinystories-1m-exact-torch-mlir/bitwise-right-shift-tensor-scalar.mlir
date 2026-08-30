module {
  func.func @main(%arg0: !torch.vtensor<[4,1],si64>) -> !torch.vtensor<[4,1],si64> {
    %int1 = torch.constant.int 1
    %0 = torch.operator "torch.aten.bitwise_right_shift.Tensor_Scalar"(%arg0, %int1) : (!torch.vtensor<[4,1],si64>, !torch.int) -> !torch.vtensor<[4,1],si64>
    return %0 : !torch.vtensor<[4,1],si64>
  }
}
