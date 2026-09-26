# RC prefill-8 module-order A/B diagnostic

This is a bounded backend diagnostic for the current compiler-generated RC
prefill-8 closure. It does not change the canonical pipeline or promote a
simulation result.

## Question

The same Futil input has produced native SystemVerilog files with different
HardFloat module ordering. This experiment asks whether that ordering alone
causes the current long-running prefill behavior.

## Method

- Source: the current `vvlf…` native-SV closure, compiled successfully with
  Verilator using one compiler job and `-O0`.
- Transformation: preserve the generated preamble and sort complete top-level
  `module … endmodule` blocks alphabetically. No module body or testbench logic
  was changed.
- Simulator: the existing generated testbench and model-memory files.
- Bound: 120 seconds of wall time.

The reordered source was compiled into `/tmp/rc-prefill8-sorted/`. The
simulation command was:

```text
timeout 120s ./obj_dir/Vtb > simulation-120s.log 2>&1
```

## Result

The run exited with timeout status 124 at exactly 120 seconds. The log was 64
bytes and contained only the `/usr/bin/time` timeout summary. No `out*` result
files or `done` indication were produced.

Therefore, module ordering alone did not remove the observed runtime frontier
within this bound. This is not evidence that ordering is irrelevant to every
tool behavior, but it is insufficient to justify an ordering-only production
fix.

## Consequence

The RC remains unqualified. The next diagnostic must localize the long-running
behavior in the generated control/data path (or compare against the historical
div/sqrt-repaired closure), rather than applying a speculative module-sort
patch. No synthesis, PCIe, DDR3, or board gate is promoted from this result.
