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
        kernel = re.search(r"calyx.component @kernel.*?^  }", output, re.M | re.S)
        main = re.search(r"calyx.component @main.*?^  }", output, re.M | re.S)
        self.assertIsNotNone(kernel)
        self.assertIsNotNone(main)
        kernel_interface = kernel.group(0).splitlines()[0]
        main_interface = main.group(0).splitlines()[0]
        self.assertRegex(kernel_interface, r"out0[^\n]*i32")
        self.assertNotRegex(main_interface, r"out0[^\n]*i32")
        self.assertIn("--lower-scf-to-calyx='top-level-function=kernel'", readme)


if __name__ == "__main__":
    unittest.main()
