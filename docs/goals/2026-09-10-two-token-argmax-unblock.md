# TinyStories-1M autonomous-generation goal and unblocking scope

## Blocked goal

The blocked goal was to extend the full compiler-generated TinyStories-1M
design from the validated first-token YPCB baseline to autonomous generation
of the frozen 16-token continuation. It preserved the authenticated model and
fixed-point contract, on-chip BRAM/LUTRAM, 30 MHz, and JTAG; excluded DDR3 and
PCIe; required a two-token FPGA checkpoint followed by exact 16-token RTL and
three-run YPCB acceptance; preserved the first-token baseline; and required
fit, covered-path timing, and earliest-mismatch localization before fixes.

The goal was blocked after repeated implementation attempts reached router
iteration 1 with 163,477 overused wires (210,948 total overuse), without a
routed netlist, FASM, or bitstream. Semantic simulation passed. BRAM/DSP
counts matched the first-token design, so the evidence points to the
production streamed-argmax/control interconnect rather than model storage or
arithmetic.

## Unblocking goal

Add and validate a compiler-owned registered argmax boundary for the production
TinyStories-1M two-token path. Preserve the authenticated model, fixed-point
arithmetic, banked BRAM weights, JTAG ABI, and 30 MHz target.

Success criteria:

1. Add a failing compiler regression that specifies the registered argmax
   boundary and rejects host-supplied tokens or intermediate states.
2. Generate the smallest implementation that satisfies that regression.
3. Prove exact two-token semantic equivalence against the authenticated oracle,
   including token feedback and all existing checkpoints.
4. Compare primitive counts, fanout/congestion evidence, and pre-route timing
   against the blocked artifact.
5. Only if semantic equivalence passes and control-path pressure improves,
   attempt a bounded implementation run at the unchanged constraints.

This is an unblocker, not board acceptance. It must not change quantization,
model weights, memory transport, or expand scope to DDR3, PCIe, other models,
or general-prompt CLI behavior. Board inference and the full 16-token goal
remain pending until a routed, timing-qualified bitstream exists.
