# Task 3 Main Representative-Core Design

## Goal

Run full TinyStories (FTS) and the FP32 representative core (RC) through the
same reproducible Task 3 pipeline, then produce a non-gating utilization
comparison. Timing is neither collected nor judged.

## Reproducibility Boundary

`task3-main/` is a source copy of `/home/roland/LLM2FPGA` commit `b6dc8ab`,
including its `flake.lock`. It owns both builds so the pinned CIRCT, LLVM,
torch-mlir, Yosys, yosys-slang, lowering scripts, RTLIL processing, memory
externalization, and staged Xilinx synthesis are identical for FTS and RC.

The root flake exposes the nested flake's packages as first-class package
attributes. The modern root pipeline is not an input to either Task 3 build.

## RC Adaptation

RC uses the approved minimum shape: vocabulary 32, two layers, hidden size 2,
one attention head, four positions, and local window 2. It uses the copied
Task 3 direct adapter-to-torch-mlir frontend rather than the modern serialized
ExportedProgram frontend.

The old FTS wrapper remains unchanged. RC's wrapper is generated from RC's
Task 3 `main.sv`, preserving the wrapper behavior while adapting only signal
names, widths, and shapes required by that generated module.

## Outputs

The FTS and RC utilization packages each expose only `summary.json`,
`summary.txt`, and `stat.json`. The comparison package emits the parity report
and copies the two input summaries. Threshold results are reported but never
cause the derivation to fail. No timing artifacts are produced.

## Verification

Evaluation must show all three root package attributes. Completion requires a
successful live build of FTS, RC, and the comparison package, followed by
inspection of the report artifacts and their input derivation closures.
