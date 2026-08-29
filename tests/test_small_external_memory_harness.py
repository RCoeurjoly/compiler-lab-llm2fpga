from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "reproducers/calyx-layernorm-memory-harness/input.futil"
PROBE = ROOT / "scripts/comparison/probe_small_external_memory.cpp"
ARTIFACT = ROOT / "artifacts/comparison/tinystories-1m-small-memory-harness.json"
MAIN1_TB = ROOT / "reproducers/calyx-layernorm-memory-harness/main1_external_tb.sv"
MAIN1_ARTIFACT = ROOT / "artifacts/comparison/tinystories-1m-layernorm-main1-iverilog-diagnostic.json"
STRUCTURAL_ARTIFACT = ROOT / "artifacts/comparison/tinystories-1m-layernorm-structural-proxy.json"


def test_fixture_exposes_four_small_external_memories_and_two_phase_schedule():
    text = FIXTURE.read_text(encoding="utf-8")
    assert text.count("@external") == 4
    assert text.count("seq_mem_d1(32, 4, 2)") == 4
    assert "control { seq { read0; word0; read1; word1; read2; word2; read3; word3; } }" in text
    assert text.count("[done] = (in_mem.done & gamma.done & beta.done)") == 4


def test_probe_is_diagnostic_and_checks_completion_and_outputs():
    text = PROBE.read_text(encoding="utf-8")
    assert "not a TinyStories or LayerNorm" in text
    assert "model.done" in text
    assert "main__DOT__in_mem__DOT__mem" in text
    assert "main__DOT__out_mem__DOT__mem" in text
    assert '\\"status\\"' in text


def test_evidence_artifact_binds_sources_and_fail_closed_scope():
    report = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert report["result"] == {"status": "ok", "done": True, "cycles": 16}
    assert report["scope"]["claims_layernorm_equivalence"] is False
    assert report["scope"]["claims_tinystories_equivalence"] is False
    assert report["fixture"]["sha256"] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert report["probe"]["sha256"] == hashlib.sha256(PROBE.read_bytes()).hexdigest()


def test_main1_diagnostic_binds_authenticated_vector_and_exact_output():
    report = json.loads(MAIN1_ARTIFACT.read_text(encoding="utf-8"))
    assert report["reference_vector"]["sha256"] == "1b84d6194874f1f9e6074a99f06527aa01e633ecc6daf92340136a86806d6304"
    assert report["reference_vector"]["input_matches_testbench"] is True
    assert report["reference_vector"]["expected_output_matches_testbench"] is True
    assert report["result"]["output_mismatches"] == 0
    assert report["result"]["output_writes"] == 64
    assert report["testbench"]["sha256"] == hashlib.sha256(MAIN1_TB.read_bytes()).hexdigest()


def test_structural_proxy_is_explicitly_not_synthesis_evidence():
    report = json.loads(STRUCTURAL_ARTIFACT.read_text(encoding="utf-8"))
    assert report["source"]["main1_lines"] == 169843
    assert report["total_instances"] == 2165
    assert report["primitive_instance_counts"]["std_sdiv_pipe"] == 65
    assert report["scope"]["post_synthesis_resources"] is False
    assert report["scope"]["timing_closure"] is False
