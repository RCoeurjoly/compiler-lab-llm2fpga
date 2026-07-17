# Six-axis survey of FPGA LLM inference papers

## Scope and method

This survey covers the expanded local archive: 443 downloaded PDFs and 448
catalogued records. Every PDF was converted with `pdftotext -layout` and
screened against six topic vocabularies. The numbers below are document-level
coverage counts, not confirmed claims that every matching paper implements the
topic. They identify the manual evidence set and prevent the survey from
silently focusing only on a few familiar papers.

| Priority | Topic | PDFs with at least one matching term |
|---:|---|---:|
| 1 | Compiler/lowering architecture | 290 |
| 2 | Nonlinear operators and Softmax | 201 |
| 3 | Quantization | 240 |
| 4 | Equivalence and validation | 327 |
| 5 | Memory and host integration | 395 |
| 6 | Resource scaling | 438 |

## 1. Compiler and lowering architecture

The papers use a wide spectrum rather than one standard compiler pipeline:

- HLS libraries and C/C++ kernels, as in HLSTransform and FlexLLM.
- Model-specific mapping/dataflow compilers, as in FlightLLM, LoopLynx, and
  StreamTensor.
- FPGA overlays and programmable instruction/dataflow engines, as in DFX and
  SkipOPU.
- Kernel generators and design-space exploration systems.
- Custom RTL or systolic-array implementations with little reusable compiler
  infrastructure.

StreamTensor is the closest architectural precedent for LLM2FPGA’s compiler
concerns. It uses an iterative tensor type system, MLIR Linalg transformations,
kernel fusion, buffer allocation, stream-layout conversion, and design-space
exploration. Its contribution is primarily dataflow and memory organization;
it does not by itself provide a direct lowering for generic `math.exp`.

The important conclusion is that “compiler pipeline” usually means a
model-/architecture-aware lowering and scheduling stack, not arbitrary PyTorch
to RTL lowering. Generality is normally bounded by supported operators,
layouts, precisions, and target architecture.

## 2. Nonlinear operators and Softmax

Softmax and normalization are repeatedly treated as special cases. The main
implementation families are:

- online/streaming Softmax with fused maximum and exponential accumulation;
- LUT or table-based exponentials;
- piecewise-linear approximations;
- polynomial/Taylor approximations;
- CORDIC or iterative arithmetic;
- mixed-precision special-function units;
- CPU/GPU delegation or an explicitly limited hardware scope.

The recurring dataflow is:

```text
scores → row maximum → stabilized scores → exp → sum → reciprocal/division
       → weighted values
```

The strongest direct precedents are DB-Attn/DH-LUT, CORDIC Is All You Need,
FAST-Prefill, SkipOPU, Hummingbird, AccLLM, and VerTQ/Design Conductor 2.0.
Together they support treating `math.exp` as a compound Softmax lowering
problem, not as an ordinary HardFloat arithmetic operation.

## 3. Quantization

The archive contains extensive INT8, INT4, BFP, ternary, binary, AWQ/GPTQ,
SmoothQuant, and mixed-precision evidence. The important pattern is that
quantization is usually operator-specific:

- matmuls receive the most aggressive quantization;
- activations and KV caches may use different widths;
- Softmax, normalization, reciprocal, and nonlinear functions often retain
  higher precision or receive dedicated approximations;
- BFP and shared-exponent formats are used to make nonlinear ranges more
  hardware-manageable;
- ternary/binary weights do not automatically make the rest of the transformer
  integer-only.

Therefore, PT2E W8A8 is a defensible numerical oracle, but it should not be
described as proof that every operation is integer-shaped or directly
lowerable to FPGA hardware.

## 4. Equivalence and validation

The keyword screen finds many papers discussing accuracy, verification,
simulation, or error, but this is the weakest area of evidence quality. Papers
frequently report model-level accuracy or perplexity without showing:

- PyTorch-versus-RTL numerical comparison;
- exact logit or token-ID agreement;
- a reproducible testbench;
- exhaustive or adversarial input coverage;
- behavior after memory packing and host integration.

This is an opportunity for LLM2FPGA. A PyTorch/PT2E oracle, explicit tolerance
contract, logits-plus-token-ID comparison, and staged equivalence gates would be
stronger than the validation evidence commonly exposed in accelerator papers.

## 5. Memory and host integration

Memory is nearly universal in the corpus. Common approaches include:

- HBM/DDR for weights and KV cache;
- BRAM/URAM for tiles, lookup tables, and local buffers;
- streaming and double buffering;
- weight packing and low-bit storage;
- online or block attention to avoid materializing large intermediates;
- CPU/FPGA or GPU/FPGA partitioning;
- specialized host/runtime control paths.

The survey supports treating memory initialization, external-memory layout,
host tokenization, and output transfer as part of the system contract. A
successful RTL synthesis result alone does not establish end-to-end inference.

## 6. Resource scaling

Nearly every paper reports some resource or performance metric, but the reports
are difficult to compare because they vary in FPGA family, clock, model,
sequence length, batch size, prefill/decode phase, and whether memory is
included. Common strategies are:

- spatial/temporal reuse;
- operator fusion;
- LUT/DSP tradeoffs;
- quantization and sparsity;
- off-chip memory to reduce BRAM pressure;
- model-specific tiling and parallelism;
- multi-FPGA scaling.

The papers rarely provide a reliable scaling law from a tiny representative
core to a complete LLM. LLM2FPGA should therefore measure scaling explicitly
and preserve the decomposition into LUT, FF, DSP, BRAM/URAM, memory bandwidth,
and control overhead.

## Overall conclusions for LLM2FPGA

1. The field is not converging on one universal PyTorch-to-FPGA compiler.
   Successful systems constrain the supported model/operator/precision space.
2. Softmax and related nonlinear operations are a central compiler/hardware
   boundary. They are commonly implemented by dedicated approximation or
   streaming structures.
3. Quantization is necessary but not sufficient. Special functions and
   reductions require their own numerical and hardware decisions.
4. Memory and runtime integration are first-class system components, not
   post-processing details.
5. Published validation is often less rigorous than the contract LLM2FPGA is
   pursuing. Functional equivalence can be a real contribution.
6. Resource numbers are not portable without target, clock, model, sequence,
   phase, and memory assumptions. Representative-core predictive validity must
   be measured rather than presumed.

## Recommended evidence matrix

The next manual pass should fill one row per paper with:

```text
paper, query provenance, model, FPGA, frontend/IR/backend,
operator coverage, Softmax method, nonlinear method, precision,
equivalence evidence, simulation/board evidence, memory system,
LUT/FF/DSP/BRAM/URAM, latency/throughput, source artifacts,
scaling claim, and unresolved limitation
```

The current report is the reproducible broad screen. The next step is manual
extraction of implementation evidence for the 290 compiler hits, beginning with
StreamTensor, FlightLLM, FlexLLM, HLSTransform, LoopLynx, DFX, SkipOPU, and the
papers with direct nonlinear-operator hardware.
