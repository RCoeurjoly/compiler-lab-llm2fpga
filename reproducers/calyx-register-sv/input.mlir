module attributes {calyx.entrypoint = "main"} {
  calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %true = hw.constant true
    %reg.in, %reg.write_en, %reg.clk, %reg.reset, %reg.out, %reg.done = calyx.register @reg : i8, i1, i1, i1, i8, i1
    calyx.wires {
      calyx.group @write_reg {
        calyx.assign %reg.in = %reg.out : i8
        calyx.assign %reg.write_en = %true : i1
        calyx.group_done %reg.done : i1
      }
    }
    calyx.control {
      calyx.enable @write_reg
    }
  } {toplevel}
}
