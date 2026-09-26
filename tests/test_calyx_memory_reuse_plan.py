import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/pipeline/plan_calyx_memory_reuse.py"
spec = importlib.util.spec_from_file_location("memory_reuse_plan", SOURCE)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_plan_is_analysis_only_and_finds_disjoint_same_shape_memories():
    futil = """
@external first = seq_mem_d1(64, 8, 3);
@external second = seq_mem_d1(64, 8, 3);
@external overlap = seq_mem_d1(64, 8, 3);
component main() -> () {
  first = seq_mem_d1(64, 8, 3);
  second = seq_mem_d1(64, 8, 3);
  overlap = seq_mem_d1(64, 8, 3);
  group produce { first.addr0 = 3'd0; first.write_en = 1'd1; }
  group consume { first.addr0 = 3'd0; second.addr0 = 3'd0; }
  group overwrite { second.addr0 = 3'd0; overlap.addr0 = 3'd0; }
  control {
    seq { produce; consume; overwrite; }
  }
}
"""
    result = module.plan(futil)
    assert result["policy"].startswith("analysis-only")
    pairs = {(entry["first"], entry["second"]) for entry in result["same_shape_disjoint_candidates"]}
    assert ("first", "second") not in pairs
    assert ("first", "overlap") in pairs


def test_apply_aliases_removes_only_the_validated_memory_declaration():
    futil = """@external scratch_a = seq_mem_d1(64, 8, 3);
@external scratch_b = seq_mem_d1(64, 8, 3);
component main() -> () {
  cells { scratch_a = seq_mem_d1(64, 8, 3); scratch_b = seq_mem_d1(64, 8, 3); }
  control { empty }
}
"""
    result = module.apply_aliases(futil, {"scratch_b": "scratch_a"})
    assert "scratch_b" not in result
    assert result.count("@external scratch_a") == 1


def test_apply_aliases_accepts_generated_external_attributes():
    futil = """@external(1) scratch_a = seq_mem_d1(64, 8, 3);
@external(1) scratch_b = seq_mem_d1(64, 8, 3);
component main() -> () {
  cells { scratch_a = seq_mem_d1(64, 8, 3); scratch_b = seq_mem_d1(64, 8, 3); }
  control { empty }
}
"""
    result = module.apply_aliases(futil, {"scratch_b": "scratch_a"})
    assert "@external(1) scratch_b" not in result
    assert result.count("@external(1) scratch_a") == 1


def test_conservative_aliases_protect_model_memories_and_do_not_chain():
    futil = """@external weights = seq_mem_d1(8, 8, 3);
@external a = seq_mem_d1(64, 8, 3);
@external b = seq_mem_d1(64, 8, 3);
component main() -> () {
  cells { weights = seq_mem_d1(8, 8, 3); a = seq_mem_d1(64, 8, 3); b = seq_mem_d1(64, 8, 3); }
  group write_a { a.addr0 = 3'd0; a.write_en = 1'd1; }
  group write_b { b.addr0 = 3'd0; b.write_en = 1'd1; }
  control { seq { write_a; write_b; } }
}
"""
    aliases = module.conservative_scratch_aliases(futil, {"weights"})
    assert aliases == {"b": "a"}


def test_plan_finds_groups_declared_in_wires_before_nested_component_control():
    futil = """
@external mem_0 = seq_mem_d1(64, 8, 3);
component main() -> () {
  cells { child = child(); }
  control { invoke child(); }
}
component child() -> () {
  cells {
    @external first = seq_mem_d1(64, 8, 3);
    @external second = seq_mem_d1(64, 8, 3);
  }
  wires {
    group produce { first.addr0 = 3'd0; first.write_en = 1'd1; }
    group consume { first.addr0 = 3'd0; second.addr0 = 3'd0; }
    group overwrite { second.addr0 = 3'd0; }
  }
  control {
    seq { produce; consume; overwrite; }
  }
}
"""
    result = module.plan(futil)
    assert result["control_group_tokens"] == 3
    pairs = {(entry["first"], entry["second"]) for entry in result["same_shape_disjoint_candidates"]}
    assert ("first", "second") not in pairs


def test_plan_resolves_generated_component_memory_arguments():
    futil = """
@external mem_0 = seq_mem_d1(64, 8, 3);
component main() -> () {
  control { invoke child[arg_mem_0 = mem_0](); }
}
component child() -> () {
  cells { ref arg_mem_0 = seq_mem_d1(64, 8, 3); }
  wires { group use_mem { arg_mem_0.addr0 = 3'd0; } }
  control { seq { use_mem; } }
}
"""
    result = module.plan(futil)
    assert result["intervals"] == {"mem_0": {"first": 0, "last": 0}}
