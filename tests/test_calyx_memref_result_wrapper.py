import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPRODUCER = ROOT / "reproducers" / "calyx-top-level-memref-result"


class CalyxMemrefResultWrapperTest(unittest.TestCase):
    def test_upstream_wrapper_discards_inner_scalar_result(self) -> None:
        source = (REPRODUCER / "input.mlir").read_text(encoding="utf-8")
        output = (REPRODUCER / "output.calyx.mlir").read_text(encoding="utf-8")
        readme = (REPRODUCER / "README.md").read_text(encoding="utf-8")

        self.assertIn("func.func @kernel", source)
        self.assertIn("memref<4xi32>", source)
        self.assertIn("-> i32", source)
        kernel = re.search(
            r"calyx\.component\s+@kernel\b\s*\([^)]*\)\s*->\s*\(([^)]*)\)",
            output,
            re.S,
        )
        main = re.search(
            r"calyx\.component\s+@main\b\s*\([^)]*\)\s*->\s*\(([^)]*)\)",
            output,
            re.S,
        )
        self.assertIsNotNone(kernel)
        self.assertIsNotNone(main)
        self.assertRegex(
            kernel.group(1),
            r"^\s*%out0\s*:\s*i32\s*,\s*%done\s*:\s*i1\s*\{\s*done\s*\}\s*$",
        )
        self.assertRegex(
            main.group(1),
            r"^\s*%done\s*:\s*i1\s*\{\s*done\s*\}\s*$",
        )
        self.assertIn("--lower-scf-to-calyx='top-level-function=kernel'", readme)


if __name__ == "__main__":
    unittest.main()
