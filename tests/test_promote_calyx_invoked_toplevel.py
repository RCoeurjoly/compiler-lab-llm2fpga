from scripts.pipeline.promote_calyx_invoked_toplevel import promote


def test_promotes_single_invoked_component():
    source = '''import "primitives/core.futil";
component main<"toplevel"=1,>(@clk clk: 1) -> (@done done: 1) {
  cells { @external(1) mem = seq_mem_d1(8, 4, 2); }
  wires { }
  control { seq { invoke main_1_instance[arg_mem_0 = mem] ()(); } }
}
component main_1(@clk clk: 1) -> (@done done: 1) {
  cells { ref arg_mem_0 = seq_mem_d1(8, 4, 2); }
  wires { }
  control { empty }
}
'''
    promoted = promote(source)
    assert promoted.count("component ") == 1
    assert 'component main_1<"toplevel"=1,>' in promoted
    assert "invoke main_1_instance" not in promoted


def test_rejects_non_wrapper_main():
    source = 'component main<"toplevel"=1,>(@clk clk: 1) -> (@done done: 1) { cells { } wires { } control { empty } }\n'
    source += 'component main_1(@clk clk: 1) -> (@done done: 1) { cells { } wires { } control { empty } }\n'
    try:
        promote(source)
    except ValueError as error:
        assert "single invoke" in str(error)
    else:
        raise AssertionError("non-wrapper main must be rejected")
