module attributes {calyx.entrypoint = "main"} {
  calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %mem_0.addr0, %mem_0.clk, %mem_0.reset, %mem_0.content_en, %mem_0.write_en, %mem_0.write_data, %mem_0.read_data, %mem_0.done = calyx.seq_mem @mem_0 <[4] x 32> [2] {external = true} : i2, i1, i1, i1, i1, i32, i32, i1
    %kernel_instance.clk, %kernel_instance.reset, %kernel_instance.go, %kernel_instance.out0, %kernel_instance.done = calyx.instance @kernel_instance of @kernel : i1, i1, i1, i32, i1
    calyx.wires {
    }
    calyx.control {
      calyx.seq {
        calyx.seq {
          calyx.invoke @kernel_instance[arg_mem_0 = mem_0]() -> ()
        }
      }
    }
  } {toplevel}
  calyx.component @kernel(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%out0: i32, %done: i1 {done}) {
    %false = hw.constant false
    %true = hw.constant true
    %c0_i32 = hw.constant 0 : i32
    %std_slice_0.in, %std_slice_0.out = calyx.std_slice @std_slice_0 : i32, i2
    %ret_arg0_reg.in, %ret_arg0_reg.write_en, %ret_arg0_reg.clk, %ret_arg0_reg.reset, %ret_arg0_reg.out, %ret_arg0_reg.done = calyx.register @ret_arg0_reg : i32, i1, i1, i1, i32, i1
    %arg_mem_0.addr0, %arg_mem_0.clk, %arg_mem_0.reset, %arg_mem_0.content_en, %arg_mem_0.write_en, %arg_mem_0.write_data, %arg_mem_0.read_data, %arg_mem_0.done = calyx.seq_mem @arg_mem_0 <[4] x 32> [2] : i2, i1, i1, i1, i1, i32, i32, i1
    calyx.wires {
      calyx.assign %out0 = %ret_arg0_reg.out : i32
      calyx.group @bb0_0 {
        calyx.assign %std_slice_0.in = %c0_i32 : i32
        calyx.assign %arg_mem_0.addr0 = %std_slice_0.out : i2
        calyx.assign %arg_mem_0.content_en = %true : i1
        calyx.assign %arg_mem_0.write_en = %false : i1
        calyx.group_done %arg_mem_0.done : i1
      }
      calyx.group @ret_assign_0 {
        calyx.assign %ret_arg0_reg.in = %arg_mem_0.read_data : i32
        calyx.assign %ret_arg0_reg.write_en = %true : i1
        calyx.group_done %ret_arg0_reg.done : i1
      }
    }
    calyx.control {
      calyx.seq {
        calyx.seq {
          calyx.enable @bb0_0
          calyx.enable @ret_assign_0
        }
      }
    }
  }
}

