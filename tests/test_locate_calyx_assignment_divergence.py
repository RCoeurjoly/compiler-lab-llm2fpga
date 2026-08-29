from pathlib import Path
import importlib.util
import tempfile

SCRIPT = Path(__file__).parents[1] / "scripts/comparison/locate_calyx_assignment_divergence.py"
spec = importlib.util.spec_from_file_location("locate", SCRIPT)
locate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(locate)


def test_locates_first_pass_after_marker():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "dump.log"
        path.write_text("before\n[INFO  calyx_opt::pass_manager] foo: 1ms\nneedle\n", encoding="utf-8")
        result = locate.locate(path, "needle")
    assert result["first"] == {"line": 3, "pass": "foo", "text": "needle"}


def test_missing_needle_is_explicit():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "dump.log"
        path.write_text("nothing\n", encoding="utf-8")
        result = locate.locate(path, "needle")
    assert result["first"] is None
    assert result["occurrence_count"] == 0
