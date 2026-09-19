"""Fail closed on wrong board-shell identities, not merely familiar basenames."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BoardShellClosureTest(unittest.TestCase):
    def module(self):
        path = ROOT / "scripts/pipeline/materialize_task6_board_shell.py"
        self.assertTrue(path.is_file(), "pinned board-shell materializer is missing")
        spec = importlib.util.spec_from_file_location("board_shell", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_materialized_bytes_are_authenticated_and_reproducible(self):
        module = self.module()
        manifest = module.build_manifest()
        self.assertEqual(manifest["llm2fpga_revision"], "e368449e30d5268433443c7de7a9017e5b9187ee")
        with tempfile.TemporaryDirectory() as directory:
            module.materialize(Path(directory), manifest)
            module.verify_materialized(Path(directory), manifest)
            target = Path(directory) / manifest["sources"][0]["logical_path"]
            target.write_bytes(target.read_bytes() + b"\n// changed\n")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                module.verify_materialized(Path(directory), manifest)

    def test_reject_changed_commit_hash_lane_bist_and_csr_contract(self):
        module = self.module()
        for key, value in [("llm2fpga_revision", "HEAD"), ("byte_lanes", 1),
                           ("bist_mode", 1), ("diagnostic_window", [2048, 2175])]:
            manifest = copy.deepcopy(module.build_manifest())
            manifest[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.verify_manifest(manifest)
        manifest = copy.deepcopy(module.build_manifest())
        manifest["sources"][0]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            module.verify_manifest(manifest)

    def test_reject_missing_wrong_named_or_ambient_dirty_sources(self):
        module = self.module()
        for source in ["/tmp/loader.sv", "/home/roland/LLM2FPGA/fpga/rtl/task6_wishbone_owner_mux.sv",
                       "/nix/store/missing-task6_wishbone_owner_mux.sv"]:
            manifest = copy.deepcopy(module.build_manifest())
            manifest["sources"][0]["source"] = source
            with self.subTest(source=source), self.assertRaises(ValueError):
                module.verify_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
