# Calyx CF Assert Blocker

Calyx lowering does not handle `cf.assert` in the direct-Linalg no-handshake
route. The TinyStories representative-core input contains bounds checks around
data-dependent token and embedding indices.

`input.mlir` reproduces the blocker with a minimal `cf.assert`.
`no-assert.mlir` is the accepted shape.

Dropping these assertions is a semantic contract choice, not a generic
optimization. It is only defensible for the hardware inference path if the test
and runtime harness constrain inputs to the model's valid token/index domain.
Do not remove assertions with textual MLIR rewriting; if assertions are dropped,
do it as an explicit named compiler pass.
