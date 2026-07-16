# Calyx 'math.exp' Reproducer

This isolates the first direct-Linalg/no-Handshake Calyx blocker for the exact
PT2E W8A8 TinyStories working representative core. The real RC reaches
'math.exp' in Q/DQ-wrapped floating arithmetic; current CIRCT rejects it
during Calyx operation grouping.

Run the pinned CIRCT package from the repository root:

~~~bash
CIRCT=$(nix build .#circt --no-link --print-out-paths)
"$CIRCT/bin/circt-opt" \
  reproducers/calyx-math-exp/input.mlir \
  --lower-scf-to-calyx='top-level-function=main'
~~~

The expected diagnostic begins:

~~~text
error: Unhandled operation during BuildOpGroups()
%result = math.exp %value : f32
~~~

An acceptable resolution must use an upstream supported lowering or an
explicit hardware implementation with a documented numerical contract that is
validated against the frozen PT2E W8A8 oracle. Replacing exp textually, or
using a resource-scout approximation, is not an equivalence fix.

Current CIRCT may print a partial Calyx module after this diagnostic and still
return exit status zero. That output is not a valid lowered artifact. The
repository wrapper accepts Calyx only when the lowerer returns zero, writes a
non-empty artifact, and emits no MLIR `error:` diagnostic; otherwise it
discards the partial file and records a failed manifest.

The checked-in Nix artifact preserves this observation without treating it as
a successful lower:

~~~bash
nix build .#calyx-math-exp-upstream-reproducer -L --no-link --print-out-paths
~~~

It writes 'lower.log', 'exit-code.txt', 'partial.calyx.mlir', and a manifest
whose 'valid_lowering' field is false. On the pinned CIRCT revision the command
records exit code 0 despite the error diagnostic, which is why consumers must
check the diagnostic/manifest rather than process exit status alone.

Textual MLIR substitution is not an acceptable fix.
