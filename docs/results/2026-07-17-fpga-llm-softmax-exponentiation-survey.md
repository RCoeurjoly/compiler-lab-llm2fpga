# FPGA LLM Softmax and exponentiation survey

## Scope and method

This is a local full-text screen of the 49 PDFs currently downloaded by the
`LLM-inference-on-FPGA-papers` archive. The archive catalog contains 50 paper
records; one record (`2512.24713`) has no cached PDF filename. PDFs were
converted with `pdftotext -layout` and searched for `softmax`, `exp`,
`exponential`, LUT/table, polynomial, piecewise, and compiler/dataflow terms.
This report records implementation evidence, not claims inferred from an
abstract or title.

StreamTensor is not among the current 50 catalog records, so it is not part of
this local survey. Its compiler-specific treatment must be added separately.

## Main result

The papers do not generally lower a generic floating-point `math.exp` through
an ML compiler into FPGA RTL. They use one of four strategies:

1. Treat Softmax as a dedicated accelerator subsystem.
2. Use online/streaming Softmax to fuse max, exponent accumulation, and the
   weighted-value computation.
3. Replace exponentiation with a LUT, piecewise-linear approximation,
   polynomial, or range-reduced approximation.
4. Keep the special-function unit in a higher-precision format while
   quantizing the surrounding matrix operations.

This is consistent with our CIRCT result: `math.exp` is not an ordinary
HardFloat arithmetic primitive. Hardware projects provide a special-purpose
implementation or reformulate the operation before hardware generation.

## Evidence table

| Paper | FPGA/compiler relevance | Softmax/exponentiation treatment | Trust implication |
|---|---|---|---|
| FlightLLM (`2401.03868`) | Complete FPGA mapping flow; U280 | Stores small single-access Softmax, SiLU, and GELU lookup tables in DDR; large data such as weights/KV cache uses HBM | Explicit LUT subsystem and memory placement; not generic `exp` lowering |
| HLSTransform (`2405.00738`) | HLS transformer implementation | Cites piecewise-linear approximations for nonlinear functions; the paper’s main flow does not establish a generic exact `exp` primitive | Approximation is an established accelerator choice, but its error contract must be measured |
| DB-Attn / BFP nonlinear acceleration (`2502.00026`) | FPGA/ASIC-oriented nonlinear-operation engine | Dynamic Hierarchical LUT (DH-LUT) uses shared exponents and a two-dimensional LUT for exponential values in Softmax | Strong direct precedent for exponent approximation plus explicit numerical analysis |
| LoopLynx (`2504.09561`) | Dataflow FPGA architecture | Identifies Softmax’s global sum dependency as a pipeline obstacle; addresses scheduling/dataflow rather than presenting a generic exponent primitive | The reduction dependency is as important as the exponential arithmetic |
| TeLLMe (`2504.16266`) | Edge FPGA accelerator | Uses a special-function unit and table-oriented hardware around attention; Softmax is handled as part of a fused attention design | Special-function hardware is kept explicit in the architecture |
| AccLLM (`2505.03745`) | U280 FPGA co-design | Uses a dedicated nonlinear processing engine for `exp(S')` and fuses attention stages around Softmax | Quantization does not eliminate the need for an exponentiation strategy |
| Hummingbird (`2507.03308`) | Embedded FPGA LLM accelerator | Uses online Softmax, fusing maximum search and exponential accumulation in one pass | Streaming reformulation reduces buffering and latency, but still requires an exp implementation |
| TENET (`2509.13765`) | LUT-centric ternary FPGA/ASIC design | Main LUT contribution targets ternary matmul; Softmax remains a separate attention/normalization concern | Do not confuse matmul LUTs with an exponentiation solution |
| TeLLMe v2 (`2510.15926`) | End-to-end ternary edge FPGA accelerator | Uses a special-function unit; reverse attention adds exponential operations and consumes additional DSP resources | An explicit cost remains even when matmul is ternary |
| LUT-LLM (`2511.06174`) | Memory-based FPGA LLM accelerator | LUTs target vector-quantized matmul and dequantization; Softmax is not shown as solved by the same LUT mechanism | Operator-specific LUTs are not automatically interchangeable |
| PD-Swap (`2512.11550`) | FPGA prefill/decode reconfiguration | Uses online Softmax/FlashAttention-style blocking and fusion | Streaming/blocking changes the dataflow contract, not necessarily the numeric primitive |
| Hardware acceleration survey (`2512.23914`) | Broad hardware survey | Identifies Softmax as a nonlinear operation that does not map naturally to many crossbar/matmul datapaths | Supports treating Softmax as a distinct hardware concern |
| FAST-Prefill (`2602.20515`) | U280 sparse-attention accelerator | Uses LUT-based exponential approximation followed by running sum and reciprocal, explicitly avoiding floating-point Softmax units | Direct FPGA precedent for replacing float Softmax with bounded LUT hardware |
| SkipOPU (`2603.14785`) | FPGA overlay with dynamic computation | Reformulates Softmax reductions using FlashAttention-style incremental max and exponential-sum updates; fuses them with adjacent linear work | Strong dataflow precedent; exact exp implementation still remains a design choice |
| Design Conductor 2.0 / VerTQ (`2605.05170`) | Automated hardware-generation pipeline | Builds a specialized exponentiation unit for online Softmax; a lower-degree polynomial had excessive error and was replaced by a fifth-order Taylor/Horner implementation | Especially relevant compiler-generation precedent: approximation was validated and repaired against numerical error |

## Compiler-pipeline interpretation

The closest lessons for LLM2FPGA are not that a particular paper provides a
drop-in MLIR pass. They are architectural:

- The compiler should recognize Softmax as a compound pattern, not leave an
  isolated generic `math.exp` operation for a backend that has no exponent
  primitive.
- A practical lowering target is an explicit Softmax subsystem containing
  row-max reduction, stabilized exponentiation, sum reduction, reciprocal or
  division, and the final weighting operation.
- Online Softmax/FlashAttention-style recurrence is valuable because it
  changes the intermediate-storage and dependency problem, even if the
  exponent approximation is unchanged.
- LUT, piecewise, and polynomial implementations are semantic replacements.
  They must be compared against the frozen PT2E W8A8 PyTorch oracle at the
  observable output boundary. Literature precedent makes the strategy
  defensible; it does not prove our implementation correct.
- The papers provide no basis for claiming that PT2E W8A8 alone makes
  Softmax integer. Most retain a special-function path, mixed precision, or
  an explicit approximation.

## Consequence for the current blocker

The most defensible next candidate is not arbitrary textual replacement of
`math.exp`. It is a documented Softmax pattern lowering with:

1. the frozen PT2E graph as numerical oracle;
2. stabilized inputs `x - rowmax(x)`;
3. a clearly specified approximation family (LUT, piecewise-linear, or
   polynomial);
4. a bounded input domain and error measurement;
5. PyTorch-versus-generated-SV comparison of logits and selected token;
6. resource measurement after the complete RC lowers.

The local evidence most directly supports two initial experiments: the
LUT-based exponential route used by FAST-Prefill/DB-Attn, and the polynomial
route illustrated by VerTQ. Neither should be integrated into the canonical
pipeline until the observable equivalence gate passes.

## Limits

The current archive does not contain StreamTensor. The survey therefore does
not yet answer how StreamTensor’s compiler specifically represents or lowers
Softmax. Also, papers that mention Softmax but delegate it to a CPU, GPU, or
pre-existing library are counted as context, not as direct FPGA exponentiation
precedents.
