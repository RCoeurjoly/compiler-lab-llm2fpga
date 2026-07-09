module attributes {calyx.entrypoint = "main"} {
  calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %reg.in, %reg.write_en, %reg.clk, %reg.reset, %reg.out, %reg.done = calyx.register @reg : i8, i1, i1, i1, i8, i1
    %inner_instance.clk, %inner_instance.reset, %inner_instance.go, %inner_instance.done = calyx.instance @inner_instance of @inner : i1, i1, i1, i1
    calyx.wires {
    }
    calyx.control {
      calyx.invoke @inner_instance[arg_reg = reg]() -> ()
    }
  } {toplevel}
  calyx.component @inner(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %true = hw.constant true
    %arg_reg.in, %arg_reg.write_en, %arg_reg.clk, %arg_reg.reset, %arg_reg.out, %arg_reg.done = calyx.register @arg_reg : i8, i1, i1, i1, i8, i1
    calyx.wires {
      calyx.group @write_reg {
        calyx.assign %arg_reg.in = %arg_reg.out : i8
        calyx.assign %arg_reg.write_en = %true : i1
        calyx.group_done %arg_reg.done : i1
      }
    }
    calyx.control {
      calyx.enable @write_reg
    }
  }
}
