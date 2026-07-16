# FPGA Transformer Nonlinear Practice Survey

**Question.** How do published Transformer/LLM accelerators deal with the
nonlinear operations that remain in the frozen PT2E W8A8 representative core:
`math.exp`, `math.tanh`, `math.fpowi`, and `math.rsqrt`?

## Scope and finding

This is a brief implementation-practice survey, not a performance comparison
and not a claim that any cited method preserves this repository's frozen PT2E
W8A8 semantics. Across the sources below, Softmax exponentials, GELU-like
activations, and normalization roots are normally handled by approximation or
reformulation: range reduction plus polynomial or piecewise-linear arithmetic,
lookup tables, iterative root arithmetic, or a dedicated special-function
block. The sources do not establish a bit-exact route for the RC's PyTorch
`math.exp`, `math.tanh`, `math.fpowi`, or `math.rsqrt` operations through their
original Q/DQ-wrapped floating-point semantics.

The last sentence is an inference from the cited papers' stated implementation
scopes, not a claim that no such implementation exists anywhere.

## Evidence map

| Source | Hardware context | `exp` / Softmax | GELU, `tanh`, or `pow` | `sqrt` / `rsqrt` / normalization | Interpretation for this RC |
| --- | --- | --- | --- | --- |
| [I-BERT](https://proceedings.mlr.press/v139/kim21d.html) | Integer-only BERT quantization; not an FPGA implementation | Replaces Softmax with an integer-only approximation | Replaces GELU with an integer-only approximation; it is not a direct `math.tanh` or `math.fpowi` preservation result | Replaces LayerNorm with an integer-only approximation | A model-level precedent for reformulating nonlinear layers before hardware lowering, but not proof of equivalence to this frozen PT2E export. |
| [FlightLLM](https://dai.sjtu.edu.cn/my_file/pdf/4fcb20f6-7386-4907-a138-bb24e21d2260.pdf) | FPGA LLM system | Assigns Softmax to its MISC instruction class; the paper lists Softmax lookup tables among small single-access data stored in DDR | The same MISC/LUT treatment includes GELU and SiLU; the paper does not present this as a direct primitive `tanh` or `pow` implementation | Assigns LayerNorm to MISC | Architectural precedent for an explicit special-function/LUT subsystem, not a numerical specification for this RC. |
| [SwiftTron](https://iris.polito.it/retrieve/handle/11583/2987506/cd452780-3ae7-457f-9349-d980c79d0ac7/2304.03986.pdf) | Transformer accelerator; ASIC rather than FPGA | Subtracts the maximum, range-reduces the exponential input to `[-ln(2), 0]`, then uses a second-order polynomial | Approximates GELU's `erf` component with a second-order polynomial; this is a GELU reformulation rather than direct `math.tanh` or `math.fpowi` preservation | Uses an iterative square-root algorithm for LayerNorm | A detailed architectural precedent for polynomial/iterative nonlinear units, but its ASIC setting and approximation choice are not an approved FPGA compiler route. |
| [Approximation-Based Softmax and LayerNorm Accelerator](https://www.mdpi.com/2079-9292/14/12/2337) | FPGA VU37P; BERT and GPT-2 | Uses piecewise-linear exponential approximation in Softmax | Does not establish a direct `tanh` or `pow` primitive route | Uses Newton-Raphson square-root approximation in LayerNorm | Direct FPGA evidence that approximation is practical, together with the paper's caution that generation can be more sensitive than classification. |
| [Hardware-Oriented Approximations of Softmax and RMSNorm](https://www.mdpi.com/2072-666X/17/1/84) | FPGA U55C; LLaMA2-7B | Uses range reduction, bipartite lookup tables, and log-domain division for Softmax | Does not establish a direct `tanh` or `pow` primitive route | Uses leading-one detection, lookup tables, and multiplication for reciprocal square root in RMSNorm | Recent FPGA/LLM precedent for fixed-point Softmax and reciprocal-root approximation, not a bit-exact implementation of `math.rsqrt`. |

## Cross-paper reading by source operation

- `math.exp`: published hardware work usually first reduces its input range,
  then uses a polynomial, piecewise-linear approximation, or lookup table. It
  is commonly embedded inside a complete Softmax dataflow that also performs
  maximum subtraction and normalization.
- `math.rsqrt`: LayerNorm or RMSNorm is generally treated as a compound
  operation. Papers use iterative square-root arithmetic or a
  leading-one-detection/LUT/multiply reciprocal-root datapath rather than
  retain a general floating `math.rsqrt` operation.
- `math.tanh` and `math.fpowi`: this small source set does not document a
  direct primitive implementation matching PyTorch's operations. In practice
  the surrounding GELU is reformulated or table/polynomial approximated, so
  the important comparison is the full activation's numerical behaviour, not
  local textual replacement of either primitive.

## What this does and does not authorize

This survey makes a future approximation or reformulation study defensible: it
gives concrete, published families of alternatives to investigate after the
standard-route frontier is measured. It does not authorize changing the frozen
PT2E W8A8 oracle, silently rewriting an operation in the current route, or
calling a LUT/polynomial/iterative design exact.

Any candidate based on these techniques needs its own declared numerical
contract and all-four-corpus-case comparison of six raw int8 output codes plus
the token ID against the frozen reference. Until that comparison passes under
an explicitly approved tolerance or exactness policy, the technique is not a
semantic-equivalence proof.
