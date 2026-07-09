# Calyx `seq_mem` SV Reproducer

This isolates the Calyx-to-SV blocker reached by small integer-core patterns.
Those patterns can emit Calyx, but `circt-opt --lower-calyx-to-hw` rejects
external `calyx.seq_mem` operations before SystemVerilog export:

```text
'calyx.seq_mem' op couldn't convert to core primitive
```

Acceptable fixes are an official Calyx/CIRCT pass sequence, a packaged native
Calyx compiler route, or an actual MLIR/CIRCT pass with tests. Textual Calyx
MLIR editing is not acceptable.

The related `calyx.memory` reproducer in `reproducers/calyx-memory-sv/` shows
that direct Calyx-to-HW currently rejects both combinational and sequential
Calyx memory primitives.
