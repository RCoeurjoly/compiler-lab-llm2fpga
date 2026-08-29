from pathlib import Path
import importlib.util

SCRIPT = Path(__file__).parents[1] / "scripts/comparison/clone_calyx_comb_cell.py"
spec = importlib.util.spec_from_file_location("clone", SCRIPT)
clone = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(clone)


def test_clone_preserves_original_and_rebinds_exact_destination():
    text = """component main() -> () {
  cells {
    x = std_signext(32, 64);
  }
  wires { group g { y.right = x.out; } }
}
"""
    out, name = clone.clone(text, "x", "y.right")
    assert name == "x__for__y_right"
    assert "x__for__y_right = std_signext(32, 64);" in out
    assert "y.right = x__for__y_right.out;" in out


def test_clone_fails_closed_for_non_combinational_or_ambiguous_source():
    text = "component main() -> () { cells { x = std_reg(32); } }\n"
    try:
        clone.clone(text, "x", "y.right")
    except ValueError:
        return
    raise AssertionError("non-combinational cell was accepted")
