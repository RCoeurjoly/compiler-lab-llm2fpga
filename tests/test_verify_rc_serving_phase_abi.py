from pathlib import Path

import pytest

from scripts.pipeline.verify_rc_serving_phase_abi import phase_shapes


ROOT = Path(__file__).resolve().parents[1]


def test_phase_shapes_require_dense_memrefs(tmp_path: Path) -> None:
    path = tmp_path / "bad.mlir"
    path.write_text("module { func.func @main(%arg1: memref<1xi64>) { } }\n")
    with pytest.raises(ValueError, match="dense"):
        phase_shapes(path)


def test_phase_shapes_reject_missing_main(tmp_path: Path) -> None:
    path = tmp_path / "bad.mlir"
    path.write_text("module { }\n")
    with pytest.raises(ValueError, match="missing"):
        phase_shapes(path)
