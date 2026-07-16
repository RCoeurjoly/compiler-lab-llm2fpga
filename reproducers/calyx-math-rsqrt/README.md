# Calyx `math.rsqrt` Reproducer

The frozen RC source contains scalar `math.rsqrt` in its LayerNorm-like paths.
The active pre-Calyx helper currently rewrites this source form to `1.0 /
math.sqrt`; the separate `calyx-math-sqrt` MRC verifies only that current CIRCT
accepts the resulting `math.sqrt` primitive. Neither fact is a raw-code
equivalence result for the rewrite.

The raw input remains checked in because it documents the source signature.
Textual MLIR substitution is not an acceptable fix.
