module attributes {calyx.entrypoint = "llm2fpga_serial_gemv_program_1_64_64"} {
  // generated_from_descriptor: compiler-owned serial GEMV, not imported RTL.
  calyx.component @llm2fpga_serial_gemv_program_1_64_64(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %activation.addr0, %activation.clk, %activation.reset, %activation.content_en, %activation.write_en, %activation.write_data, %activation.read_data, %activation.done = calyx.seq_mem @activation <[64] x 64> [6] {external = true} : i6, i1, i1, i1, i1, i64, i64, i1
    %weights.addr0, %weights.clk, %weights.reset, %weights.content_en, %weights.write_en, %weights.write_data, %weights.read_data, %weights.done = calyx.seq_mem @weights <[4096] x 64> [12] {external = true} : i12, i1, i1, i1, i1, i64, i64, i1
    %results.addr0, %results.clk, %results.reset, %results.content_en, %results.write_en, %results.write_data, %results.read_data, %results.done = calyx.seq_mem @results <[64] x 64> [6] {external = true} : i6, i1, i1, i1, i1, i64, i64, i1
    %llm2fpga_serial_gemv_instance.clk, %llm2fpga_serial_gemv_instance.reset, %llm2fpga_serial_gemv_instance.go, %llm2fpga_serial_gemv_instance.done = calyx.instance @llm2fpga_serial_gemv_instance of @llm2fpga_serial_gemv_64_64 : i1, i1, i1, i1
    calyx.wires {
    }
    calyx.control {
      calyx.invoke @llm2fpga_serial_gemv_instance[activation = activation, weights = weights, results = results]() -> ()
    }
  } {toplevel}
  // generated_from_descriptor rows=1 outputs=64 inputs=64 mac_order=ascending_i64_wrap
  calyx.component @llm2fpga_serial_gemv_64_64(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %activation.addr0, %activation.clk, %activation.reset, %activation.content_en, %activation.write_en, %activation.write_data, %activation.read_data, %activation.done = calyx.seq_mem @activation <[64] x 64> [6] : i6, i1, i1, i1, i1, i64, i64, i1
    %weights.addr0, %weights.clk, %weights.reset, %weights.content_en, %weights.write_en, %weights.write_data, %weights.read_data, %weights.done = calyx.seq_mem @weights <[4096] x 64> [12] : i12, i1, i1, i1, i1, i64, i64, i1
    %results.addr0, %results.clk, %results.reset, %results.content_en, %results.write_en, %results.write_data, %results.read_data, %results.done = calyx.seq_mem @results <[64] x 64> [6] : i6, i1, i1, i1, i1, i64, i64, i1
    %true = hw.constant true
    %false = hw.constant false
    %zero_i64 = hw.constant 0 : i64
    %one_i64 = hw.constant 1 : i64
    %input_limit_i64 = hw.constant 64 : i64
    %output_limit_i64 = hw.constant 64 : i64
    %k_counter.in, %k_counter.write_en, %k_counter.clk, %k_counter.reset, %k_counter.out, %k_counter.done = calyx.register @k_counter : i64, i1, i1, i1, i64, i1
    %output_counter.in, %output_counter.write_en, %output_counter.clk, %output_counter.reset, %output_counter.out, %output_counter.done = calyx.register @output_counter : i64, i1, i1, i1, i64, i1
    %accumulator.in, %accumulator.write_en, %accumulator.clk, %accumulator.reset, %accumulator.out, %accumulator.done = calyx.register @accumulator : i64, i1, i1, i1, i64, i1
    %mac_mul.clk, %mac_mul.reset, %mac_mul.go, %mac_mul.left, %mac_mul.right, %mac_mul.out, %mac_mul.done = calyx.std_mult_pipe @mac_mul : i1, i1, i1, i64, i64, i64, i1
    %mac_add.left, %mac_add.right, %mac_add.out = calyx.std_add @mac_add : i64, i64, i64
    %next_k.left, %next_k.right, %next_k.out = calyx.std_add @next_k : i64, i64, i64
    %next_output.left, %next_output.right, %next_output.out = calyx.std_add @next_output : i64, i64, i64
    %k_less.left, %k_less.right, %k_less.out = calyx.std_lt @k_less : i64, i64, i1
    %output_less.left, %output_less.right, %output_less.out = calyx.std_lt @output_less : i64, i64, i1
    calyx.wires {
      calyx.comb_group @k_not_done {
        calyx.assign %k_less.left = %k_counter.out : i64
        calyx.assign %k_less.right = %input_limit_i64 : i64
      }
      calyx.comb_group @output_not_done {
        calyx.assign %output_less.left = %output_counter.out : i64
        calyx.assign %output_less.right = %output_limit_i64 : i64
      }
      calyx.group @mac_step {
        calyx.assign %mac_mul.left = %activation.read_data : i64
        calyx.assign %mac_mul.right = %weights.read_data : i64
        calyx.assign %mac_mul.go = %true : i1
        calyx.assign %mac_add.left = %accumulator.out : i64
        calyx.assign %mac_add.right = %mac_mul.out : i64
        calyx.assign %accumulator.in = %mac_add.out : i64
        calyx.assign %accumulator.write_en = %true : i1
        calyx.assign %next_k.left = %k_counter.out : i64
        calyx.assign %next_k.right = %one_i64 : i64
        calyx.assign %k_counter.in = %next_k.out : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.assign %activation.content_en = %true : i1
        calyx.assign %weights.content_en = %true : i1
        calyx.assign %results.content_en = %true : i1
        calyx.assign %results.write_en = %false : i1
        calyx.group_done %k_counter.done : i1
      }
      calyx.group @advance_output {
        calyx.assign %next_output.left = %output_counter.out : i64
        calyx.assign %next_output.right = %one_i64 : i64
        calyx.assign %output_counter.in = %next_output.out : i64
        calyx.assign %output_counter.write_en = %true : i1
        calyx.assign %k_counter.in = %zero_i64 : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.group_done %output_counter.done : i1
      }
    }
    calyx.control {
      calyx.while %output_less.out with @output_not_done {
        calyx.seq {
          calyx.while %k_less.out with @k_not_done {
            calyx.enable @mac_step
          }
          calyx.enable @advance_output
        }
      }
    }
  }
}
