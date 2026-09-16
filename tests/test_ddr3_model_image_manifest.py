from pathlib import Path

from scripts.analysis.build_ddr3_model_image_manifest import build


def test_manifest_is_canonical_and_16_byte_aligned(tmp_path: Path) -> None:
    (tmp_path / "image-z.hex").write_text("01\n02\n")
    (tmp_path / "image-a.hex").write_text("00000001\n00000002\n")
    first = build(tmp_path)
    second = build(tmp_path)
    assert first == second
    assert first["tensor_count"] == 2
    assert first["line_count"] == 2
    assert first["image_bytes"] == 32
    assert [x["name"] for x in first["tensors"]] == ["a", "z"]
    assert first["tensors"][0]["ddr3_offset"] == 0
    assert first["tensors"][1]["ddr3_offset"] == 16
    assert first["tensors"][0]["payload_bytes"] == 8
    assert first["tensors"][1]["payload_bytes"] == 2
