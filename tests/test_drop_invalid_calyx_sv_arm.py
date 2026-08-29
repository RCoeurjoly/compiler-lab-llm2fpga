from pathlib import Path
import importlib.util
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/drop_invalid_calyx_sv_arm.py"


def _module():
    spec = importlib.util.spec_from_file_location("drop_invalid_calyx_sv_arm", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_drops_one_complete_or_term_from_first_mux_arm_only():
    module = _module()
    source = "assign std_add_251_right = bb0_191_go_out | bb0_1066_go_out ? std_signext_63_out : 64'd1;\n"

    rewritten, receipt = module.drop_or_guard_term(
        source, "std_add_251_right", "bb0_191_go_out"
    )

    assert rewritten == (
        "assign std_add_251_right = bb0_1066_go_out ? std_signext_63_out : 64'd1;\n"
    )
    assert receipt == {
        "assignment": "std_add_251_right",
        "guard": "bb0_191_go_out",
        "removed_arms": 1,
    }


def test_rejects_a_guard_that_is_not_an_entire_or_term():
    module = _module()
    source = "assign std_add_251_right = bb0_191_go_out & select ? std_signext_63_out : 64'd1;\n"

    try:
        module.drop_or_guard_term(source, "std_add_251_right", "bb0_191_go_out")
    except ValueError as error:
        assert "complete OR term" in str(error)
    else:
        raise AssertionError("partial guard was unexpectedly rewritten")
