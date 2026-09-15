import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ddr3_feasibility", ROOT / "scripts/analysis/tinystories_ddr3_feasibility.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_one_step_trace_has_exact_compiler_weight_count():
    result = MODULE.analyze(1)
    # 8 layers * (4*64*64 + 2*64*256) byte reads, plus packed LM head.
    expected_block = 4 * 8 * (4 * 64 * 64 + 2 * 64 * 256)
    expected_lm_reads = 50257 * 16
    expected_lm_bytes = expected_lm_reads * 4
    assert result["statistics"]["reads_total"] == expected_block + expected_lm_reads
    assert result["statistics"]["payload_bytes_total"] == expected_block + expected_lm_bytes


def test_sixteen_step_context_rows_are_real_schedule_rows():
    result = MODULE.analyze(16)
    rows = [entry["context_rows"] for entry in result["statistics"]["steps"]]
    assert rows == list(range(4, 20))
    assert all(entry["reads"] > 0 for entry in result["statistics"]["steps"])


def test_trace_is_deterministic_and_lm_head_is_packed():
    first = MODULE.analyze(2)
    second = MODULE.analyze(2)
    assert first["trace_sha256"] == second["trace_sha256"]
    assert first["statistics"]["steps"][0]["bursts_if_sequential"] > 0
    lm_reads = [x for x in MODULE.iter_weight_reads(1) if x["table"] == "lm_head_packed"]
    assert len(lm_reads) == 50257 * 16
    assert {x["word_bytes"] for x in lm_reads} == {4}
