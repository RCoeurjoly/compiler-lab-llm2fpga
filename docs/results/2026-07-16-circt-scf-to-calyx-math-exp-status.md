# CIRCT SCF-to-Calyx `math.exp` Diagnostic-Status Candidate

## Scope

This note records a local, issue-ready observation. No upstream issue or patch
has been filed from this repository.

## Revisions inspected

- Pinned CIRCT: `5dc62fe46c9dbf8936f4f706083301e7503715eb` (`2026-03-31`).
- Upstream main inspected: `ffd2188ab345cdaf655ebcec348d9635bedd0f3e`
  (`2026-07-16`).
- Result of source inspection: `math::ExpOp` remains absent from the
  SCF-to-Calyx supported-operation handling; the post-pin SCF-to-Calyx change
  was tracking-safe mutation refactoring, not this failure-status behavior.

## Minimal command

```sh
/nix/store/6nz8q4n4z2c3yb6xikq84rbn1rrh61xy-circt-1.144.0g20260331_5dc62fe/bin/circt-opt \
  reproducers/calyx-math-exp/input.mlir \
  --lower-scf-to-calyx='top-level-function=main' \
  -o /dev/null
```

## Expected and observed behavior

Expected: an error diagnostic causes a nonzero process status and no caller
accepts partial Calyx text as a valid lowering.

Observed: CIRCT prints `error: Unhandled operation during BuildOpGroups()`
naming `math.exp`, writes partial Calyx text when given an output path, and
returns status zero.

The full RC also reaches a later verifier error and is recorded locally as a
failed Calyx stage. That later error does not repair the direct minimal-case
status defect.

## Issue-ready report

Title: `SCF-to-Calyx reports an unhandled math.exp error but exits zero and
writes partial output`.

Attach `reproducers/calyx-math-exp/input.mlir`, the exact command above,
`lower.log`, `exit-code.txt`, and `partial.calyx.mlir` from
`calyx-math-exp-upstream-reproducer`.
