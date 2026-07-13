# PT2E TOSA zero-point legalization design

## Objective

Make the full TinyStories PT2E W8A8 TOSA graph profile-valid without rewriting arbitrary quantized additions. Validate TOSA immediately after its production, legalize only recognized PT2E quantization scaffolding, and rerun the no-handshake pipeline to its next compiler or synthesis frontier.

## Root cause

Torch-MLIR lowers `quantized_decomposed.quantize_per_tensor` into a float rounding sequence followed by:

```text
tosa.cast f32 -> i8
tosa.add i8, i8_zero_point -> i8
tosa.cast i8 -> i32
```

The selected TOSA profile rejects the narrow `tosa.add`; its integer add form requires `i32` operands and result. The full-model failures have the stronger structural signature of quantization zero-point scaffolding: the narrow add consumes a float-to-`i8` cast and a splat `tosa.const`, and its result is immediately widened to `i32` for dequantization. An arbitrary `i8 tosa.add` does not provide that evidence and must remain untouched.

## Considered approaches

1. Patch Torch-MLIR at the source. This produces the cleanest TOSA, and an archived patch demonstrates it, but reintroduces a local upstream patch stack that the active pipeline deliberately removed.
2. Add a local post-TOSA MLIR pass. This keeps upstream Torch-MLIR unchanged, provides an isolated regression test, and can be removed when upstream lowering is corrected. This is the selected approach.
3. Rewrite all narrow TOSA additions. This is rejected because real quantized tensor additions can have different scales and zero points and require scale-aware rescaling.

## Pass contract

Add `llm2fpga-legalize-pt2e-tosa-zero-point` to the existing MLIR pass plugin. The pass matches only a `tosa.add` for which all of the following hold:

- Both operands and the result are ranked tensors with `i8` elements.
- One operand is produced by `tosa.cast` from a floating-point tensor.
- The other operand is a splat `tosa.const` representing a scalar/broadcast zero point.
- Shapes are broadcast-compatible under the already valid TOSA add.

For a match, the pass creates:

```text
tosa.cast rounded_float -> i32
tosa.const zero_point : i32
tosa.add i32, i32 -> i32
tosa.rescale i32 -> i8 with identity scale and zero input/output zero points
tosa.cast i8 -> i32
```

All existing consumers are retained and receive the same `i8` boundary, whether they dequantize, reshape, feed integer matmul, or share the value. Consumer count and kind are not part of quantization semantics. `tosa.rescale` performs the profile-valid saturating narrowing; TOSA does not permit `tosa.clamp` on `i32`. The pass does not match `i8` additions lacking the producer provenance signature and does not attempt scale alignment.

## Pipeline integration

Split TOSA production into two durable boundaries:

1. Torch-MLIR emits raw TOSA.
2. The local pass plugin legalizes PT2E zero-point scaffolding, then `tosa-validate` checks the resulting module.
3. TOSA-to-Linalg consumes only validated TOSA.

The public model aliases remain unchanged. The validated/legalized TOSA replaces the current TOSA stage consumed by Linalg, while diagnostics preserve enough information to identify raw versus legalized failures.

## Tests

- A minimal positive reproducer proves the recognized PT2E pattern is rewritten to an `i32` add and identity `tosa.rescale` narrowing to `i8`.
- A negative reproducer proves an arbitrary `i8 tosa.add` is unchanged and therefore still rejected by `tosa-validate`.
- A second negative case proves a zero-point-like add with multiple uses is not rewritten.
- Repository tests assert pass registration and pipeline ordering.
- The full TinyStories package is rebuilt through Yosys or until the next failing stage, with timing, artifact size, graph shape, and frontier evidence recorded.

## Success criteria

- The original illegal PT2E zero-point additions no longer reach TOSA validation.
- Unrecognized `i8 tosa.add` operations are not silently changed.
- `tosa-validate` runs before TOSA-to-Linalg.
- The full scout advances beyond the previous TOSA-to-Linalg `i8`-add failure, or produces evidence that precisely distinguishes any remaining instance from the matched scaffolding.
- Equivalence, board validation, and SmoothQuant remain deferred as previously decided.
