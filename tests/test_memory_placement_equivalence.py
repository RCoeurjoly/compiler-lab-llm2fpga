import hashlib
import json
from pathlib import Path

from scripts.analysis.memory_placement_equivalence import (
    BramBackend,
    Ddr3PrefetchBackend,
    ProjectionTable,
    run_equivalence,
)


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "result-compiler-top-30mhz-20260908/image-q_weight_codes_i8.hex"


def table() -> ProjectionTable:
    # One authenticated compiler projection table: block 0 q, 64x64 INT8.
    raw = bytes(int(line.strip(), 16) for line in IMAGE.read_text().splitlines())
    return ProjectionTable(
        logical_name="blocks.0.attn.q.weight",
        width_bits=8,
        depth_words=64 * 64,
        data=raw[: 64 * 64],
        source_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),
        source_path=str(IMAGE),
    )


def test_bram_and_ddr3_preserve_ordered_reads_and_gemv_result():
    t = table()
    # Includes row starts, 16-byte DDR boundaries, and repeated addresses.
    addresses = [0, 1, 15, 16, 63, 64, 127, 255, 1023, 2048, 4095, 0, 64, 4095]
    result = run_equivalence(t, addresses, input_codes=[-3, 7, 11, -5] * 16)
    assert result["status"] == "pass"
    assert result["bram"]["response_sha256"] == result["ddr3"]["response_sha256"]
    assert result["bram"]["output_sha256"] == result["ddr3"]["output_sha256"]
    assert result["first_mismatch"] is None
    assert result["contract"]["logical_name"] == t.logical_name
    assert result["contract"]["source_sha256"] == t.source_sha256


def test_ddr3_prefetch_has_explicit_variable_latency_but_same_data():
    t = table()
    backend = Ddr3PrefetchBackend(t, line_bytes=16, prefetch_lines=8)
    responses = backend.read_trace([0, 1, 15, 16, 17])
    assert [item["data"] for item in responses] == list(t.data[:2]) + [t.data[15], t.data[16], t.data[17]]
    assert len({item["cycle"] for item in responses}) > 1
    assert backend.stats["external_requests"] == 1
