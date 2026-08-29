# Small external-memory backend probe

This fixture is deliberately not a reduced TinyStories implementation.  It
checks only the backend plumbing needed before attempting the generated
LayerNorm design: four external `seq_mem_d1(32, 4, 2)` memories, one-cycle
read latency, Verilator hierarchy initialization, and completion through the
top-level `go`/`done` interface.  It computes `out[i] = in[i] + gamma[i] +
beta[i]`.

Run from the repository root (the Calyx package is currently not in the
default development shell):

```sh
calyx=/nix/store/hafr57h6q1q46494z95a83fc9ad6bjlf-calyx-0.7.1/bin/calyx
lib=/nix/store/hafr57h6q1q46494z95a83fc9ad6bjlf-calyx-0.7.1/share/calyx
$calyx reproducers/calyx-layernorm-memory-harness/input.futil \
  -o /tmp/llm2fpga-layernorm-memory-harness.sv -b verilog -l "$lib"
rm -rf /tmp/llm2fpga-layernorm-memory-harness-obj
probe="$PWD/scripts/comparison/probe_small_external_memory.cpp"
nix develop -c verilator --cc /tmp/llm2fpga-layernorm-memory-harness.sv \
  --top-module main --public-flat-rw \
  --exe "$probe" \
  --build -Mdir /tmp/llm2fpga-layernorm-memory-harness-obj -j 8
nix develop -c make -C /tmp/llm2fpga-layernorm-memory-harness-obj \
  -f Vmain.mk Vmain -j8
/tmp/llm2fpga-layernorm-memory-harness-obj/Vmain
```

Observed result on 2026-08-29: `{"status":"ok","done":true,"cycles":16}`.
This result establishes that a small generated Calyx design can be initialized
and executed through Verilator.  It does not establish LayerNorm or
TinyStories equivalence.

## Full generated LayerNorm diagnostic

Icarus can parse and execute the full generated LayerNorm Verilog without the
large Verilator C++ build.  The testbench must hold `go` high until `done`;
the generated top-level currently uses `go` as a level-sensitive invocation
enable.  For diagnosis only, copy the generated Verilog and replace its
time-zero one-hot `$fatal` checks with `$display`, then compile with
`nix shell nixpkgs#iverilog`.  On the authenticated 64-word alternating
±1 vector this reaches `done` with zero output mismatches.  A one-cycle `go`
pulse times out with all external-memory completion signals low.  This is
recorded in `artifacts/comparison/tinystories-1m-layernorm-iverilog-diagnostic.json`;
it is not a production RTL fix or a TinyStories equivalence result.

The direct `main_1` testbench (`main1_external_tb.sv`) models the external
memory service and latches the rising edge of `done`.  It observes 64 output
writes with zero mismatches; `done` is a pulse and is low again when sampled
later.  The result is recorded in
`artifacts/comparison/tinystories-1m-layernorm-main1-iverilog-diagnostic.json`.
