# Route-compatibility Survey Summary

- Generated UTC: 2026-08-06T21:23:01.360303+00:00
- Total records: 461

## Scope & input status

| Scope | Count |
|---|---:|
| full_paper | 443 |
| metadata_fallback | 18 |

| PDF status | Count |
|---|---:|
| ok | 443 |
| unavailable_or_failed | 18 |

## Route hints (high/medium classification)

| Route | Count |
|---|---:|
| mlir_circt | 43 |
| hls | 140 |
| overlay | 39 |
| param_rtl | 129 |
| dataflow | 229 |
| cpu_fpga_fallback | 366 |

## Overall reusability labels

| Label | Count |
|---|---:|
| high | 280 |
| medium | 48 |
| low | 123 |
| none | 10 |

## High/medium reusable candidate shortlist

| arxiv_id | title | reusable | routes | llm_relevance_hits |
|---|---|---|---|---|
| 1206.3332v2 | Inexpensive hardware and software for photon statistics and correlation spectroscopy | high | cpu_fpga_fallback:high | decode;inference |
| 1610.00552v1 | FPGA-Based Low-Power Speech Recognition with Recurrent Neural Networks | high | cpu_fpga_fallback:high | decode;inference |
| 1808.02950v2 | Low-complexity 8-point DCT Approximation Based on Angle Similarity for Image and Video Coding | high | cpu_fpga_fallback:high | attention |
| 1811.10126v1 | Artificial Retina Using A Hybrid Neural Network With Spatial Transform Capability | high | cpu_fpga_fallback:high | decode |
| 2607.02376v1 | Hardware-Enforced Semantic Coordination for Safety-Critical Real-Time Autonomous Systems | high | cpu_fpga_fallback:high |  llm;large language model;gpt;token;inference |
| 2404.15185v1 | PIVOT- Input-aware Path Selection for Energy-efficient ViT Inference | high | cpu_fpga_fallback:high;dataflow:high | transformer;attention;token;inference |
| 2504.17376v1 | On-Device Qwen2.5: Efficient LLM Inference with Model Compression and Hardware Acceleration | high | cpu_fpga_fallback:high;dataflow:high |  llm;large language model;transformer;attention;gpt;token;prefill;decode;inference |
| 2305.18691v2 | Edge-MoE: Memory-Efficient Multi-Task Vision Transformer Architecture with Task-level Sparsity via Mixture-of-Experts | high | cpu_fpga_fallback:high;dataflow:high;hls:high | transformer;attention;token;decode;inference |
| 2401.09890v1 | A Survey on Hardware Accelerators for Large Language Models | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;large language model;transformer;attention;gpt;token;autoregressive;decode;inference |
| 2406.12385v2 | Fast Graph Vector Search via Hardware Acceleration and Delayed-Synchronization Traversal | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;large language model;token;prefill;inference |
| 2501.12032v3 | Accelerating Recommender Model ETL with a Streaming FPGA-GPU Dataflow | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;token;inference |
| 2503.16731v3 | Design and Implementation of an FPGA-Based Hardware Accelerator for Transformer | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;large language model;transformer;attention;inference |
| 2509.04162v1 | Real Time FPGA Based Transformers & VLMs for Vision Tasks: SOTA Designs and Optimizations | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;large language model;transformer;attention;gpt;token;autoregressive;decode;inference |
| 2510.15926v2 | TeLLMe v2: An Efficient End-to-End Ternary LLM Prefill and Decode Accelerator with Table-Lookup Matmul on Edge FPGAs | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2601.15710v1 | FlexLLM: Composable HLS Library for Flexible Hybrid LLM Accelerator Design | high | cpu_fpga_fallback:high;dataflow:high;hls:high |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2211.08110v2 | HeatViT: Hardware-Efficient Adaptive Token Pruning for Vision Transformers | high | cpu_fpga_fallback:high;dataflow:high;hls:medium | transformer;attention;token;inference |
| 2407.18175v1 | Quasar-ViT: Hardware-Oriented Quantization-Aware Architecture Search for Vision Transformers | high | cpu_fpga_fallback:high;dataflow:high;hls:medium |  llm;large language model;transformer;attention;token;inference |
| 2502.05602v3 | UbiMoE: A Ubiquitous Mixture-of-Experts Vision Transformer Accelerator With Hybrid Computation Pattern on FPGA | high | cpu_fpga_fallback:high;dataflow:high;hls:medium | transformer;attention;token;inference |
| 2504.16266v2 | TeLLMe: An Energy-Efficient Ternary LLM Accelerator for Prefilling and Decoding on Edge FPGAs | high | cpu_fpga_fallback:high;dataflow:high;hls:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2506.08496v1 | CoQMoE: Co-Designed Quantization and Computation Orchestration for Mixture-of-Experts Vision Transformer on FPGA | high | cpu_fpga_fallback:high;dataflow:high;hls:medium | transformer;attention;token;inference |
| 2602.20515v1 | FAST-Prefill: FPGA Accelerated Sparse Attention for Long Context LLM Prefill | high | cpu_fpga_fallback:high;dataflow:high;hls:medium |  llm;large language model;transformer;attention;kv cache;token;prefill;decode;inference |
| 2603.05931v1 | A Persistent-State Dataflow Accelerator for Memory-Bound Linear Attention Decode on FPGA | high | cpu_fpga_fallback:high;dataflow:high;hls:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2603.29002v3 | Understand and Accelerate Memory Processing Pipeline for Large Language Model Inference | high | cpu_fpga_fallback:high;dataflow:high;hls:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2003.06700v3 | CoCoPIE: Making Mobile AI Sweet As PIE --Compression-Compilation Co-Design Goes a Long Way | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:low | transformer;attention;inference |
| 2110.06155v1 | Memory-Efficient CNN Accelerator Based on Interlayer Feature Map Compression | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:low | decode;inference |
| 2306.05021v2 | Mixed-TD: Efficient Neural Network Accelerator with Layer-Specific Tensor Decomposition | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:low | transformer;inference |
| 2602.18750v2 | HillInfer: Efficient Long-Context LLM Inference on the Edge with Hierarchical KV Eviction using SmartSSD | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:low |  llm;large language model;transformer;attention;kv cache;token;autoregressive;prefill;decode;inference |
| 2503.11685v1 | CORDIC Is All You Need | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:medium |  llm;transformer;attention;gpt;decode;inference |
| 2512.13263v1 | An End-to-End Neural Network Transceiver Design for OFDM System with FPGA-Accelerated Implementation | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:medium | transformer;attention;inference |
| 2606.31938v1 | FlexViT: A Flexible FPGA-based Accelerator for Edge Vision Transformers | high | cpu_fpga_fallback:high;dataflow:high;mlir_circt:medium | transformer;attention;token;inference |
| 2401.10417v2 | SSR: Spatial Sequential Hybrid Architecture for Latency Throughput Tradeoff in Transformer Acceleration | high | cpu_fpga_fallback:high;dataflow:high;overlay:high | transformer;attention;token;inference |
| 2407.17879v2 | HG-PIPE: Vision Transformer Acceleration with Hybrid-Grained Pipeline | high | cpu_fpga_fallback:high;dataflow:high;overlay:high | transformer;attention;token;inference |
| 2410.04466v4 | Large Language Model Inference Acceleration: A Comprehensive Hardware Perspective | high | cpu_fpga_fallback:high;dataflow:high;overlay:high |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2507.03308v2 | Hummingbird: A Smaller and Faster Large Language Model Accelerator on Embedded FPGA | high | cpu_fpga_fallback:high;dataflow:high;overlay:high |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2505.22194v2 | Refining Datapath for Microscaling ViTs | high | cpu_fpga_fallback:high;dataflow:high;overlay:low |  llm;large language model;transformer;attention;gpt;token;inference |
| 2508.20334v1 | Systolic Array-based Architecture for Low-Bit Integerized Vision Transformers | high | cpu_fpga_fallback:high;dataflow:high;overlay:low |  llm;large language model;transformer;attention;gpt;token;inference |
| 2511.22889v1 | The Immutable Tensor Architecture: A Pure Dataflow Approach for Secure, Energy-Efficient AI Inference | high | cpu_fpga_fallback:high;dataflow:high;overlay:low |  llm;large language model;transformer;attention;gpt;kv cache;token;decode;inference |
| 2603.23668v1 | Energy Efficient Software Hardware CoDesign for Machine Learning: From TinyML to Large Language Models | high | cpu_fpga_fallback:high;dataflow:high;overlay:low |  llm;large language model;transformer;attention;gpt;inference |
| 2605.13507v1 | Efficient Implementation of an Adaptive Transformer Accelerator for Massive MIMO Outdoor Localization | high | cpu_fpga_fallback:high;dataflow:high;overlay:low | transformer;attention;token;inference |
| 2606.12556v2 | ITME: Inference Tiered Memory Expansion with Disaggregated CXL-Hybrid Memories | high | cpu_fpga_fallback:high;dataflow:high;overlay:low |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2401.03868v2 | FlightLLM: Efficient Large Language Model Inference with a Complete Mapping Flow on FPGAs | high | cpu_fpga_fallback:high;dataflow:high;overlay:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2409.09689v1 | CAT: Customized Transformer Accelerator Framework on Versal ACAP | high | cpu_fpga_fallback:high;dataflow:high;overlay:medium |  llm;transformer;attention;token;decode;inference |
| 2409.03384v1 | Hardware Acceleration of LLMs: A comprehensive survey and comparison | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:high |  llm;large language model;transformer;attention;gpt;token;autoregressive;decode;inference |
| 2407.21325v2 | EdgeLLM: A Highly Efficient CPU-FPGA Heterogeneous Edge Accelerator for Large Language Models | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2410.15008v1 | IANUS: Integrated Accelerator based on NPU-PIM Unified Memory System | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2502.10659v1 | Pushing up to the Limit of Memory Bandwidth and Capacity Utilization for Efficient LLM Decoding on Embedded FPGA | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2502.16823v1 | A Review of Memory Wall for Neuromorphic Computing | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low | inference |
| 2506.18003v1 | AMD Versal Implementations of FAM and SSCA Estimators | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low | autoregressive |
| 2509.13765v1 | TENET: An Efficient Sparsity-Aware LUT-Centric Architecture for Ternary LLM Inference On Edge | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2603.22867v1 | TRINE: A Token-Aware, Runtime-Adaptive FPGA Inference Engine for Multimodal AI | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:low | transformer;attention;token;inference |
| 2209.10797v1 | DFX: A Low-latency Multi-FPGA Appliance for Accelerating Transformer-based Text Generation | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:medium | transformer;attention;gpt;token;decode;inference |
| 2410.05686v3 | Deep Learning and Machine Learning with GPGPU and CUDA: Unlocking the Power of Parallel Computing | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:medium | large language model;transformer;attention;token;decode;inference |
| 2505.03745v1 | AccLLM: Accelerating Long-Context LLM Inference Via Algorithm-Hardware Co-Design | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2506.03938v2 | FPGA-Enabled Machine Learning Applications in Earth Observation: A Systematic Review | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:medium | transformer;gpt;token;inference |
| 2512.11920v1 | CXL-SpecKV: A Disaggregated FPGA Speculative KV-Cache for Datacenter LLM Serving | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2603.14785v1 | SkipOPU: An FPGA-based Overlay Processor for Large Language Models with Dynamically Allocated Computation | high | cpu_fpga_fallback:high;dataflow:high;param_rtl:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 1607.04549v2 | DiaSys: Improving SoC Insight Through On-Chip Diagnosis | high | cpu_fpga_fallback:high;dataflow:low | decode |
| 2002.05645v5 | Training Large Neural Networks with Constant Memory using a New Execution Algorithm | high | cpu_fpga_fallback:high;dataflow:low | large language model;transformer;gpt |
| 2105.05530v1 | Winograd Algorithm for AdderNet | high | cpu_fpga_fallback:high;dataflow:low | attention;inference |
| 2209.15436v1 | XR-RF Imaging Enabled by Software-Defined Metasurfaces and Machine Learning: Foundational Vision, Technologies and Challenges | high | cpu_fpga_fallback:high;dataflow:low | inference |
| 2210.14793v1 | M$^3$ViT: Mixture-of-Experts Vision Transformer for Efficient Multi-task Learning with Model-Accelerator Co-design | high | cpu_fpga_fallback:high;dataflow:low | transformer;attention;token;decode;inference |
| 2509.15076v1 | Forecasting and Visualizing Air Quality from Sky Images with Vision-Language Models | high | cpu_fpga_fallback:high;dataflow:low |  llm;large language model;attention;gpt;autoregressive;inference |
| 2601.07130v1 | The Potential Impact of Neuromorphic Computing on Radio Telescope Observatories | high | cpu_fpga_fallback:high;dataflow:low | inference |
| 1701.03534v1 | An OpenCL(TM) Deep Learning Accelerator on Arria 10 | high | cpu_fpga_fallback:high;dataflow:medium | attention;inference |
| 2110.11290v1 | Physical Side-Channel Attacks on Embedded Neural Networks: A Survey | high | cpu_fpga_fallback:high;dataflow:medium | attention;inference |
| 2402.09109v1 | Stochastic Spiking Attention: Accelerating Attention with Stochastic Computing in Spiking Networks | high | cpu_fpga_fallback:high;dataflow:medium | transformer;attention;gpt;token;autoregressive;inference |
| 2502.16141v2 | A Hybrid Neural Architecture: Online Attosecond X-ray Characterization | high | cpu_fpga_fallback:high;dataflow:medium | decode;inference |
| 2509.15097v1 | The Energy-Efficient Hierarchical Neural Network with Fast FPGA-Based Incremental Learning | high | cpu_fpga_fallback:high;dataflow:medium |  llm;large language model;transformer;attention;gpt;inference |
| 2606.23541v1 | HeteroViT: A Versatile Single-Layer Vision Transformer Concept, Co-Designed for Distributed Real-Time Data Reduction on Scientific Detectors | high | cpu_fpga_fallback:high;dataflow:medium | large language model;transformer;attention;token;inference |
| 2404.04527v1 | VTR: An Optimized Vision Transformer for SAR ATR Acceleration on FPGA | high | cpu_fpga_fallback:high;dataflow:medium;hls:low | transformer;attention;token;inference |
| 2009.09736v1 | NetReduce: RDMA-Compatible In-Network Reduction for Distributed DNN Training Acceleration | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low | transformer;gpt |
| 2208.03646v2 | A Length Adaptive Algorithm-Hardware Co-design of Transformer on FPGA Through Sparse Attention and Dynamic Pipelining | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low | transformer;attention;token;decode |
| 2305.04887v1 | Hardware Acceleration of Explainable Artificial Intelligence | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low | attention;inference |
| 2501.14512v1 | Real-world Edge Neural Network Implementations Leak Private Interactions Through Physical Side Channel | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low |  llm;large language model;transformer;attention;gpt;token;inference |
| 2505.18975v4 | FastMamba: A High-Speed and Efficient Mamba Accelerator on FPGA with Accurate Quantization | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low |  llm;large language model;transformer;attention;token;prefill;decode;inference |
| 2507.01035v1 | Research on Low-Latency Inference and Training Efficiency Optimization for Graph Neural Network and Large Language Model-Based Recommendation Systems | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low |  llm;large language model;transformer;attention;gpt;inference |
| 2511.06767v2 | QUARK: Quantization-Enabled Circuit Sharing for Transformer Acceleration by Exploiting Common Patterns in Nonlinear Operations | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low |  llm;large language model;transformer;attention;token;inference |
| 2605.06082v1 | PoTAcc: A Pipeline for End-to-End Acceleration of Power-of-Two Quantized DNNs | high | cpu_fpga_fallback:high;dataflow:medium;mlir_circt:low |  llm;transformer;attention;decode;inference |
| 2101.05314v1 | EXMA: A Genomics Accelerator for Exact-Matching | high | cpu_fpga_fallback:high;dataflow:medium;overlay:low | inference |
| 2109.14349v2 | Relational Memory: Native In-Memory Accesses on Rows and Columns | high | cpu_fpga_fallback:high;dataflow:medium;overlay:low | transformer |
| 2203.01414v3 | ICARUS: A Specialized Architecture for Neural Radiance Fields Rendering | high | cpu_fpga_fallback:high;dataflow:medium;overlay:low | decode;inference |
| 2503.11663v1 | MEADOW: Memory-efficient Dataflow and Data Packing for Low Power Edge LLMs | high | cpu_fpga_fallback:high;dataflow:medium;overlay:low |  llm;large language model;transformer;attention;token;prefill;decode;inference |
| 2606.13708v1 | Tiara: A Programmable Line-Rate ISA for Remote Memory Access | high | cpu_fpga_fallback:high;dataflow:medium;overlay:low |  llm;large language model;attention;kv cache;token;prefill;inference |
| 2606.22621v1 | Multi-Level Resistive Synapses for On-Chip Neural Networks: A Physics-Based Design of a Memristive Crossbar Fabric with Quasi-Continuous Conductance States | high | cpu_fpga_fallback:high;dataflow:medium;overlay:low |  llm;large language model;transformer;attention;kv cache;token;autoregressive;decode;inference |
| 2112.13149v1 | Fast and Scalable Computation of the Forward and Inverse Discrete Periodic Radon Transform | high | cpu_fpga_fallback:high;dataflow:medium;param_rtl:low | attention |
| 2407.02913v1 | SFC: Achieve Accurate Fast Convolution under Low-precision Arithmetic | high | cpu_fpga_fallback:high;dataflow:medium;param_rtl:low | attention;inference |
| 2409.11424v1 | LlamaF: An Efficient Llama2 Architecture Accelerator on Embedded FPGAs | high | cpu_fpga_fallback:high;dataflow:medium;param_rtl:low |  llm;large language model;transformer;attention;gpt;kv cache;token;decode;inference |
| 2512.00335v1 | Efficient Kernel Mapping and Comprehensive System Evaluation of LLM Acceleration on a CGLA | high | cpu_fpga_fallback:high;dataflow:medium;param_rtl:low |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2201.06618v2 | VAQF: Fully Automatic Software-Hardware Co-Design Framework for Low-Bit Vision Transformer | high | cpu_fpga_fallback:high;hls:high;dataflow:high | transformer;attention;token;inference |
| 2404.16158v1 | The Feasibility of Implementing Large-Scale Transformers on Multi-FPGA Platforms | high | cpu_fpga_fallback:high;hls:high;dataflow:high |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2409.14912v1 | Efficient Tabular Data Preprocessing of ML Pipelines | high | cpu_fpga_fallback:high;hls:high;dataflow:high | transformer;attention;gpt;token;decode;inference |
| 2506.20810v1 | FINN-GL: Generalized Mixed-Precision Extensions for FPGA-Accelerated LSTMs | high | cpu_fpga_fallback:high;hls:high;dataflow:high | attention;inference |
| 2512.11550v1 | PD-Swap: Prefill-Decode Logic Swapping for End-to-End LLM Inference on Edge FPGAs via Dynamic Partial Reconfiguration | high | cpu_fpga_fallback:high;hls:high;dataflow:high |  llm;large language model;transformer;attention;kv cache;token;autoregressive;prefill;decode;inference |
| 2604.13933v2 | A Case Study on Energy-Efficient Edge AI Crack Segmentation | high | cpu_fpga_fallback:high;hls:high;dataflow:high | transformer;attention;decode;inference |
| 1803.06305v1 | C-LSTM: Enabling Efficient LSTM using Structured Compression Techniques on FPGAs | high | cpu_fpga_fallback:high;hls:high;dataflow:medium | decode;inference |
| 2208.05163v1 | Auto-ViT-Acc: An FPGA-Aware Automatic Acceleration Framework for Vision Transformer with Mixed-Scheme Quantization | high | cpu_fpga_fallback:high;hls:high;dataflow:medium | transformer;attention;token;decode;inference |
| 2606.27350v2 | CHIA: An open-source framework for principled, agentic AI-driven hardware/software co-design research | high | cpu_fpga_fallback:high;hls:high;param_rtl:high |  llm;large language model;attention;gpt;token;inference |
| 2110.10030v1 | Accelerating Framework of Transformer by Hardware Design and Model Compression Co-Optimization | high | cpu_fpga_fallback:high;hls:high;param_rtl:low | transformer;attention;decode;inference |
| 2512.15838v2 | Low-Latency FPGA Control System for Real-Time Neural Network Processing in CCD-Based Trapped-Ion Qubit Measurement | high | cpu_fpga_fallback:high;hls:high;param_rtl:medium | transformer;attention;token;decode;inference |
| 2007.08563v1 | FTRANS: Energy-Efficient Acceleration of Transformers using FPGA | high | cpu_fpga_fallback:high;hls:low;dataflow:low | transformer;attention;token;decode;inference |
| 2604.23880v1 | Coordinated Multipoint Anti-jamming Beam Pattern Synthesis: From AI Accelerated Algorithm to Hardware Implementation | high | cpu_fpga_fallback:high;hls:low;dataflow:low | decode;inference |
| 2401.02721v3 | A Cost-Efficient FPGA Implementation of Tiny Transformer Model using Neural ODE | high | cpu_fpga_fallback:high;hls:medium | transformer;attention;inference |
| 1602.02517v1 | Energy Efficient Video Fusion with Heterogeneous CPU-FPGA Devices | high | cpu_fpga_fallback:high;hls:medium;dataflow:medium | decode |
| 2310.09949v4 | Chameleon: a Heterogeneous and Disaggregated Accelerator System for Retrieval-Augmented Language Models | high | cpu_fpga_fallback:high;hls:medium;dataflow:medium |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2504.16269v2 | COBRA: Algorithm-Architecture Co-optimized Binary Transformer Accelerator for Edge Inference | high | cpu_fpga_fallback:high;hls:medium;dataflow:medium | large language model;transformer;attention;token;inference |
| 2602.02005v1 | Position: The Need for Ultrafast Training | high | cpu_fpga_fallback:high;hls:medium;dataflow:medium | decode;inference |
| 2505.16335v1 | FPQVAR: Floating Point Quantization for Visual Autoregressive Model with FPGA Hardware Co-design | high | cpu_fpga_fallback:high;hls:medium;mlir_circt:low |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;decode;inference |
| 2002.04971v1 | FastWave: Accelerating Autoregressive Convolutional Neural Networks on FPGA | high | cpu_fpga_fallback:high;hls:medium;overlay:low | attention;autoregressive;inference |
| 2501.06921v1 | Monolithic 3D FPGAs Utilizing Back-End-of-Line Configuration Memories | high | cpu_fpga_fallback:high;hls:medium;param_rtl:low |  llm;large language model;gpt;decode;inference |
| 2503.03088v4 | AHCQ-SAM: Toward Accurate and Hardware-Compatible Post-Training Segment Anything Model Quantization | high | cpu_fpga_fallback:high;hls:medium;param_rtl:low | large language model;transformer;attention;token;decode;inference |
| 2509.13694v2 | StreamTensor: Make Tensors Stream in Dataflow Accelerators for LLMs | high | cpu_fpga_fallback:high;mlir_circt:high;dataflow:high |  llm;large language model;transformer;attention;gpt;token;autoregressive;inference |
| 1805.02094v2 | Exploring Hyper-Parameter Optimization for Neural Machine Translation on GPU Architectures | high | cpu_fpga_fallback:high;mlir_circt:low | transformer;attention;token;decode |
| 2207.03782v1 | VidConv: A modernized 2D ConvNet for Efficient Video Recognition | high | cpu_fpga_fallback:high;mlir_circt:low | transformer;attention;inference |
| 2209.03353v1 | Learned Image Compression with Generalized Octave Convolution and Cross-Resolution Parameter Estimation | high | cpu_fpga_fallback:high;mlir_circt:low | transformer;attention;autoregressive;decode |
| 2408.16495v1 | On-device AI: Quantization-aware Training of Transformers in Time-Series | high | cpu_fpga_fallback:high;mlir_circt:low | transformer;attention;decode;inference |
| 2411.10948v1 | Towards Accurate and Efficient Sub-8-Bit Integer Training | high | cpu_fpga_fallback:high;mlir_circt:low | large language model;transformer;attention;inference |
| 2205.15062v2 | A Transistor Operations Model for Deep Learning Energy Consumption Scaling Law | high | cpu_fpga_fallback:high;mlir_circt:low;dataflow:low | transformer;attention;gpt;inference |
| 2206.10461v1 | An Automatic and Efficient BERT Pruning for Edge AI Systems | high | cpu_fpga_fallback:high;mlir_circt:low;dataflow:low | transformer;attention;gpt;autoregressive;decode;inference |
| 2504.16112v2 | HPU: High-Bandwidth Processing Unit for Scalable, Cost-effective LLM Inference via GPU Co-processing | high | cpu_fpga_fallback:high;mlir_circt:low;dataflow:low |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;decode;inference |
| 2508.07431v1 | Investigating 1-Bit Quantization in Transformer-Based Top Tagging | high | cpu_fpga_fallback:high;mlir_circt:low;dataflow:low |  llm;large language model;transformer;attention;token;inference |
| 2510.14060v2 | Decoding Correlated Errors in Quantum LDPC Codes | high | cpu_fpga_fallback:high;mlir_circt:low;dataflow:low | decode;inference |
| 2510.16418v1 | FourierCompress: Layer-Aware Spectral Activation Compression for Efficient and Accurate Collaborative LLM Inference | high | cpu_fpga_fallback:high;mlir_circt:low;dataflow:low |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;inference |
| 2203.11295v1 | Benchmarking Test-Time Unsupervised Deep Neural Network Adaptation on Edge Devices | high | cpu_fpga_fallback:high;mlir_circt:medium;dataflow:low | inference |
| 2502.00026v2 | Pushing the Limits of BFP on Narrow Precision LLM Inference | high | cpu_fpga_fallback:high;mlir_circt:medium;dataflow:medium |  llm;large language model;transformer;attention;gpt;prefill;inference |
| 2603.28239v3 | A Switch-Centric In-Network Architecture for Accelerating LLM Inference in Shared-Memory Network | high | cpu_fpga_fallback:high;mlir_circt:medium;dataflow:medium |  llm;large language model;transformer;attention;gpt;token;prefill;decode;inference |
| 2502.16473v2 | TerEffic: Highly Efficient Ternary LLM Inference on FPGA | high | cpu_fpga_fallback:high;overlay:high;dataflow:high |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2607.03652v1 | ELiTeFormer: An Efficient Transformer for FPGAs | high | cpu_fpga_fallback:high;overlay:high;dataflow:high |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2409.13975v1 | ProTEA: Programmable Transformer Encoder Acceleration on FPGA | high | cpu_fpga_fallback:high;overlay:high;hls:high | transformer;attention;token;decode;inference |
| 2401.11851v2 | BETA: Binarized Energy-Efficient Transformer Accelerator at the Edge | high | cpu_fpga_fallback:high;overlay:low |  llm;large language model;transformer;attention;gpt;inference |
| 2210.12703v1 | Transformations for accelerator-based quantum circuit simulation in Haskell | high | cpu_fpga_fallback:high;overlay:low;dataflow:low | decode |
| 2403.14047v2 | Accelerating ViT Inference on FPGA through Static and Dynamic Pruning | high | cpu_fpga_fallback:high;overlay:low;dataflow:low | transformer;attention;token;inference |
| 2505.06847v1 | Image processing Application Development on Software Configurable Processor Array | high | cpu_fpga_fallback:high;overlay:low;dataflow:low | decode |
| 2406.17995v4 | Managing Classical Processing Requirements for Quantum Error Correction | high | cpu_fpga_fallback:high;overlay:low;mlir_circt:low | transformer;decode |
| 2104.06535v1 | NPE: An FPGA-based Overlay Processor for Natural Language Processing | high | cpu_fpga_fallback:high;overlay:medium;dataflow:low | transformer;attention;token;decode;inference |
| 2308.13922v1 | An Efficient FPGA-Based Accelerator for Swin Transformer | high | cpu_fpga_fallback:high;overlay:medium;dataflow:medium | transformer;attention;inference |
| 2403.20230v1 | An FPGA-Based Reconfigurable Accelerator for Convolution-Transformer Hybrid EfficientViT | high | cpu_fpga_fallback:high;overlay:medium;dataflow:medium | transformer;attention;token;inference |
| 2409.00661v1 | Research on LLM Acceleration Using the High-Performance RISC-V Processor "Xiangshan" (Nanhu Version) Based on the Open-Source Matrix Instruction Set Extension (Vector Dot Product) | high | cpu_fpga_fallback:high;overlay:medium;dataflow:medium |  llm;large language model;transformer;attention;gpt;token;inference |
| 2511.13676v1 | T-SAR: A Full-Stack Co-design for CPU-Only Ternary LLM Inference via In-Place SIMD ALU Reorganization | high | cpu_fpga_fallback:high;overlay:medium;dataflow:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2301.01454v1 | Accurate, Low-latency, Efficient SAR Automatic Target Recognition on FPGA | high | cpu_fpga_fallback:high;overlay:medium;hls:medium | transformer;attention;inference |
| 2402.09709v1 | ME-ViT: A Single-Load Memory-Efficient FPGA Accelerator for Vision Transformers | high | cpu_fpga_fallback:high;overlay:medium;hls:medium | large language model;transformer;attention;token;inference |
| 2601.06065v1 | Enabling Long FFT Convolutions on Memory-Constrained FPGAs via Chunking | high | cpu_fpga_fallback:high;overlay:medium;hls:medium | transformer;attention |
| 2109.14704v1 | Accelerating Encrypted Computing on Intel GPUs | high | cpu_fpga_fallback:high;overlay:medium;mlir_circt:low | decode;inference |
| 2311.12359v3 | Shedding the Bits: Pushing the Boundaries of Quantization with Minifloats on FPGAs | high | cpu_fpga_fallback:high;overlay:medium;mlir_circt:low | large language model;transformer;gpt;inference |
| 2408.00462v1 | Designing Efficient LLM Accelerators for Edge Devices | high | cpu_fpga_fallback:high;overlay:medium;param_rtl:low |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2209.09570v1 | Adaptable Butterfly Accelerator for Attention-based NNs via Hardware and Algorithm Co-design | high | cpu_fpga_fallback:high;param_rtl:high;dataflow:high | transformer;attention;gpt;token;autoregressive;decode;inference |
| 2605.19399v1 | HSCO-Bench: An Agent-Driven End-to-End Hardware-Software Co-design Benchmark for Systems-on-Chip | high | cpu_fpga_fallback:high;param_rtl:high;dataflow:high |  llm;large language model;transformer;gpt;inference |
| 2510.24738v2 | StrikeWatch: Wrist-worn Gait Recognition with Compact Time-series Models on Low-power FPGAs | high | cpu_fpga_fallback:high;param_rtl:high;dataflow:low | transformer;attention;inference |
| 2408.06810v1 | HLSPilot: LLM-based High-Level Synthesis | high | cpu_fpga_fallback:high;param_rtl:high;hls:high |  llm;large language model;attention;gpt;decode |
| 2411.18148v5 | A Runtime-Adaptive Transformer Neural Network Accelerator on FPGAs | high | cpu_fpga_fallback:high;param_rtl:high;hls:high | large language model;transformer;attention;token;decode;inference |
| 2502.02404v1 | FPGA Innovation Research in the Netherlands: Present Landscape and Future Outlook | high | cpu_fpga_fallback:high;param_rtl:high;hls:high | attention;decode;inference |
| 2504.14641v3 | HLSTester: Efficient Testing of Behavioral Discrepancies with LLMs for High-Level Synthesis | high | cpu_fpga_fallback:high;param_rtl:high;hls:high |  llm;large language model;transformer;attention;gpt |
| 2508.15468v2 | JEDI-linear: Fast and Efficient Graph Neural Networks for Jet Tagging on FPGAs | high | cpu_fpga_fallback:high;param_rtl:high;hls:high |  llm;transformer;inference |
| 2109.02484v1 | Compiler-Driven FPGA Virtualization with SYNERGY | high | cpu_fpga_fallback:high;param_rtl:high;overlay:high | attention;decode;inference |
| 2304.02510v1 | FPGA-Patch: Mitigating Remote Side-Channel Attacks on FPGAs using Dynamic Patch Generation | high | cpu_fpga_fallback:high;param_rtl:low | attention |
| 2502.13705v2 | Millimeter-Wave Communication Testbed Using Digital Coding Dynamic Metasurface Antenna: Practical Design and Implementation | high | cpu_fpga_fallback:high;param_rtl:low | attention;decode |
| 2601.19413v1 | NET4EXA: Pioneering the Future of Interconnects for Supercomputing and AI | high | cpu_fpga_fallback:high;param_rtl:low | large language model |
| 2606.27350v3 | CHIA: An open-source framework for principled, agentic AI-driven hardware/software co-design research | high | cpu_fpga_fallback:high;param_rtl:low |  llm |
| 2407.05521v1 | Accelerating MRI Uncertainty Estimation with Mask-based Bayesian Neural Network | high | cpu_fpga_fallback:high;param_rtl:low;dataflow:low | attention;inference |
| 2507.11549v2 | A Memory-Efficient Framework for Deformable Transformer with Neural Architecture Search | high | cpu_fpga_fallback:high;param_rtl:low;dataflow:low | transformer;attention;gpt;token;inference |
| 2606.16440v1 | NeuronFabric: A Software Reference Architecture for On-Chip Transformer Training with Local Adam | high | cpu_fpga_fallback:high;param_rtl:low;dataflow:low |  llm;large language model;transformer;attention;gpt;token;autoregressive;inference |
| 2311.12449v1 | HPCNeuroNet: Advancing Neuromorphic Audio Signal Processing with Transformer-Enhanced Spiking Neural Networks | high | cpu_fpga_fallback:high;param_rtl:low;mlir_circt:low | transformer;attention;gpt;decode;inference |
| 2504.17929v2 | ApproXAI: Energy-Efficient Hardware Acceleration of Explainable AI using Approximate Computing | high | cpu_fpga_fallback:high;param_rtl:low;mlir_circt:low | inference |
| 2508.10370v1 | eMamba: Efficient Acceleration Framework for Mamba Models in Edge Computing | high | cpu_fpga_fallback:high;param_rtl:low;mlir_circt:low |  llm;large language model;transformer;attention;token;inference |
| 2606.15045v1 | NEURON-Fabric: CXL-Side Low-Bit Gradient Aggregation for Distributed Training | high | cpu_fpga_fallback:high;param_rtl:low;mlir_circt:low |  llm;large language model;transformer;gpt;decode |
| 2607.07597v1 | Quantum Software Engineering in Practice: FPGA and AI Integration for Quantum Certification | high | cpu_fpga_fallback:high;param_rtl:medium |  llm;large language model;gpt;token |
| 1406.1918v1 | Front-End Board with Cyclone V as a Test High-Resolution Platform for the Auger-Beyond-2015 Front End Electronics | high | cpu_fpga_fallback:high;param_rtl:medium;dataflow:low | transformer |
| 2605.05170v1 | Design Conductor 2.0: An agent builds a TurboQuant inference accelerator in 80 hours | high | cpu_fpga_fallback:high;param_rtl:medium;dataflow:low |  llm;large language model;attention;kv cache;token;autoregressive;decode;inference |
| 1404.3877v1 | Design space exploration for image processing architectures on FPGA targets | high | cpu_fpga_fallback:high;param_rtl:medium;dataflow:medium | decode |
| 2201.10114v2 | PowerGear: Early-Stage Power Estimation in FPGA HLS via Heterogeneous Edge-Centric GNNs | high | cpu_fpga_fallback:high;param_rtl:medium;hls:medium | attention;inference |
| 2405.11353v1 | NTTSuite: Number Theoretic Transform Benchmarks for Accelerating Encrypted Computation | high | cpu_fpga_fallback:high;param_rtl:medium;hls:medium | inference |
| 2504.01806v2 | Quattro: Transformer-Accelerated Iterative Linear Quadratic Regulator Framework for Fast Trajectory Optimization | high | cpu_fpga_fallback:high;param_rtl:medium;hls:medium |  llm;transformer;attention;decode;inference |
| 2510.21745v1 | Simopt-Power: Leveraging Simulation Metadata for Low-Power Design Synthesis | high | cpu_fpga_fallback:high;param_rtl:medium;hls:medium | large language model;attention |
| 2007.11434v3 | A Deep Learning-Based FPGA Function Block Detection Method with Bitstream to Image Transformation | high | cpu_fpga_fallback:high;param_rtl:medium;mlir_circt:low | inference |
| 2407.11041v6 | Integer-only Quantized Transformers for Embedded FPGA-based Time-series Forecasting in AIoT | high | cpu_fpga_fallback:high;param_rtl:medium;mlir_circt:low | transformer;attention;inference |
| 2405.01775v2 | Torch2Chip: An End-to-end Customizable Deep Neural Network Compression and Deployment Toolkit for Prototype Hardware Accelerator Design | high | cpu_fpga_fallback:high;param_rtl:medium;overlay:low | large language model;transformer;attention;inference |
| 2509.24425v1 | BiHDTrans: binary hyperdimensional transformer for efficient multivariate time series classification | high | dataflow:high;cpu_fpga_fallback:high |  llm;transformer;attention;token;decode;inference |
| 1809.07683v1 | AutoAccel: Automated Accelerator Generation and Optimization with Composable, Parallel and Pipeline Architecture | high | dataflow:high;cpu_fpga_fallback:high;hls:high | attention |
| 1902.10345v3 | Stateful Dataflow Multigraphs: A Data-Centric Model for Performance Portability on Heterogeneous Architectures | high | dataflow:high;cpu_fpga_fallback:high;hls:high | inference |
| 2312.15159v2 | Understanding the Potential of FPGA-Based Spatial Acceleration for Large Language Model Inference | high | dataflow:high;cpu_fpga_fallback:high;hls:high |  llm;large language model;transformer;attention;gpt;kv cache;token;autoregressive;prefill;decode;inference |
| 2511.08135v1 | UniFormer: Unified and Efficient Transformer for Reasoning Across General and Custom Computing | high | dataflow:high;cpu_fpga_fallback:high;hls:high |  llm;large language model;transformer;attention;token |
| 2405.17025v1 | SWAT: Scalable and Efficient Window Attention-based Transformers Acceleration on FPGAs | high | dataflow:high;cpu_fpga_fallback:high;hls:medium | transformer;attention;token;inference |
| 2501.06663v2 | Ultra Memory-Efficient On-FPGA Training of Transformers via Tensor-Compressed Optimization | high | dataflow:high;cpu_fpga_fallback:high;hls:medium |  llm;large language model;transformer;attention;token;decode;inference |
| 2502.15260v2 | LightMamba: Efficient Mamba Acceleration on FPGA with Quantization and Hardware Co-design | high | dataflow:high;cpu_fpga_fallback:high;hls:medium |  llm;large language model;transformer;attention;gpt;token;autoregressive;prefill;decode;inference |
| 2508.10303v1 | DiffAxE: Diffusion-driven Hardware Accelerator Generation and Design Space Exploration | high | dataflow:high;cpu_fpga_fallback:high;hls:medium |  llm;large language model;transformer;attention;gpt;token;prefill;decode;inference |
| 2511.06174v2 | LUT-LLM: Efficient Large Language Model Inference with Memory-based Computations on FPGAs | high | dataflow:high;cpu_fpga_fallback:high;hls:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2512.23914v3 | Hardware Acceleration for Neural Networks: A Comprehensive Survey | high | dataflow:high;cpu_fpga_fallback:high;hls:medium |  llm;large language model;transformer;attention;gpt;token;autoregressive;prefill;decode;inference |
| 1902.07463v2 | DNNVM : End-to-End Compiler Leveraging Heterogeneous Optimizations on FPGA-based CNN Accelerators | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:high | transformer;attention;inference |
| 2601.09217v2 | Relational Hoare Logic for High-Level Synthesis of Hardware Accelerators | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:high | attention |
| 1511.05552v4 | Recurrent Neural Networks Hardware Implementation on FPGA | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:low | decode |
| 1711.08740v1 | fpgaConvNet: A Toolflow for Mapping Diverse Convolutional Neural Networks on Embedded FPGAs | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:low | inference |
| 2501.19135v1 | A Tensor-Train Decomposition based Compression of LLMs on Group Vector Systolic Accelerator | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:low |  llm;large language model;transformer;attention;kv cache;token;autoregressive;decode;inference |
| 2510.03516v3 | COMET: Co-Optimization of a CNN Model using Efficient-Hardware OBC Techniques | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:low | attention;inference |
| 2510.24985v1 | FaRAccel: FPGA-Accelerated Defense Architecture for Efficient Bit-Flip Attack Resilience in Transformer Models | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:low |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2601.02135v1 | HFRWKV: A High-Performance Fully On-Chip Hardware Accelerator for RWKV | high | dataflow:high;cpu_fpga_fallback:high;mlir_circt:low |  llm;large language model;transformer;attention;token;decode;inference |
| 2511.15505v1 | Instruction-Based Coordination of Heterogeneous Processing Units for Acceleration of DNN Inference | high | dataflow:high;cpu_fpga_fallback:high;overlay:high | transformer;attention;token;decode;inference |
| 2604.04694v1 | Mestra: Exploring Migration on Virtualized CGRAs | high | dataflow:high;cpu_fpga_fallback:high;overlay:low |  llm;attention;token |
| 2604.21290v1 | GraphLeap: Decoupling Graph Construction and Convolution for Vision GNN Acceleration on FPGA | high | dataflow:high;cpu_fpga_fallback:high;overlay:low | transformer;attention;token;inference |
| 2504.09561v1 | LoopLynx: A Scalable Dataflow Architecture for Efficient LLM Inference | high | dataflow:high;cpu_fpga_fallback:high;overlay:medium |  llm;large language model;transformer;attention;gpt;kv cache;token;prefill;decode;inference |
| 2505.12771v1 | FireFly-T: High-Throughput Sparsity Exploitation for Spiking Transformer Acceleration with Dual-Engine Overlay Architecture | high | dataflow:high;cpu_fpga_fallback:high;overlay:medium | transformer;attention;token;decode;inference |
| 2507.20420v1 | Demystifying the 7-D Convolution Loop Nest for Data and Instruction Streaming in Reconfigurable AI Accelerators | high | dataflow:high;cpu_fpga_fallback:high;overlay:medium | inference |
| 2605.06052v1 | XtraMAC: An Efficient MAC Architecture for Mixed-Precision LLM Inference on FPGA | high | dataflow:high;cpu_fpga_fallback:high;overlay:medium |  llm;large language model;transformer;attention;gpt;token;decode;inference |
| 2208.06118v1 | An Algorithm-Hardware Co-Optimized Framework for Accelerating N:M Sparse Transformers | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:high | transformer;attention;token;decode;inference |
| 2510.22243v1 | Real-Time Semantic Segmentation on FPGA for Autonomous Vehicles Using LMIINet with the CGRA4ML Framework | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:high | transformer;attention;decode;inference |
| 2605.01935v1 | ViM-Q: Scalable Algorithm-Hardware Co-Design for Vision Mamba Model Inference on FPGA | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:high |  llm;transformer;attention;token;inference |
| 2303.12901v1 | Dynasparse: Accelerating GNN Inference through Dynamic Sparsity Exploitation | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:low | inference |
| 2411.03697v1 | TATAA: Programmable Mixed-Precision Transformer Acceleration with a Transformable Arithmetic Architecture | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:low | large language model;transformer;attention;gpt;token;decode;inference |
| 2505.08992v3 | Dataflow & Tiling Strategies in Edge-AI FPGA Accelerators: A Comprehensive Literature Review | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:low | large language model;transformer;token;inference |
| 2104.12339v1 | TensorLib: A Spatial Accelerator Generation Framework for Tensor Algebra | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:medium | inference |
| 2512.15515v1 | FAME: FPGA Acceleration of Secure Matrix Multiplication with Homomorphic Encryption | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:medium | inference |
| 2607.15123v1 | NIFA: Nonlinear IMC enhanced FPGA for efficient ML inference | high | dataflow:high;cpu_fpga_fallback:high;param_rtl:medium |  llm;transformer;attention;inference |
| 2507.04315v3 | HLStrans: Dataset for C-to-HLS Hardware Code Synthesis | high | dataflow:high;hls:high;cpu_fpga_fallback:high |  llm;large language model;gpt;token |
| 2305.19896v1 | fpgaHART: A toolflow for throughput-oriented acceleration of 3D CNNs for HAR onto FPGAs | high | dataflow:high;hls:medium;cpu_fpga_fallback:medium | transformer;attention;inference |
| 2409.14023v3 | FAMOUS: Flexible Accelerator for the Attention Mechanism of Transformer on UltraScale+ FPGAs | high | dataflow:high;hls:medium;cpu_fpga_fallback:medium | transformer;attention;inference |
| 2010.07746v1 | Real-Time Refocusing using an FPGA-based Standard Plenoptic Camera | high | dataflow:high;param_rtl:medium;cpu_fpga_fallback:medium | attention;decode |
| 2510.24784v1 | Sub-microsecond Transformers for Jet Tagging on FPGAs | high | hls:high;cpu_fpga_fallback:high | transformer;attention |
| 2112.07789v1 | FLOWER: A comprehensive dataflow compiler for high-level synthesis | high | hls:high;cpu_fpga_fallback:high;dataflow:high | inference |
| 2503.02891v3 | Vision Transformers on the Edge: A Comprehensive Survey of Model Compression and Acceleration Strategies | high | hls:high;cpu_fpga_fallback:high;dataflow:high | transformer;attention;token;decode;inference |
| 1803.09004v1 | Face Recognition with Hybrid Efficient Convolution Algorithms on FPGAs | high | hls:high;cpu_fpga_fallback:high;dataflow:low | inference |
| 2406.14593v2 | Enhancing Dropout-based Bayesian Neural Networks with Multi-Exit on FPGA | high | hls:high;cpu_fpga_fallback:high;dataflow:medium | attention;decode;inference |
| 2409.05207v1 | Low Latency Transformer Inference on FPGAs for Physics Applications with hls4ml | high | hls:high;cpu_fpga_fallback:high;dataflow:medium | transformer;attention;inference |
| 2601.17215v1 | JetFormer: A Scalable and Efficient Transformer for Jet Tagging from Offline Analysis to FPGA Triggers | high | hls:high;cpu_fpga_fallback:high;mlir_circt:medium | transformer;attention;token;inference |
| 2405.19948v1 | Scalable Test Generation to Trigger Rare Targets in High-Level Synthesizable IPs for Cloud FPGAs | high | hls:high;cpu_fpga_fallback:high;param_rtl:high | attention |
| 2306.08746v1 | MetaML: Automating Customizable Cross-Stage Design-Flow for Deep Learning Acceleration | high | hls:high;cpu_fpga_fallback:high;param_rtl:low | attention;inference |
| 2308.06849v1 | When Monte-Carlo Dropout Meets Multi-Exit: Optimizing Bayesian Neural Networks on FPGA | high | hls:high;cpu_fpga_fallback:high;param_rtl:low | attention;decode;inference |
| 2501.12003v1 | Broadband, Dead-Time-Free Spectrometer Using RFSoC for WISP Dark Matter Searches | high | hls:high;cpu_fpga_fallback:high;param_rtl:low | attention |
| 2103.02800v1 | Hardware Acceleration of Fully Quantized BERT for Efficient Natural Language Processing | high | hls:high;cpu_fpga_fallback:high;param_rtl:medium | transformer;attention;decode;inference |
| 2201.11522v2 | High-level Synthesis using the Julia Language | high | hls:high;cpu_fpga_fallback:high;param_rtl:medium | inference |
| 2508.11594v2 | It's not a FAD: first results in using Flows for unsupervised Anomaly Detection at 40 MHz at the Large Hadron Collider | high | hls:high;cpu_fpga_fallback:high;param_rtl:medium | inference |
| 2511.05615v1 | wa-hls4ml: A Benchmark and Surrogate Models for hls4ml Resource and Latency Estimation | high | hls:high;cpu_fpga_fallback:high;param_rtl:medium |  llm;transformer;attention;token;inference |
| 2310.01906v1 | Implementation of hyperspectral inversion algorithms on FPGA: Hardware comparison using High Level Synthesis | high | hls:high;cpu_fpga_fallback:medium;param_rtl:low | attention |
| 2412.17571v1 | HPCNeuroNet: A Neuromorphic Approach Merging SNN Temporal Dynamics with Transformer Attention for FPGA-based Particle Physics | high | hls:high;cpu_fpga_fallback:medium;param_rtl:low | transformer;attention;gpt;decode;inference |
| 2308.05930v1 | INR-Arch: A Dataflow Architecture and Compiler for Arbitrary-Order Gradient Computations in Implicit Neural Representation Processing | high | hls:high;dataflow:high;cpu_fpga_fallback:high | decode;inference |
| 2605.05920v1 | LLM-Driven Design Space Exploration of FPGA-based Accelerators | high | hls:high;dataflow:high;cpu_fpga_fallback:high |  llm;large language model;token;inference |
| 2606.07246v1 | MailoHLS: Multi-Adapter Structure-Aware Learning for Pareto-Driven HLS Pragma Optimization | high | hls:high;dataflow:high;cpu_fpga_fallback:high |  llm;large language model;transformer;attention;gpt;token;autoregressive;decode;inference |
| 2602.06085v1 | LAAFD: LLM-based Agents for Accelerated FPGA Design | high | hls:high;dataflow:high;param_rtl:high |  llm;large language model;gpt;token;inference |
| 1606.06451v1 | High Level Synthesis with a Dataflow Architectural Template | high | hls:high;dataflow:high;param_rtl:medium | token |
| 2504.21187v1 | LIFT: LLM-Based Pragma Insertion for HLS via GNN Supervised Fine-Tuning | high | hls:high;mlir_circt:high;param_rtl:medium |  llm;large language model;transformer;attention;gpt;token;autoregressive;inference |
| 2402.01047v1 | Ultra Fast Transformers on FPGAs for Particle Physics Experiments | high | hls:high;mlir_circt:low;dataflow:low | transformer;attention;gpt;decode;inference |
| 2509.26335v2 | TrackCore-F: Deploying Transformer-Based Subatomic Particle Tracking on FPGAs | high | hls:high;mlir_circt:low;dataflow:low | transformer;attention;inference |
| 2202.04976v2 | Fast Muon Tracking with Machine Learning Implemented in FPGA | high | hls:high;mlir_circt:medium;cpu_fpga_fallback:medium | inference |
| 2405.00738v1 | HLSTransform: Energy-Efficient Llama 2 Inference on FPGAs Via High Level Synthesis | high | hls:high;param_rtl:high;cpu_fpga_fallback:high |  llm;large language model;transformer;attention;gpt;token;inference |
| 2411.11384v1 | SILVIA: Automated Superword-Level Parallelism Exploitation via HLS-Specific LLVM Passes for Compute-Intensive FPGA Accelerators | high | hls:high;param_rtl:high;cpu_fpga_fallback:high | attention;inference |
| 2507.17962v1 | TimelyHLS: LLM-Based Timing-Aware and Architecture-Specific FPGA HLS Optimization | high | hls:high;param_rtl:high;cpu_fpga_fallback:medium |  llm;large language model;gpt;decode;inference |
| 2501.13379v2 | A Quantitative Evaluation of Approximate Softmax Functions for Deep Neural Networks | high | hls:high;param_rtl:medium;cpu_fpga_fallback:low |  llm;large language model;inference |
| 2501.04845v1 | Intelligent experiments through real-time AI: Fast Data Processing and Autonomous Detector Control for sPHENIX and future EIC detectors | high | hls:high;param_rtl:medium;dataflow:medium | transformer;attention |
| 2501.09118v1 | Stream-HLS: Towards Automatic Dataflow Acceleration | high | mlir_circt:high;cpu_fpga_fallback:high;hls:high | transformer;attention;decode;inference |
| 2607.07643v1 | ATLAS: Automated HLS for DL-Optimized FPGAs | high | mlir_circt:high;hls:high;dataflow:high | transformer;attention;inference |
| 2509.01149v1 | Compiler Bugs Detection in Logic Synthesis Tools via Linear Upper Confidence Bound | high | param_rtl:high;cpu_fpga_fallback:high;dataflow:low |  llm;large language model |
| 2305.12824v1 | FieldHAR: A Fully Integrated End-to-end RTL Framework for Human Activity Recognition with Neural Networks from Heterogeneous Sensors | high | param_rtl:high;cpu_fpga_fallback:high;dataflow:medium | attention;inference |
| 2302.02959v1 | Rule-based High-level Hardware-RTL Synthesis of Algorithms, Virtualizing Machines, and Communication Protocols with FPGAs based on Concurrent Communicating Sequential Processes and the ConPro Synthesis Framework | high | param_rtl:high;cpu_fpga_fallback:high;hls:high | decode;inference |
| 2602.09410v1 | Accelerating Post-Quantum Cryptography via LLM-Driven Hardware-Software Co-Design | high | param_rtl:high;cpu_fpga_fallback:high;hls:high |  llm;large language model;gpt;token |
| 2405.01419v3 | Natural Language to Verilog: Design of a Recurrent Spiking Neural Network using Large Language Models and ChatGPT | high | param_rtl:high;cpu_fpga_fallback:high;mlir_circt:low |  llm;large language model;gpt;inference |
| 2604.19856v1 | ChipCraftBrain: Validation-First RTL Generation via Multi-Agent Orchestration | high | param_rtl:high;cpu_fpga_fallback:high;mlir_circt:medium |  llm;large language model;attention;gpt;token;autoregressive;decode;inference |
| 2404.07235v2 | LLM-aided explanations of EDA synthesis errors | high | param_rtl:high;cpu_fpga_fallback:low |  llm;large language model;transformer;attention;gpt |
| 2503.01138v1 | A Novel Interactive-Guided Differential Testing Approach for FPGA Simulation Debugger Tools | high | param_rtl:high;cpu_fpga_fallback:medium | attention |
| 1907.07764v1 | HTCC: Haskell to Handel-C Compiler | high | param_rtl:high;cpu_fpga_fallback:medium;hls:low | token;decode |
| 2307.07319v5 | The Power of Large Language Models for Wireless Communication System Development: A Case Study on FPGA Platforms | high | param_rtl:high;cpu_fpga_fallback:medium;hls:low |  llm;large language model;transformer;attention;gpt;token;inference |
| 2505.17662v5 | Automating Versatile Time-Series Analysis with Tiny Transformers on Embedded FPGAs | high | param_rtl:high;cpu_fpga_fallback:medium;overlay:low | transformer;attention;inference |
| 2512.00016v1 | Architect in the Loop Agentic Hardware Design and Verification | high | param_rtl:high;cpu_fpga_fallback:medium;overlay:low |  llm;large language model;attention;gpt;token;inference |
| 1705.04543v3 | Hardware Automated Dataflow Deployment of CNNs | high | param_rtl:high;dataflow:high;cpu_fpga_fallback:high | token;inference |
| 1903.03509v1 | OpenCL-based FPGA accelerator for disparity map generation with stereoscopic event cameras | high | param_rtl:high;dataflow:high;cpu_fpga_fallback:high | inference |
| 2511.00812v1 | LL-ViT: Edge Deployable Vision Transformers with Look Up Table Neurons | high | param_rtl:high;dataflow:high;cpu_fpga_fallback:high | transformer;attention;token;inference |
| 2512.14762v1 | Workflows vs Agents for Code Translation | high | param_rtl:high;dataflow:high;cpu_fpga_fallback:medium |  llm;large language model;attention;token;inference |
| 1501.02995v1 | Improved 8-point Approximate DCT for Image and Video Compression Requiring Only 14 Additions | high | param_rtl:high;dataflow:low;cpu_fpga_fallback:low | attention |
| 1712.04322v1 | Tactics to Directly Map CNN graphs on Embedded FPGAs | high | param_rtl:high;dataflow:medium;cpu_fpga_fallback:low | inference |
| 2508.08709v1 | CRADLE: Conversational RTL Design Space Exploration with LLM-based Multi-Agent Systems | high | param_rtl:high;dataflow:medium;cpu_fpga_fallback:low |  llm;large language model;gpt |
| 2603.12637v1 | ExpanderGraph-128: A Novel Graph-Theoretic Block Cipher with Formal Security Analysis and Hardware Implementation | high | param_rtl:high;dataflow:medium;cpu_fpga_fallback:medium | token |
| 2501.01511v1 | TreeLUT: An Efficient Alternative to Deep Neural Networks for Inference Acceleration Using Gradient Boosted Decision Trees | high | param_rtl:high;hls:high;cpu_fpga_fallback:high | inference |
| 2502.05850v3 | MetaML-Pro: Cross-Stage Design Flow Automation for Efficient Deep Learning Acceleration | high | param_rtl:high;hls:high;cpu_fpga_fallback:high | large language model;transformer;attention;inference |
| 2604.17097v1 | From Natural Language to Silicon: The Representation Bottleneck in LLM Hardware Design | high | param_rtl:high;hls:high;cpu_fpga_fallback:medium |  llm;large language model;gpt |
| 1907.07929v5 | FBLAS: Streaming Linear Algebra on FPGA | high | param_rtl:high;hls:high;dataflow:high | attention |
| 2508.10904v3 | A2H-MAS: An Algorithm-to-HLS Multi-Agent System for Automated and Reliable FPGA Implementation | high | param_rtl:high;hls:high;dataflow:high |  llm;large language model;attention;gpt |
| 2511.15323v1 | SkyEgg: Joint Implementation Selection and Scheduling for Hardware Synthesis using E-graphs | high | param_rtl:high;hls:high;dataflow:high | inference |
| 2606.11117v1 | Towards Autonomous Accelerator Design: FPGA Accelerator Generation with SECDA | high | param_rtl:high;hls:high;dataflow:high |  llm;large language model;gpt;inference |
| 2601.15151v1 | Pipeline Automation Framework for Reusable High-throughput Network Applications on FPGA | high | param_rtl:high;hls:high;dataflow:medium | inference |
| 2601.14098v1 | A flexible language model-assisted electronic design automation framework | high | param_rtl:high;hls:low;dataflow:low |  llm;large language model;gpt;token |
| 2305.15999v1 | An Overview of FPGA-inspired Obfuscation Techniques | high | param_rtl:high;hls:medium;cpu_fpga_fallback:medium | attention |
| 2503.08823v2 | ResBench: Benchmarking LLM-Generated FPGA Designs with Resource Awareness | high | param_rtl:high;hls:medium;cpu_fpga_fallback:medium |  llm;large language model;transformer;attention;gpt |
| 2305.10838v2 | ProgSG: Cross-Modality Representation Learning for Programs in Electronic Design Automation | high | param_rtl:high;hls:medium;overlay:low | large language model;token |
| 2410.13079v1 | RapidStream IR: Infrastructure for FPGA High-Level Physical Synthesis | high | param_rtl:high;mlir_circt:high;hls:high |  llm;large language model;inference |
| 1309.7843v3 | Energy Efficient Telemonitoring of Physiological Signals via Compressed Sensing: A Fast Algorithm and Power Consumption Evaluation | medium | cpu_fpga_fallback:medium | autoregressive |
| 1609.07750v1 | Accurate and Efficient Hyperbolic Tangent Activation Function on FPGA using the DCT Interpolation Filter | medium | cpu_fpga_fallback:medium | decode |
| 1803.00521v2 | Segmented Successive Cancellation List Polar Decoding with Tailored CRC | medium | cpu_fpga_fallback:medium | decode |
| 2104.00252v1 | Observational demonstration of a low-cost fast Fourier transform spectrometer with a delay-line-based ramp-compare ADC implemented on FPGA | medium | cpu_fpga_fallback:medium | decode |
| 2311.12082v2 | Tiny-VBF: Resource-Efficient Vision Transformer based Lightweight Beamformer for Ultrasound Single-Angle Plane Wave Imaging | medium | cpu_fpga_fallback:medium | transformer;attention;decode;inference |
| 2509.17355v1 | CMOS Implementation of Field Programmable Spiking Neural Network for Hardware Reservoir Computing | medium | cpu_fpga_fallback:medium |  llm;large language model;transformer;gpt;inference |
| 1706.08863v1 | OCTAD-S: Digital Fast Fourier Transform Spectrometers by FPGA | medium | cpu_fpga_fallback:medium;dataflow:low | decode |
| 2502.07796v1 | Enhancing Olfactory Perception Through Large Language Models: Integrating Sensory Data for Advanced Odor Recognition | medium | cpu_fpga_fallback:medium;dataflow:low | large language model;attention |
| 2505.06578v1 | Compact and Efficient Neural Networks for Image Recognition Based on Learned 2D Separable Transform | medium | cpu_fpga_fallback:medium;dataflow:low | inference |
| 2505.20250v2 | Efficient Optimization Accelerator Framework for Multistate Ising Problems | medium | cpu_fpga_fallback:medium;mlir_circt:low | attention |
| 2011.05670v1 | FPGA: Fast Patch-Free Global Learning Framework for Fully End-to-End Hyperspectral Image Classification | medium | cpu_fpga_fallback:medium;mlir_circt:low;dataflow:low | attention;decode;inference |
| 2112.13890v2 | SPViT: Enabling Faster Vision Transformers via Soft Token Pruning | medium | cpu_fpga_fallback:medium;mlir_circt:low;dataflow:low | transformer;attention;token;inference |
| 2410.23083v1 | Developing a Self-Explanatory Transformer | medium | cpu_fpga_fallback:medium;overlay:low;dataflow:low | transformer |
| 2009.08605v1 | Hardware Accelerator for Multi-Head Attention and Position-Wise Feed-Forward in the Transformer | medium | cpu_fpga_fallback:medium;param_rtl:low;mlir_circt:low | transformer;attention;decode;inference |
| 1712.03411v1 | FPGA with Improved Routability and Robustness in 130nm CMOS with Open-Source CAD Targetability | medium | cpu_fpga_fallback:medium;param_rtl:low;overlay:low | decode |
| 1504.05372v1 | Inferring Program Transformations from Type Transformations for Partitioning of Ordered Sets | medium | dataflow:medium;cpu_fpga_fallback:low | inference |
| 2410.09227v1 | Fast Data-independent KLT Approximations Based on Integer Functions | medium | dataflow:medium;cpu_fpga_fallback:low | decode |
| 2501.11867v1 | A Fully Pipelined FIFO Based Polynomial Multiplication Hardware Architecture Based On Number Theoretic Transform | medium | dataflow:medium;cpu_fpga_fallback:low | attention |
| 1502.04221v1 | A Row-parallel 8$\times$8 2-D DCT Architecture Using Algebraic Integer Based Exact Computation | medium | dataflow:medium;cpu_fpga_fallback:medium | decode |
| 2512.24713v2 | FPGA Co-Design for Efficient N:M Sparse and Quantized Model Inference | medium | dataflow:medium;cpu_fpga_fallback:medium;mlir_circt:low |  llm;large language model;token;inference |
| 1708.08917v1 | CirCNN: Accelerating and Compressing Deep Neural Networks Using Block-CirculantWeight Matrices | medium | dataflow:medium;cpu_fpga_fallback:medium;param_rtl:low | decode;inference |
| 2404.10896v1 | From a Lossless (~1.5:1) Compression Algorithm for Llama2 7B Weights to Variable Precision, Variable Range, Compressed Numeric Data Types for CNNs and LLMs | medium | dataflow:medium;cpu_fpga_fallback:medium;param_rtl:low |  llm;large language model;transformer;attention;kv cache;token;decode;inference |
| 2405.15923v3 | Spiketrum: An FPGA-based Implementation of a Neuromorphic Cochlea | medium | dataflow:medium;cpu_fpga_fallback:medium;param_rtl:low | decode |
| 2410.04805v1 | HF-NTT: Hazard-Free Dataflow Accelerator for Number Theoretic Transform | medium | dataflow:medium;cpu_fpga_fallback:medium;param_rtl:low | attention |
| 2507.14139v1 | SpeedLLM: An FPGA Co-design of Large Language Model Inference Accelerator | medium | dataflow:medium;cpu_fpga_fallback:medium;param_rtl:low |  llm;large language model;gpt;token;decode;inference |
| 2607.01798v2 | Approximate Attention Weighting for Sustainable FPGA-Based Vision Transformer Inference | medium | dataflow:medium;cpu_fpga_fallback:medium;param_rtl:low | transformer;attention;token;inference |
| 1710.11200v1 | VLSI Computational Architectures for the Arithmetic Cosine Transform | medium | dataflow:medium;param_rtl:low;cpu_fpga_fallback:low |  llm;attention |
| 2605.17222v1 | Triple-Hoisted Baby-Step Giant-Step Linear Transformation over CKKS Homomorphic Encryption and Hardware Accelerator | medium | dataflow:medium;param_rtl:low;cpu_fpga_fallback:low | large language model;transformer;inference |
| 2605.19199v2 | Discrete Wavelet Transform for Serial X-ray Crystallography Image Segmentation | medium | hls:medium;cpu_fpga_fallback:medium;dataflow:low | transformer;inference |
| 2607.11585v1 | Machine Learning-Based Reconstruction for Resistive Silicon Sensors | medium | hls:medium;cpu_fpga_fallback:medium;mlir_circt:low | transformer;attention;token |
| 2603.03075v1 | TinyIceNet: Low-Power SAR Sea Ice Segmentation for On-Board FPGA Inference | medium | hls:medium;dataflow:medium;cpu_fpga_fallback:medium | attention;decode;inference |
| 2310.02654v1 | A Study of Quantisation-aware Training on Time Series Transformer Models for Resource-constrained FPGAs | medium | mlir_circt:medium | transformer;attention;inference |
| 2108.00874v2 | Few-Shot Domain Adaptation For End-to-End Communication | medium | mlir_circt:medium;cpu_fpga_fallback:low | decode |
| 1905.10830v3 | Feature Map Transform Coding for Energy-Efficient CNN Inference | medium | mlir_circt:medium;cpu_fpga_fallback:medium | attention;decode;inference |
| 2303.13601v1 | Scaled Quantization for the Vision Transformer | medium | mlir_circt:medium;cpu_fpga_fallback:medium | transformer;attention;token;inference |
| 1609.07630v4 | Low-complexity Image and Video Coding Based on an Approximate Discrete Tchebichef Transform | medium | mlir_circt:medium;dataflow:low;cpu_fpga_fallback:low | decode |
| 2603.14785v2 | SkipOPU: An FPGA-based Overlay Processor for Large Language Models with Dynamically Allocated Computation | medium | overlay:medium;cpu_fpga_fallback:low |  llm;large language model;token;inference |
| 2402.14307v1 | An FPGA-Based Accelerator Enabling Efficient Support for CNNs with Arbitrary Kernel Sizes | medium | overlay:medium;dataflow:medium;cpu_fpga_fallback:medium | transformer;attention;inference |
| 1607.04663v1 | Inter-Technology Backscatter: Towards Internet Connectivity for Implanted Devices | medium | param_rtl:medium;cpu_fpga_fallback:low | decode |
| 2508.13905v2 | Automated Energy-Aware Time-Series Model Deployment on Embedded FPGAs for Resilient Combined Sewer Overflow Management | medium | param_rtl:medium;cpu_fpga_fallback:medium;dataflow:low | transformer;attention;inference |
| 1203.3972v1 | High-resolution wide-band Fast Fourier Transform spectrometers | medium | param_rtl:medium;dataflow:low;cpu_fpga_fallback:low | decode |
| 1801.06541v1 | HGum: Messaging Framework for Hardware Accelerators | medium | param_rtl:medium;dataflow:medium;cpu_fpga_fallback:medium | token;decode |
| 2407.12736v4 | CHOSEN: Compilation to Hardware Optimization Stack for Efficient Vision Transformer Inference | medium | param_rtl:medium;dataflow:medium;cpu_fpga_fallback:medium | transformer;attention;token;inference |
| 1008.1673v2 | Space and the Synchronic A-Ram | medium | param_rtl:medium;dataflow:medium;overlay:low | token |
| 2403.01215v2 | Efficient Algorithm Level Error Detection for Number-Theoretic Transform used for Kyber Assessed on FPGAs and ARM | medium | param_rtl:medium;hls:medium;cpu_fpga_fallback:medium | decode |
| 2507.10912v1 | Mapping Fusion: Improving FPGA Technology Mapping with ASIC Mapper | medium | param_rtl:medium;hls:medium;cpu_fpga_fallback:medium | attention |
| 1411.0863v1 | Inner Loop Optimizations in Mapping Single Threaded Programs to Hardware | medium | param_rtl:medium;mlir_circt:medium;hls:medium | token |
| 2401.10364v1 | Using LLM such as ChatGPT for Designing and Implementing a RISC Processor: Execution,Challenges and Limitations | medium | param_rtl:medium;overlay:low;cpu_fpga_fallback:low |  llm;large language model;transformer;attention;gpt;token;decode |
