# Deep-review family extraction

Selected project-family/control rows: **36**.

Every populated RQ1–RQ6 value is linked to a portable exact locator in the CSV `evidence_locations` object. Blank CSV values are rendered as `not reported`; no blank is an inferred positive claim.

Evidence status is recorded in `notes` as documented, observed, or inferred. No Task 5 repository audit or reproducibility conclusion is pre-claimed.

## Composition

- `CPU_FPGA_FALLBACK`: 6
- `DATAFLOW`: 15
- `HLS`: 5
- `MLIR_CIRCT`: 2
- `OVERLAY`: 6
- `PARAMETERIZED_RTL`: 2

The 30% route-family cap has a protocol exception for `DATAFLOW` because the mandatory supported Level A families alone exceed the cap.

## Selected families

| CSV row | Family | Level | Route | Score | RQ2 completeness | RQ4 closed requirements | RQ6 reproduction status |
|---:|---|---|---|---:|---|---|---|
| [row 2](deep_review.csv#L2) | CONTROL-COMPILER-LAB — compiler-lab TinyStories MLIR-to-SystemVerilog artifact control | CONTROL | MLIR_CIRCT | 9 | pipeline artifact control; no full-model quality or accelerator-optimization claim | not reported | not reported |
| [row 3](deep_review.csv#L3) | PF-08FCFE46123303F6 — Efficient Kernel Mapping and Comprehensive System Evaluation of LLM Acceleration on a CGLA | A | OVERLAY | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 4](deep_review.csv#L4) | PF-0ED1ABCF4AFE5CD3 — A Tensor-Train Decomposition based Compression of LLMs on Group Vector Systolic Accelerator | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 5](deep_review.csv#L5) | PF-1273CF4396325B77 — Hummingbird: A Smaller and Faster Large Language Model Accelerator on Embedded FPGA | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 6](deep_review.csv#L6) | PF-1326C1A7929FA973 — Understand and Accelerate Memory Processing Pipeline for Large Language Model Inference | A | CPU_FPGA_FALLBACK | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 7](deep_review.csv#L7) | PF-13AB3CD7DD5A3586 — TENET: An Efficient Sparsity-Aware LUT-Centric Architecture for Ternary LLM Inference On Edge | A | OVERLAY | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 8](deep_review.csv#L8) | PF-18F3D35D2702BF81 — Pushing up to the Limit of Memory Bandwidth and Capacity Utilization for Efficient LLM Decoding on Embedded FPGA | A | DATAFLOW | 4 | not reported | not reported | not reported |
| [row 9](deep_review.csv#L9) | PF-229201185ED716DB — StreamTensor: Make Tensors Stream in Dataflow Accelerators for LLMs | C | DATAFLOW | 5 | route-boundary case: cited abstract does not document an end-to-end causal token loop | not reported | not reported |
| [row 10](deep_review.csv#L10) | PF-25C132E08D276681 — TeLLMe v2: An Efficient End-to-End Ternary LLM Prefill and Decode Accelerator with Table-Lookup Matmul on Edge FPGAs | A | DATAFLOW | 4 | end-to-end inference documented in abstract | not reported | not reported |
| [row 11](deep_review.csv#L11) | PF-380B7AC0E2B58F96 — HFRWKV: A High-Performance Fully On-Chip Hardware Accelerator for RWKV | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 12](deep_review.csv#L12) | PF-3DBBE522B68ECE13 — Low Latency Transformer Inference on FPGAs for Physics Applications with hls4ml | C | HLS | 4 | route-boundary case: cited abstract does not document an end-to-end causal token loop | not reported | not reported |
| [row 13](deep_review.csv#L13) | PF-3F53C7B76FD59E5C — DNNVM : End-to-End Compiler Leveraging Heterogeneous Optimizations on FPGA-based CNN Accelerators | C | OVERLAY | 3 | route-boundary case: cited abstract does not document an end-to-end causal token loop | not reported | not reported |
| [row 14](deep_review.csv#L14) | PF-40340776F6A61628 — TerEffic: Highly Efficient Ternary LLM Inference on FPGA | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 15](deep_review.csv#L15) | PF-4EBDD47F47E94583 — Automating Versatile Time-Series Analysis with Tiny Transformers on Embedded FPGAs | C | PARAMETERIZED_RTL | 5 | route-boundary case: cited abstract does not document an end-to-end causal token loop | not reported | not reported |
| [row 16](deep_review.csv#L16) | PF-52A5A896CDEFF78D — FlexLLM: Composable HLS Library for Flexible Hybrid LLM Accelerator Design | A | HLS | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 17](deep_review.csv#L17) | PF-5345A35EEB976D35 — FastMamba: A High-Speed and Efficient Mamba Accelerator on FPGA with Accurate Quantization | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 18](deep_review.csv#L18) | PF-5423EA8E2FD4952E — Platform-Aware FPGA System Architecture Generation based on MLIR | C | MLIR_CIRCT | 2 | route-boundary case: cited abstract does not document an end-to-end causal token loop | not reported | not reported |
| [row 19](deep_review.csv#L19) | PF-5487714A7E757A5C — TATAA: Programmable Mixed-Precision Transformer Acceleration with a Transformable Arithmetic Architecture | A | OVERLAY | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 20](deep_review.csv#L20) | PF-5EF68A1A692430F1 — On-Device Qwen2.5: Efficient LLM Inference with Model Compression and Hardware Acceleration | A | CPU_FPGA_FALLBACK | 5 | not reported | not reported | not reported |
| [row 21](deep_review.csv#L21) | PF-6242F1E077C405BE — EdgeLLM: A Highly Efficient CPU-FPGA Heterogeneous Edge Accelerator for Large Language Models | A | CPU_FPGA_FALLBACK | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 22](deep_review.csv#L22) | PF-6B691A2E44900498 — PD-Swap: Prefill-Decode Logic Swapping for End-to-End LLM Inference on Edge FPGAs via Dynamic Partial Reconfiguration | A | DATAFLOW | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 23](deep_review.csv#L23) | PF-7E3A5FA298AD6A6F — MEADOW: Memory-efficient Dataflow and Data Packing for Low Power Edge LLMs | A | DATAFLOW | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 24](deep_review.csv#L24) | PF-7FF210B343FEAC43 — FlightLLM: Efficient Large Language Model Inference with a Complete Mapping Flow on FPGAs | A | PARAMETERIZED_RTL | 5 | not reported | not reported | not reported |
| [row 25](deep_review.csv#L25) | PF-854ADC02588B68F7 — AccLLM: Accelerating Long-Context LLM Inference Via Algorithm-Hardware Co-Design | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 26](deep_review.csv#L26) | PF-85A0286974EFC09E — LightMamba: Efficient Mamba Acceleration on FPGA with Quantization and Hardware Co-design | A | DATAFLOW | 6 | not reported | not reported | not reported |
| [row 27](deep_review.csv#L27) | PF-86FE8DBFB50CB04C — Understanding the Potential of FPGA-Based Spatial Acceleration for Large Language Model Inference | A | HLS | 5 | not reported | not reported | not reported |
| [row 28](deep_review.csv#L28) | PF-99E0323A054EE2AD — LUT-LLM: Efficient Large Language Model Inference with Memory-based Computations on FPGAs | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 29](deep_review.csv#L29) | PF-ADA5DD9E17D22182 — Research on LLM Acceleration Using the High-Performance RISC-V Processor "Xiangshan" (Nanhu Version) Based on the Open-Source Matrix Instruction Set Extension (Vector Dot Product) | A | OVERLAY | 5 | not reported | not reported | not reported |
| [row 30](deep_review.csv#L30) | PF-B1181609C0AF254C — SpeedLLM: An FPGA Co-design of Large Language Model Inference Accelerator | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 31](deep_review.csv#L31) | PF-BBFD7FC8E3510445 — DFX: A Low-latency Multi-FPGA Appliance for Accelerating Transformer-based Text Generation | A | OVERLAY | 5 | end-to-end inference documented in abstract | not reported | not reported |
| [row 32](deep_review.csv#L32) | PF-CAA8FD9CB8D76AF5 — LlamaF: An Efficient Llama2 Architecture Accelerator on Embedded FPGAs | A | CPU_FPGA_FALLBACK | 4 | not reported | not reported | not reported |
| [row 33](deep_review.csv#L33) | PF-DA130C9A8682ACE6 — LoopLynx: A Scalable Dataflow Architecture for Efficient LLM Inference | A | DATAFLOW | 5 | not reported | not reported | not reported |
| [row 34](deep_review.csv#L34) | PF-E18206EB018BCA85 — HPU: High-Bandwidth Processing Unit for Scalable, Cost-effective LLM Inference via GPU Co-processing | A | CPU_FPGA_FALLBACK | 5 | not reported | not reported | not reported |
| [row 35](deep_review.csv#L35) | PF-E7AA5B0B1A09F007 — HLSTransform: Energy-Efficient Llama 2 Inference on FPGAs Via High Level Synthesis | A | HLS | 6 | not reported | not reported | not reported |
| [row 36](deep_review.csv#L36) | PF-E9C1300B04E80B95 — Compiler-Driven FPGA Virtualization with SYNERGY | C | CPU_FPGA_FALLBACK | 2 | route-boundary case: cited abstract does not document an end-to-end causal token loop | not reported | not reported |
| [row 37](deep_review.csv#L37) | PF-F284524C8FAF1FF5 — ELiTeFormer: An Efficient Transformer for FPGAs | A | HLS | 5 | end-to-end inference documented in abstract | not reported | not reported |

## Scope limitation

This Task 4 extraction is deliberately limited to claims supported by the frozen paper/title/abstract evidence and the pinned compiler-lab control. Repository availability, licenses, dependency closure, and reproduction status remain `not reported` unless the row contains an exact citation. Task 5 performs the broader repository audit.
