// This component deliberately has no behavior beyond declaring f32 constants.
// The exporter must preserve each IEEE-754 storage word in its Calyx cells.
module attributes {calyx.entrypoint = "main"} {
  calyx.component @main(%clk: i1 {clk}, %reset: i1 {reset}, %go: i1 {go}) -> (%done: i1 {done}) {
    %tiny = calyx.constant @tiny <7.54663105e-08 : f32> : i32
    %neg_zero = calyx.constant @neg_zero <0x80000000 : f32> : i32
    %pos_inf = calyx.constant @pos_inf <0x7F800000 : f32> : i32
    %nan = calyx.constant @nan <0x7FC00001 : f32> : i32
    %four_point_two = calyx.constant @four_point_two <4.200000e+00 : f32> : i32
    calyx.wires {
      calyx.assign %done = %go : i1
    }
    calyx.control {}
  } {toplevel}
}
