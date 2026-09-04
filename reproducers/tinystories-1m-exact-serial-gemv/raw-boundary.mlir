module {
  func.func @main(
      %scaled_input_q24: !torch.vtensor<[1,64],si64>,
      %weight_codes: !torch.vtensor<[64,64],si64>
  ) -> !torch.vtensor<[1,64],si64> {
    %0 = torch.operator "torch.llm2fpga.serial_gemv"(
      %scaled_input_q24, %weight_codes
    ) : (!torch.vtensor<[1,64],si64>, !torch.vtensor<[64,64],si64>) -> !torch.vtensor<[1,64],si64>
    return %0 : !torch.vtensor<[1,64],si64>
  }
}
