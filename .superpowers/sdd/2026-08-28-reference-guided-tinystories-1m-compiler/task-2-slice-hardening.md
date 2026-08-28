# Task 2 slice extraction hardening

## Result

The TinyStories-1M RTLIL extractor now emits complete, reparsable module
definitions. It tracks RTLIL `module`, `cell`, `process`, and `switch` block
depth instead of stopping at the first nested `end`.

Dependency closure now distinguishes generated parameterized design modules
from Yosys primitives:

- a declared `$paramod...` cell type is included in the closure;
- a missing `$paramod...` cell type fails closed as
  `unbounded_dependency_closure`;
- an undeclared ordinary Yosys `$...` cell remains a built-in primitive;
- any `$...` type that is explicitly declared as a module is included.

Extracted filenames are sanitized and receive a stable name hash, so escaped
RTLIL identifiers cannot create accidental subpaths or collide after
sanitization.

The checked-in `source_artifact_unavailable` manifest is now the byte-for-byte
output of this shipped CLI invocation from the repository root:

```sh
nix develop -c python scripts/comparison/extract_tinystories_1m_block_slice.py \
  --repo-root . \
  --contract artifacts/reference/tinystories-1m-kev-gpt-contract.json \
  --out artifacts/comparison/tinystories-1m-slice-manifest.json
```

The non-zero exit status is intentional while the full compiler-generated
TinyStories-1M source artifact remains unavailable. No Representative Core or
historical utilization artifact is substituted for it.

## Verification

Focused Task 2 suite:

```text
nix develop -c python -m unittest discover -s tests \
  -p 'test_tinystories_1m_slice_manifest.py' -v
Ran 9 tests in 0.032s
OK
```

The realistic RTLIL regression contains nested process/switch and cell blocks,
a declared `$paramod` module, and a built-in `$not` cell. The extracted files
are reparsed by the pinned Yosys executable during the test.

Repository-wide suite:

```text
nix develop -c python -m unittest discover -s tests -p 'test_*.py' -v
Ran 355 tests in 3.684s
FAILED (failures=4, errors=1, skipped=1)
```

All Task 1 and Task 2 tests passed in that run. The five failures are outside
this task and pre-existing in unrelated files: one syntax error in
`tests/test_rc_observable_driver.py`, two assertions that the existing
`patches/` directory is absent, and two Representative Core script/document
expectations.
