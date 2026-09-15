import hashlib
from pathlib import Path

from scripts.analysis.memory_placement_contract import placement_record, placement_manifest_hash
from scripts.analysis.memory_placement_equivalence import ProjectionTable


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "result-compiler-top-30mhz-20260908/image-q_weight_codes_i8.hex"


def projection_table():
    raw = bytes(int(line.strip(), 16) for line in IMAGE.read_text().splitlines())[:4096]
    return ProjectionTable("blocks.0.attn.q.weight", 8, len(raw), raw,
                           hashlib.sha256(IMAGE.read_bytes()).hexdigest(), str(IMAGE))


def test_modes_share_shape_and_provenance_but_have_explicit_latency():
    table = projection_table()
    bram = placement_record(table, "bram")
    ddr3 = placement_record(table, "ddr3")
    assert bram["space"] == "bram"
    assert ddr3["space"] == "ddr3"
    assert bram["width_bits"] == ddr3["width_bits"] == 8
    assert bram["depth_words"] == ddr3["depth_words"] == 4096
    assert bram["source_sha256"] == ddr3["source_sha256"] == table.source_sha256
    assert bram["read_latency"] == 1
    assert ddr3["read_latency"] == "variable_bounded"
    assert ddr3["burst_words"] == 16
    assert ddr3["alignment_bytes"] == 16


def test_manifest_hash_is_canonical_and_mode_sensitive():
    table = projection_table()
    left = placement_manifest_hash([placement_record(table, "bram")])
    right = placement_manifest_hash([placement_record(table, "ddr3")])
    assert left != right
    assert left == placement_manifest_hash([placement_record(table, "bram")])
