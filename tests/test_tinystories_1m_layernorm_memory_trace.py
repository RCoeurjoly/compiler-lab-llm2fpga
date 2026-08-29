from pathlib import Path
import importlib.util
import json
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/comparison/verify_tinystories_1m_layernorm_memory_trace.py"
RECEIPT = ROOT / "artifacts/comparison/tinystories-1m-layernorm-memory-trace-verification.json"
YOSYS_RECEIPT = ROOT / "artifacts/comparison/tinystories-1m-layernorm-yosys-stat.json"
YOSYS_CHECK = ROOT / "artifacts/comparison/tinystories-1m-layernorm-yosys-check.json"
BACKEND_VARIANT = ROOT / "artifacts/comparison/tinystories-1m-layernorm-calyx-backend-variant.json"


def _module():
    spec = importlib.util.spec_from_file_location("trace_verify", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_checked_in_receipt_is_accepted_and_binds_reference_vector():
    report = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert report["status"] == "accepted"
    assert report["transactions"] == 256
    assert report["output_matches_reference"] is True
    assert report["vector_sha256"] == "1b84d6194874f1f9e6074a99f06527aa01e633ecc6daf92340136a86806d6304"


def test_verifier_rejects_wrong_transaction_count():
    module = _module()
    with tempfile.TemporaryDirectory() as directory:
        trace = Path(directory) / "trace.csv"
        trace.write_text("0,0,0,0,xxxxxxxx\n", encoding="utf-8")
        try:
            module.verify(trace, ROOT / "artifacts/reference/tinystories-1m-rtl-layernorm-vector.json")
        except ValueError as error:
            assert "256" in str(error)
        else:
            raise AssertionError("malformed trace was accepted")


def test_yosys_statistics_are_scoped_as_pre_synthesis_data():
    report = json.loads(YOSYS_RECEIPT.read_text(encoding="utf-8"))
    assert report["top"] == "main_1"
    assert report["statistics"]["cells"] == 81456
    assert report["statistics"]["signed_divider_submodules"] == 65
    assert report["scope"]["post_synthesis_resource_count"] is False
    assert report["scope"]["timing_closure"] is False


def test_pretechmap_check_records_undriven_outputs_without_claiming_a_loop():
    report = json.loads(YOSYS_CHECK.read_text(encoding="utf-8"))
    assert report["status"] == "failed_structural_check"
    assert report["problems"] == 96
    assert report["findings"]["undriven_external_memory_write_data_bits"] is True
    assert report["findings"]["undriven_ports"] == [
        "arg_mem_0_write_data[31:0]",
        "arg_mem_1_write_data[31:0]",
        "arg_mem_2_write_data[31:0]",
    ]
    assert report["findings"]["combinational_loop_reported"] is False
    assert report["scope"]["timing_closure"] is False


def test_backend_variant_binds_exact_probe_and_fair_structural_counts():
    report = json.loads(BACKEND_VARIANT.read_text(encoding="utf-8"))
    assert report["variant"]["yosys_techmap_status"] == "completed_but_structural_check_failed"
    assert report["variant"]["yosys_post_techmap_check_problems"] == 128
    assert report["functional_probe"]["output_mismatches"] == 0
    assert report["fair_structural_comparison"]["variant_yosys_proc_opt_cells"] == 7654
    assert report["baseline"]["yosys_proc_opt_cells"] == 7654
    assert report["scope"]["full_transformer_equivalence"] is False
