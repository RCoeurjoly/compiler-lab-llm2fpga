# Calyx Memref-Result Wrapper Reproducer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce and preserve whether upstream SCF-to-Calyx drops a scalar result when it creates a `main` wrapper for a top-level function with a `memref` argument.

**Architecture:** Run the packaged upstream `circt-opt` on one minimal MLIR function, check in the unedited output, and assert the inner-component and wrapper interfaces separately. The test records observed behavior and does not implement or endorse a fix.

**Tech Stack:** MLIR, CIRCT SCF-to-Calyx, Nix, Python `unittest`, Markdown.

## Global Constraints

- Use the repository-packaged upstream CIRCT binary.
- Preserve generated Calyx MLIR without textual modification.
- Test both the retained inner output and generated wrapper output shape.
- Do not implement a workaround or compiler fix.

---

### Task 1: Create and verify the upstream reproducer

**Files:**
- Create: `tests/test_calyx_memref_result_wrapper.py`
- Create: `reproducers/calyx-top-level-memref-result/input.mlir`
- Create: `reproducers/calyx-top-level-memref-result/output.calyx.mlir`
- Create: `reproducers/calyx-top-level-memref-result/README.md`

**Interfaces:**
- Consumes: `circt-opt --lower-scf-to-calyx='top-level-function=kernel'`.
- Produces: checked-in input/output evidence and one structural regression test.

- [ ] **Step 1: Write the failing structural test**

Create `tests/test_calyx_memref_result_wrapper.py`:

```python
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
        self.assertRegex(kernel.group(0), r"out0[^\n]*i32")
        self.assertNotRegex(main.group(0), r"out0[^\n]*i32")
        self.assertIn("--lower-scf-to-calyx='top-level-function=kernel'", readme)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify RED**

```bash
python3 -m unittest discover -s tests -p 'test_calyx_memref_result_wrapper.py' -v
```

Expected: `ERROR` because the reproducer files do not exist yet.

- [ ] **Step 3: Add the minimal input**

Create `input.mlir` exactly as follows:

```mlir
module {
  func.func @kernel(%memory: memref<4xi32>) -> i32 {
    %c0 = arith.constant 0 : index
    %value = memref.load %memory[%c0] : memref<4xi32>
    return %value : i32
  }
}
```

- [ ] **Step 4: Run upstream CIRCT and preserve its output**

```bash
CIRCT=$(nix build .#circt --no-link --print-out-paths)
"$CIRCT/bin/circt-opt" \
  reproducers/calyx-top-level-memref-result/input.mlir \
  --lower-scf-to-calyx='top-level-function=kernel' \
  -o reproducers/calyx-top-level-memref-result/output.calyx.mlir
```

Expected: exit 0 and an output containing both `calyx.component @kernel` and `calyx.component @main`.

- [ ] **Step 5: Document the exact observation**

Create `README.md` with the command above, CIRCT package revision from `flake.lock`, the inner `kernel` port shape, the top-level `main` port shape, and a conclusion limited to what the output demonstrates. State explicitly that the output file is unedited tool output.

- [ ] **Step 6: Verify and commit**

```bash
python3 -m unittest discover -s tests -p 'test_calyx_memref_result_wrapper.py' -v
python3 -m unittest discover -s tests -v
git diff --check
git add tests/test_calyx_memref_result_wrapper.py \
  reproducers/calyx-top-level-memref-result
git commit -m "test: reproduce Calyx top-level result loss"
```

Expected: focused and complete test suites pass, the diff is clean, and all reproducer evidence is committed.
