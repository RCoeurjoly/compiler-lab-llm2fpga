# Native Calyx `std_float_const` Reproducer

The fixed-layernorm representative-core no-handshake pipeline now reaches CIRCT
Calyx MLIR and `circt-translate --export-calyx`, but native Calyx 0.7.1 rejects
the exported Futil when it contains cells like:

```futil
cst = std_float_const(0, 32, 0.000000);
```

This is a backend compatibility blocker after Calyx export. Textual Futil or
MLIR rewriting is not an acceptable fix.

The full representative-core export also imports SoftFloat-style primitive
files such as `primitives/float.futil`, `primitives/float/addFN.futil`, and
`primitives/float/divSqrtFN.futil`. The packaged native Calyx 0.7.1 library in
this repo does not include those files, so replacing only `std_float_const`
would not make the route valid.

Acceptable fixes are version-aligning the official Calyx backend with CIRCT's
exporter, changing dialect/model semantics to avoid float constants before
Calyx export, or fixing the exporter/backend through a real compiler/backend
change.
