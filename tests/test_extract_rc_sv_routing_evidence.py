import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pipeline" / "extract_rc_sv_routing_evidence.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("extract_rc_sv_routing_evidence", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = _load_module()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _memory_abi():
    rows = []
    for number in range(146):
        if number <= 24 or 27 <= number <= 45:
            kind, width, depth = "image", 32, 4
        elif number == 25:
            kind, width, depth = "token", 64, 8
        elif number == 26:
            kind, width, depth = "output", 8, 64
        else:
            kind, width, depth = "scratch", 8, 4
        expression = "1'd0" if kind == "image" else f"write_active_{number}"
        rows.append({
            "number": number,
            "width": width,
            "depth": depth,
            "kind": kind,
            "write_enable_sha256": hashlib.sha256(expression.encode()).hexdigest(),
        })
    canonical = _canonical(rows)
    return {
        "schema": "rc-sv-memory-abi-v1",
        "ports": rows,
        "canonical_json": canonical,
        "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def _generated_sv(*, learned_port_zero=True):
    declarations, assignments = [], []
    for number, row in enumerate(_memory_abi()["ports"]):
        address_width = max(1, (row["depth"] - 1).bit_length())

        def pin(direction, name, width):
            packed = f" [{width - 1}:0]" if width > 1 else ""
            return f"  {direction} logic{packed} arg_mem_{number}_{name}"

        declarations.extend((
            pin("output", "addr0", address_width),
            pin("output", "content_en", 1),
            pin("output", "write_en", 1),
            pin("output", "write_data", row["width"]),
            pin("input", "read_data", row["width"]),
            pin("input", "done", 1),
        ))
        is_learned = number <= 24 or 27 <= number <= 45
        expression = "1'd0" if is_learned and learned_port_zero else f"write_active_{number}"
        assignments.append(f"assign arg_mem_{number}_write_en = {expression};")
    return "module main_1(\n" + ",\n".join(declarations) + "\n);\n" + "\n".join(assignments) + "\nendmodule\n"


class ExtractRcSvRoutingEvidenceTest(unittest.TestCase):
    def test_extracts_complete_routing_evidence_from_exact_sv_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main_1.sv"
            source.write_text(_generated_sv(), encoding="utf-8")

            receipt = extract.build_evidence([source], _memory_abi())

            self.assertEqual(receipt["schema"], "rc-sv-routing-evidence-v1")
            self.assertEqual(receipt["source_sha256"], extract.source_sha256([source]))
            self.assertEqual(receipt["memory_abi_sha256"], _memory_abi()["sha256"])
            self.assertEqual(len(receipt["ports"]), 146)
            self.assertEqual(receipt["ports"][0], {
                "port": 0,
                "pins": {"addr0": "output", "content_en": "output", "write_en": "output",
                         "write_data": "output", "read_data": "input", "done": "input"},
                "write_enable": "proven-zero",
            })
            self.assertEqual(receipt["ports"][25]["write_enable"], "dynamic")
            self.assertEqual(receipt["completion"], {
                "max_outstanding": 1,
                "response": "one-done-per-accepted-request",
            })
            self.assertEqual(receipt["sha256"], hashlib.sha256(
                receipt["canonical_json"].encode()).hexdigest())

    def test_rejects_a_learned_port_without_a_proven_zero_write_enable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main_1.sv"
            source.write_text(_generated_sv(learned_port_zero=False), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "arg_mem_0.*proven-zero"):
                extract.build_evidence([source], _memory_abi())

    def test_source_hash_changes_when_the_exact_sv_input_bytes_change(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "main_1.sv"
            source.write_text(_generated_sv(), encoding="utf-8")
            before = extract.source_sha256([source])
            source.write_bytes(source.read_bytes() + b"// source byte provenance\n")
            self.assertNotEqual(extract.source_sha256([source]), before)

    def test_cli_writes_canonical_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main_1.sv"
            source.write_text(_generated_sv(), encoding="utf-8")
            abi_path = root / "memory-abi.json"
            abi_path.write_text(json.dumps(_memory_abi()), encoding="utf-8")
            out = root / "routing-evidence.json"

            extract.main(["--memory-abi", str(abi_path), "--sv", str(source), "--out", str(out)])

            self.assertEqual(json.loads(out.read_text(encoding="utf-8")),
                             extract.build_evidence([source], _memory_abi()))


if __name__ == "__main__":
    unittest.main()
