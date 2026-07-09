module attributes {calyx.entrypoint = "main"} {
  calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %mem.addr0, %mem.clk, %mem.reset, %mem.content_en, %mem.write_en, %mem.write_data, %mem.read_data, %mem.done = calyx.seq_mem @mem <[4] x 8> [2] {external = true} : i2, i1, i1, i1, i1, i8, i8, i1
    %inner_instance.clk, %inner_instance.reset, %inner_instance.go, %inner_instance.done = calyx.instance @inner_instance of @inner : i1, i1, i1, i1
    calyx.wires {
    }
    calyx.control {
      calyx.invoke @inner_instance[arg_mem = mem]() -> ()
    }
  } {toplevel}
  calyx.component @inner(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %true = hw.constant true
    %c0_i2 = hw.constant 0 : i2
    %arg_mem.addr0, %arg_mem.clk, %arg_mem.reset, %arg_mem.content_en, %arg_mem.write_en, %arg_mem.write_data, %arg_mem.read_data, %arg_mem.done = calyx.seq_mem @arg_mem <[4] x 8> [2] : i2, i1, i1, i1, i1, i8, i8, i1
    calyx.wires {
      calyx.group @read_mem {
        calyx.assign %arg_mem.addr0 = %c0_i2 : i2
        calyx.assign %arg_mem.content_en = %true : i1
        calyx.group_done %arg_mem.done : i1
      }
    }
    calyx.control {
      calyx.enable @read_mem
    }
  }
}
