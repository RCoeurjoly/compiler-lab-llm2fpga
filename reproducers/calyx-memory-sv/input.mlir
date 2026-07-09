module attributes {calyx.entrypoint = "main"} {
  calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %mem.addr0, %mem.write_data, %mem.write_en, %mem.clk, %mem.read_data, %mem.done = calyx.memory @mem <[4] x 8> [2] {external = true} : i2, i8, i1, i1, i8, i1
    calyx.wires {
      calyx.group @done_group {
        calyx.group_done %mem.done : i1
      }
    }
    calyx.control {
      calyx.enable @done_group
    }
  } {toplevel}
}
