# Compiler DDR3 queued-address reset experiment

The static-counter six-hour route ended with exit 124, without routed FASM,
routed JSON, or final timing. Its last logged queue had 94,834 arcs after
21,274.77 router seconds. The full log remains at
`/tmp/compiler-ddr3-route-6h.ZFiOPF/route.log`, SHA-256
`aa5f3ced552b70ca175da324b6e8e021bf1165ff726e7489208cdfca3540fa90`.
This is a timeout, not proof of unroutability or a final timing failure.

Read-only netlist inspection found 23,598 physical input-pin loads on
`rowstream_rst_n`, versus 19,603 in the static-wait placement whose full route
completed (but failed timing). In the current synthesis, 3,745 reset loads
belong to external request-address registers. This is a measured optimization
target, not proof that reset fanout caused the routing timeout.

The compiler external-memory cell now captures `queued_address` in a separate
reset-independent process when its local slot is empty. Valid/control reset,
request-index reset, response state, PCIe, DDR3, clocks and constraints are
unchanged. An address is captured on the enqueue edge and held while queued
or pending. Its invalid-cycle value is deliberately unspecified.

The structural regression failed on the prior resetful implementation because
Yosys inferred SRST on the address register. The new implementation passes.
A frozen compiler-cell reference (not kev-gpt) supports a Yosys induction
miter for WIDTH=8, IDX_SIZE=4, SIZE=16, BASE=19. It compares valid addresses,
done, read data and unchanged internal control/index state, assuming initial
reset only. Subsequent resets and all other inputs are unrestricted. The
internal-state assertions strengthen induction; they are not assumptions.
The initial output-only proof timed out at 90 seconds; the strengthened proof
passes. This cell proof does not qualify every full-model parameterization.

Full-model regeneration, exact-image simulation, synthesis/resource comparison,
routing, timing and board inference remain required before promotion. The
previous pinned static-counter candidate and loader baseline remain intact.
