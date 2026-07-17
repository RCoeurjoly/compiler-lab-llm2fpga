# FPGA transformer/LLM Softmax and exponentiation survey

## Scope

This revision covers the expanded local archive: 443 downloaded PDFs from 448
catalogued arXiv records. The archive now uses a broad LLM/FPGA query plus
RTL, compiler, operator, and transformer/FPGA supplementary queries. The
search preserves query provenance but does not classify papers into mutually
exclusive sets.

Each PDF was converted with `pdftotext -layout` and scanned for Softmax and
related numerical/dataflow concepts. The counts below are document counts;
they are a discovery screen, not proof that every hit implements the concept.

| Concept | PDFs mentioning it |
|---|---:|
| Softmax | 134 |
| `exp`, exponential, or exponentiation | 125 |
| LUT or lookup table | 258 |
| Polynomial or Taylor | 118 |
| Piecewise approximation | 15 |
| Range reduction | 1 |
| Reciprocal/inverse/rsqrt | 127 |
| Normalization/LayerNorm/RMSNorm | 168 |
| GELU/SiLU/SwiGLU | 85 |
| Online Softmax | 7 |
| FlashAttention | 20 |
| Compiler/MLIR/PyTorch/HLS/RTL/dataflow/fusion terms | 354 |
| Approximation/fixed-point/integer/mixed precision | 344 |

The broad scan found 210 PDFs mentioning Softmax or exponentiation. Detailed
manual extraction should focus on those papers, while the remaining papers
remain part of the archive and can reveal compiler or numerical precedents that
do not use the exact keyword.

## What the literature does with Softmax and `exp`

The consistent pattern is that FPGA designs do not pass a generic floating
`math.exp` through a compiler backend and expect ordinary arithmetic lowering.
They expose Softmax as a compound operation and use one or more of:

- online/streaming max and exponential accumulation;
- LUT or table-based exponentials;
- piecewise-linear approximations;
- polynomial/Taylor approximations;
- range reduction before lookup or polynomial evaluation;
- reciprocal/division units for the final normalization;
- mixed-precision special-function units;
- CPU/GPU delegation when the FPGA path does not support the operation.

The important decomposition is:

```text
scores → row maximum → stabilized scores → exp approximation
       → sum/reduction → reciprocal or division → weighted values
```

This is directly relevant to LLM2FPGA: CIRCT rejecting `math.exp` is not an
unusual isolated compiler failure. The architecture needs a recognized
Softmax lowering or an explicit special-function implementation.

## Strongest direct precedents

| Paper | Evidence | Relevance to LLM2FPGA |
|---|---|---|
| DB-Attn / Pushing the Limits of BFP (`2502.00026`) | Dynamic Hierarchical LUT (DH-LUT) uses shared exponents and lookup structures for Softmax exponentials | Direct precedent for a bounded, quantized exponent implementation |
| CORDIC Is All You Need (`2503.11685`) | Uses CORDIC-style arithmetic for nonlinear functions | Standard hardware algorithm family worth testing against LUT/polynomial candidates |
| LoopLynx (`2504.09561`) | Treats the global Softmax sum as a dataflow/pipeline dependency | Shows that reduction scheduling is a first-class issue, not just `exp` arithmetic |
| AccLLM (`2505.03745`) | Dedicated nonlinear processing engine and fused attention stages | Supports explicit special-function hardware around quantized matmuls |
| Hummingbird (`2507.03308`) | Online Softmax fuses maximum search and exponential accumulation | Strong streaming/dataflow precedent |
| FAST-Prefill (`2602.20515`) | LUT-based exponential approximation plus running sum and reciprocal; avoids floating Softmax units | Very close to the desired hardware-looking route |
| SkipOPU (`2603.14785`) | FlashAttention-style incremental max/exponential-sum updates fused with linear work | Shows how to hide reduction latency and reduce intermediate storage |
| Design Conductor 2.0 / VerTQ (`2605.05170`) | Generated a polynomial exponent unit; a low-degree polynomial failed numerically and was replaced by fifth-order Taylor/Horner evaluation | Direct precedent for approximation validation and correction in an automated hardware pipeline |
| QUARK (`2511.06767`) | Circuit sharing for repeated nonlinear transformer patterns | Relevant to resource reduction when multiple Softmax/nonlinear sites share hardware |
| TATAA (`2411.03697`) | Programmable mixed-precision transformer arithmetic | Relevant to keeping special functions at a different precision from W8A8 matmuls |
| DFX (`2209.10797`) | Transformer text-generation FPGA appliance with Softmax and nonlinear pipeline concerns | System-level precedent for treating Softmax as a distinct pipeline stage |

Additional earlier evidence remains relevant: FlightLLM stores Softmax/SiLU/GELU
tables as small single-access data in DDR; TeLLMe and TeLLMe v2 use explicit
special-function structures; PD-Swap uses online/block attention; and the
hardware surveys identify Softmax and normalization as operations that do not
map naturally onto matmul-centric datapaths.

## Compiler-pipeline evidence: StreamTensor

StreamTensor (`2509.13694`) is now included in the expanded archive. Its full
text describes a compiler framework that constructs stream-based dataflow
accelerators, uses an iterative tensor type system, performs kernel fusion,
buffer allocation, and memory optimization, and applies MLIR Linalg passes to
the intermediate representation.

The paper is highly relevant to compiler architecture, but the PDF does not
provide a direct `math.exp`/Softmax lowering recipe comparable to DH-LUT,
FAST-Prefill, or VerTQ. Its lesson for LLM2FPGA is therefore structural:
compiler IR and dataflow transformations can solve streaming, fusion, and
buffer problems, but they do not remove the need for a numerical implementation
of exponentiation.

## Trust and equivalence implications

Literature precedent makes LUT, polynomial, CORDIC, and online-Softmax routes
defensible engineering choices. It does not prove that any candidate is
equivalent to our frozen PT2E W8A8 model.

For LLM2FPGA, each candidate must specify:

1. stabilized input domain;
2. numerical format and saturation behavior;
3. approximation error versus the PyTorch PT2E oracle;
4. effect on all logits and selected token ID;
5. resource and latency cost after complete lowering.

The most conservative next experiments are therefore:

1. a standard LUT/range-bounded exponential candidate;
2. a polynomial or CORDIC candidate;
3. online Softmax/dataflow restructuring;
4. PyTorch-versus-SV output comparison before accepting any route.

No candidate should be silently substituted into the canonical PT2E graph.

## Limits

The keyword counts include papers outside LLM inference, including vision
transformers, generic FPGA neural-network work, surveys, and unrelated uses of
“exponential.” They are intentionally recall-oriented. The next refinement is
manual evidence extraction for the 134 Softmax papers, with separate fields for
exact arithmetic, approximation family, input domain, error metric, and whether
the implementation is compiler-generated or hand-designed.
