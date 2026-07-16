# Quantized RC Working-System Gate Result

**Status:** Gate 1 is blocked before generated SystemVerilog. This is a
reproducible compiler-arithmetic frontier, not an I/O-interface failure and
not a negative equivalence result.

## Fixed unit under test

The unit under test remains exactly:

'tinystories-w8a8-rc-study-mask9-vocab6-width2'

It is the frozen static XNNPACK PT2E W8A8 export, with vocabulary 6, two
layers, context length 8, hidden width 2, one head, and seed 0. The four fixed
corpus cases and their six final raw int8 codes plus lowest-index argmax token
ID are the numerical oracle.

## Completed evidence

| Boundary | Result | Evidence |
| --- | --- | --- |
| PT2E reference | pass | 'tinystories-w8a8-rc-reference-image' builds the frozen reference, aligned image, manifest, and CPU image replay. |
| CPU image replay | pass | The image contains all 49 PT2E state tensors, is 64-byte aligned and little-endian, and reproduces every corpus output exactly. |
| Direct-Linalg/no-Handshake flat-SCF ABI | pass | '@main' has 27 caller-owned memrefs; '%arg25: memref<1x8xi64>' supplies tokens and '%arg26: memref<1x8x6xi8>' receives the complete raw output. |
| Calyx lowering | blocked | Current CIRCT stops at 'math.exp' before emitting Calyx MLIR. |
| Native SV, Verilator equivalence, memory provenance, image-fixture equivalence, DDR3, host control | not attempted | Each depends on real generated SV from the preceding boundary. |

The Nix-built ABI artifact is:

'tinystories-w8a8-rc-abi-audit'

Its interface.json deliberately records both truths:

~~~json
{
  "status": "flat-scf-abi-confirmed",
  "materialization_required": false,
  "sv_interface": {"status": "blocked-before-sv"}
}
~~~

Therefore no custom RC I/O-materialization pass was added. The model already
has the desired input and output buffer ABI before Calyx; adding a pass would
only introduce a second source of semantic risk.

## Immediate lowerer frontier

The exact no-Handshake route reaches a pre-Calyx program with:

- 1,102 float operations;
- 2 'math.exp' operations, which are the first operations rejected by
  CIRCT's '--lower-scf-to-calyx';
- additional future nonlinear operations: 2 'math.fpowi', 2 'math.tanh',
  and 5 'math.sqrt'.

The captured first diagnostic is:

~~~text
error: Unhandled operation during BuildOpGroups()
%102 = math.exp %101 : f32
~~~

This is consistent with the PT2E W8A8 graph retaining Q/DQ-wrapped floating
arithmetic. W8A8 gives an integer raw output and quantized weights, but it
does not by itself make the full lowered computation integer-only.

## Reproduction

~~~bash
nix build .#tinystories-w8a8-rc-reference-image -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-abi-audit -L --no-link --print-out-paths
nix build .#calyx-math-exp-upstream-reproducer -L --no-link --print-out-paths
nix build .#tinystories-w8a8-rc-working-via-linalg-no-handshake-calyx-native-sv -L
~~~

The first three commands must succeed. The math-exp reproducer records an
upstream error diagnostic and marks its partial Calyx text invalid even though
the pinned tool reports process exit code zero. The last command is expected to fail
without producing placeholder SV, naming 'math.exp' as its first blocker.

## Consequence

Do not implement a fake SV harness, an image-memory adapter, or a DDR3 adapter
against a behavioral substitute. The next bounded experiment must establish
one exact implementation path for the remaining PT2E nonlinear/float
semantics, or select another exact lowering route. Only after real SV exists
should the Gate 1 all-six-code equivalence test and the later external-memory
and board gates resume.
