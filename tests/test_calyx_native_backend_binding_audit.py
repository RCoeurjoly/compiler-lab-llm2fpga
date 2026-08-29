"""Focused guard against native-Calyx cross-cell input rebinding.

The LayerNorm source program assigns ``std_signext_63.out`` only to
``std_add_62.right``.  A generated-Verilog assignment to a different add-cell
input is therefore a backend boundary defect, not a CIRCT scheduling loop that
an upstream pass can safely fix.
"""

from pathlib import Path
import importlib.util
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/audit_calyx_native_backend_bindings.py"


def _module():
    spec = importlib.util.spec_from_file_location("calyx_binding_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_audit_rejects_generated_input_sourced_from_unrelated_futil_cell():
    module = _module()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        futil = root / "model.futil"
        sv = root / "main.sv"
        futil.write_text(
            """component main() -> () {\n"
            "  cells { std_add_62 = std_add(64); std_add_251 = std_add(64); std_signext_63 = std_signext(32, 64); }\n"
            "  wires { group g { std_add_62.right = std_signext_63.out; std_add_251.right = 64'd1; g[done] = 1'd1; } }\n"
            "  control { enable g; }\n"
            "}\n""",
            encoding="utf-8",
        )
        sv.write_text(
            """module main;\n"
            "wire [63:0] std_signext_63_out;\n"
            "wire [63:0] std_add_251_right;\n"
            "assign std_add_251_right = guard ? std_signext_63_out : 64'd1;\n"
            "endmodule\n""",
            encoding="utf-8",
        )
        report = module.audit(futil, sv, ["std_add_251_right"])

    assert report["status"] == "backend_binding_mismatch"
    assert report["mismatches"] == [
        {
            "generated_input": "std_add_251_right",
            "generated_sources": ["std_signext_63_out"],
            "source_cell": "std_signext_63",
            "futil_destinations": ["std_add_62.right"],
        }
    ]


def test_audit_accepts_a_generated_input_with_matching_futil_source_cell():
    module = _module()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        futil = root / "model.futil"
        sv = root / "main.sv"
        futil.write_text(
            "component main() -> () { wires { group g { std_add_251.right = std_signext_63.out; } } }\n",
            encoding="utf-8",
        )
        sv.write_text(
            "assign std_add_251_right = guard ? std_signext_63_out : 64'd1;\n",
            encoding="utf-8",
        )
        report = module.audit(futil, sv, ["std_add_251_right"])

    assert report["status"] == "accepted"
    assert report["mismatches"] == []
