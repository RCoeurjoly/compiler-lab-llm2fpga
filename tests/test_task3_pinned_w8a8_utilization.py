import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class Task3PinnedW8A8UtilizationTest(unittest.TestCase):
    def test_nested_task3_flake_exports_pinned_import_and_mapping_api(self) -> None:
        flake = read("task3-main/flake.nix")

        for symbol in [
            "mkTask3RtlilFromSlangFilelist",
            "mkTask3XilinxUtilization",
            "task3Toolchain",
            "task3-yosys-toolchain.json",
            "yosys = yosysPkg;",
            "yosysSlang = yosysSlang;",
        ]:
            self.assertIn(symbol, flake)

        self.assertIn(
            "read_slang --threads 1 --no-proc --max-parse-depth 20000", flake
        )
        self.assertIn("mkSynthJsonStages", flake)
        self.assertIn("stages = mkSynthJsonStages {", flake)
        self.assertIn("mkMappedJsonUtilizationReport", flake)


if __name__ == "__main__":
    unittest.main()
