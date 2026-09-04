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
  // generated_from_descriptor runtime rows=1 outputs=64 inputs=64 mac_order=ascending_i64_wrap
  calyx.component @llm2fpga_serial_gemv_64_64(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %activation.addr0, %activation.clk, %activation.reset, %activation.content_en, %activation.write_en, %activation.write_data, %activation.read_data, %activation.done = calyx.seq_mem @activation <[64] x 64> [6] : i6, i1, i1, i1, i1, i64, i64, i1
    %weights.addr0, %weights.clk, %weights.reset, %weights.content_en, %weights.write_en, %weights.write_data, %weights.read_data, %weights.done = calyx.seq_mem @weights <[4096] x 64> [12] : i12, i1, i1, i1, i1, i64, i64, i1
    %results.addr0, %results.clk, %results.reset, %results.content_en, %results.write_en, %results.write_data, %results.read_data, %results.done = calyx.seq_mem @results <[64] x 64> [6] : i6, i1, i1, i1, i1, i64, i64, i1
    %true = hw.constant true
    %false = hw.constant false
    %zero_i64 = hw.constant 0 : i64
    %one_i64 = hw.constant 1 : i64
    %row_limit_i64 = hw.constant 1 : i64
    %output_limit_i64 = hw.constant 64 : i64
    %input_limit_i64 = hw.constant 64 : i64
    %row_counter.in, %row_counter.write_en, %row_counter.clk, %row_counter.reset, %row_counter.out, %row_counter.done = calyx.register @row_counter : i64, i1, i1, i1, i64, i1
    %output_counter.in, %output_counter.write_en, %output_counter.clk, %output_counter.reset, %output_counter.out, %output_counter.done = calyx.register @output_counter : i64, i1, i1, i1, i64, i1
    %k_counter.in, %k_counter.write_en, %k_counter.clk, %k_counter.reset, %k_counter.out, %k_counter.done = calyx.register @k_counter : i64, i1, i1, i1, i64, i1
    %accumulator.in, %accumulator.write_en, %accumulator.clk, %accumulator.reset, %accumulator.out, %accumulator.done = calyx.register @accumulator : i64, i1, i1, i1, i64, i1
    %activation_base.in, %activation_base.write_en, %activation_base.clk, %activation_base.reset, %activation_base.out, %activation_base.done = calyx.register @activation_base : i64, i1, i1, i1, i64, i1
    %activation_address.in, %activation_address.write_en, %activation_address.clk, %activation_address.reset, %activation_address.out, %activation_address.done = calyx.register @activation_address : i64, i1, i1, i1, i64, i1
    %weight_address.in, %weight_address.write_en, %weight_address.clk, %weight_address.reset, %weight_address.out, %weight_address.done = calyx.register @weight_address : i64, i1, i1, i1, i64, i1
    %result_address.in, %result_address.write_en, %result_address.clk, %result_address.reset, %result_address.out, %result_address.done = calyx.register @result_address : i64, i1, i1, i1, i64, i1
    %activation_address_slice.in, %activation_address_slice.out = calyx.std_slice @activation_address_slice : i64, i6
    %weight_address_slice.in, %weight_address_slice.out = calyx.std_slice @weight_address_slice : i64, i12
    %result_address_slice.in, %result_address_slice.out = calyx.std_slice @result_address_slice : i64, i6
    %operands_done.left, %operands_done.right, %operands_done.out = calyx.std_and @operands_done : i1, i1, i1
    %mac_mul.clk, %mac_mul.reset, %mac_mul.go, %mac_mul.left, %mac_mul.right, %mac_mul.out, %mac_mul.done = calyx.std_mult_pipe @mac_mul : i1, i1, i1, i64, i64, i64, i1
    %mac_add.left, %mac_add.right, %mac_add.out = calyx.std_add @mac_add : i64, i64, i64
    %next_row.left, %next_row.right, %next_row.out = calyx.std_add @next_row : i64, i64, i64
    %next_output.left, %next_output.right, %next_output.out = calyx.std_add @next_output : i64, i64, i64
    %next_k.left, %next_k.right, %next_k.out = calyx.std_add @next_k : i64, i64, i64
    %next_activation_base.left, %next_activation_base.right, %next_activation_base.out = calyx.std_add @next_activation_base : i64, i64, i64
    %next_activation_address.left, %next_activation_address.right, %next_activation_address.out = calyx.std_add @next_activation_address : i64, i64, i64
    %next_weight_address.left, %next_weight_address.right, %next_weight_address.out = calyx.std_add @next_weight_address : i64, i64, i64
    %next_result_address.left, %next_result_address.right, %next_result_address.out = calyx.std_add @next_result_address : i64, i64, i64
    %row_less.left, %row_less.right, %row_less.out = calyx.std_lt @row_less : i64, i64, i1
    %output_less.left, %output_less.right, %output_less.out = calyx.std_lt @output_less : i64, i64, i1
    %k_less.left, %k_less.right, %k_less.out = calyx.std_lt @k_less : i64, i64, i1
    calyx.wires {
      calyx.comb_group @row_not_done {
        calyx.assign %row_less.left = %row_counter.out : i64
        calyx.assign %row_less.right = %row_limit_i64 : i64
      }
      calyx.comb_group @output_not_done {
        calyx.assign %output_less.left = %output_counter.out : i64
        calyx.assign %output_less.right = %output_limit_i64 : i64
      }
      calyx.comb_group @k_not_done {
        calyx.assign %k_less.left = %k_counter.out : i64
        calyx.assign %k_less.right = %input_limit_i64 : i64
      }
      calyx.group @read_operands {
        calyx.assign %activation_address_slice.in = %activation_address.out : i64
        calyx.assign %weight_address_slice.in = %weight_address.out : i64
        calyx.assign %activation.addr0 = %activation_address_slice.out : i6
        calyx.assign %weights.addr0 = %weight_address_slice.out : i12
        calyx.assign %activation.content_en = %true : i1
        calyx.assign %activation.write_en = %false : i1
        calyx.assign %weights.content_en = %true : i1
        calyx.assign %weights.write_en = %false : i1
        calyx.assign %operands_done.left = %activation.done : i1
        calyx.assign %operands_done.right = %weights.done : i1
        calyx.group_done %operands_done.out : i1
      }
      calyx.group @launch_multiply {
        calyx.assign %mac_mul.left = %activation.read_data : i64
        calyx.assign %mac_mul.right = %weights.read_data : i64
        calyx.assign %mac_mul.go = %true : i1
        calyx.group_done %mac_mul.done : i1
      }
      calyx.group @accumulate_and_advance_k {
        calyx.assign %mac_add.left = %accumulator.out : i64
        calyx.assign %mac_add.right = %mac_mul.out : i64
        calyx.assign %accumulator.in = %mac_add.out : i64
        calyx.assign %accumulator.write_en = %true : i1
        calyx.assign %next_k.left = %k_counter.out : i64
        calyx.assign %next_k.right = %one_i64 : i64
        calyx.assign %k_counter.in = %next_k.out : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.assign %next_activation_address.left = %activation_address.out : i64
        calyx.assign %next_activation_address.right = %one_i64 : i64
        calyx.assign %activation_address.in = %next_activation_address.out : i64
        calyx.assign %activation_address.write_en = %true : i1
        calyx.assign %next_weight_address.left = %weight_address.out : i64
        calyx.assign %next_weight_address.right = %one_i64 : i64
        calyx.assign %weight_address.in = %next_weight_address.out : i64
        calyx.assign %weight_address.write_en = %true : i1
        calyx.group_done %accumulator.done : i1
      }
      calyx.group @write_result {
        calyx.assign %result_address_slice.in = %result_address.out : i64
        calyx.assign %results.addr0 = %result_address_slice.out : i6
        calyx.assign %results.write_data = %accumulator.out : i64
        calyx.assign %results.content_en = %true : i1
        calyx.assign %results.write_en = %true : i1
        calyx.group_done %results.done : i1
      }
      calyx.group @advance_output {
        calyx.assign %next_output.left = %output_counter.out : i64
        calyx.assign %next_output.right = %one_i64 : i64
        calyx.assign %output_counter.in = %next_output.out : i64
        calyx.assign %output_counter.write_en = %true : i1
        calyx.assign %k_counter.in = %zero_i64 : i64
        calyx.assign %k_counter.write_en = %true : i1
        calyx.assign %accumulator.in = %zero_i64 : i64
        calyx.assign %accumulator.write_en = %true : i1
        calyx.assign %activation_address.in = %activation_base.out : i64
        calyx.assign %activation_address.write_en = %true : i1
        calyx.assign %next_result_address.left = %result_address.out : i64
        calyx.assign %next_result_address.right = %one_i64 : i64
        calyx.assign %result_address.in = %next_result_address.out : i64
        calyx.assign %result_address.write_en = %true : i1
        calyx.group_done %output_counter.done : i1
      }
      calyx.group @advance_row {
        calyx.assign %next_row.left = %row_counter.out : i64
        calyx.assign %next_row.right = %one_i64 : i64
        calyx.assign %row_counter.in = %next_row.out : i64
        calyx.assign %row_counter.write_en = %true : i1
        calyx.assign %output_counter.in = %zero_i64 : i64
        calyx.assign %output_counter.write_en = %true : i1
        calyx.assign %weight_address.in = %zero_i64 : i64
        calyx.assign %weight_address.write_en = %true : i1
        calyx.assign %next_activation_base.left = %activation_base.out : i64
        calyx.assign %next_activation_base.right = %input_limit_i64 : i64
        calyx.assign %activation_base.in = %next_activation_base.out : i64
        calyx.assign %activation_base.write_en = %true : i1
        calyx.assign %activation_address.in = %next_activation_base.out : i64
        calyx.assign %activation_address.write_en = %true : i1
        calyx.group_done %row_counter.done : i1
      }
    }
    calyx.control {
      calyx.while %row_less.out with @row_not_done {
        calyx.seq {
          calyx.while %output_less.out with @output_not_done {
            calyx.seq {
              calyx.while %k_less.out with @k_not_done {
                calyx.seq {
                  calyx.enable @read_operands
                  calyx.enable @launch_multiply
                  calyx.enable @accumulate_and_advance_k
                }
              }
              calyx.enable @write_result
              calyx.enable @advance_output
            }
          }
          calyx.enable @advance_row
        }
      }
    }
  }
}
