# RC Verilator iteration-cost design

## Status and objective

**Status:** approved by the request to pursue the simulation-cost survey as an
active goal.

Make the V=6 PT2E W8A8 representative-core SystemVerilog loop materially
faster to iterate on without changing the DUT's numerical model, its
image-backed memory ABI, or the exact frozen-oracle contract.  The first
implementation phase addresses avoidable simulator and compilation work; it
does not attempt an accelerator rewrite.

## Evidence and boundary

The generated native Calyx SV is about 9.96 MB and contains two especially
large control expressions: a 6,993-arm `fsm0_in` priority ternary and an
8,854-term `fsm0_write_en` bitwise-OR expression.  The existing
simulation-only normalizer replaces both with procedural `always_comb` scans.
That form is not equivalent for unknown (`X`) or high-impedance (`Z`) values:
an `if (X)` selects neither branch, whereas an SV conditional can merge both
arms and bitwise OR propagates an unknown where appropriate.

The current fixture also bakes heartbeat logging and the selected corpus case
into the compiled testbench.  Canonical builds therefore cannot change
verbosity or select one of the frozen cases without a rebuild.  Finally, the
runner reports one aggregate Verilator time, so front-end/C++ generation and
the native C++ build cannot be optimized independently.

This work is limited to the V=6 RC's simulation fixture and lexical,
simulation-only normalization.  It must not edit the raw generated SV, the
PT2E export, the reference image, the lowering pipeline, arithmetic, or
memory-response protocol.

## Design

### Reusable quiet fixture

The generated testbench always contains all frozen corpus cases.  Its runtime
configuration uses Verilator plusargs:

- `+heartbeat_cycles=<nonnegative integer>` controls periodic telemetry; zero
  disables it without evaluating a modulo-by-zero expression.
- `+timeout_cycles=<positive integer>` changes only the fixture watchdog.
- `+case_index=<index>` selects one compiled corpus case; `-1` runs all cases.
- `+stop_after_output=0|1` preserves the existing first-output diagnostic.
- `+trace_output_writes=0|1` enables the verbose output-write trace only for
  diagnosis.

The Python CLI validates these values and supplies them on every execution,
including `--run-only`.  Thus one cached binary can run quietly, verbosely, or
for a selected frozen case.  The normal build default is quiet; the existing
heartbeat diagnostics retain explicit nonzero values.

Each compiled cache also records hashes of the runner, SV, image, manifest, and
frozen reference, its fixture defaults, binary-relative path, and compiler
configuration. The canonical `--run-only` gate verifies those input hashes and
reports cached compilation metadata rather than treating current run-only CLI
defaults as compile settings.

### Conservative continuous-expression normalizer

The normalizer remains lexical and simulation-only, but it no longer emits
procedural assignments.

For a large scalar bitwise-OR assignment, it creates a hierarchy of scalar
`wire` pages, each retaining the original `|` operator and no more than a
fixed number of operands.  The top-level assignment ORs the page outputs.
Bitwise OR is associative per four-state bit, and all intermediate signals are
nets, so the transformation retains the expression's stable-value `X`/`Z`
behavior after combinational settling. The added page nets can add delta
cycles, so this is not a general same-timestep or event-order equivalence
claim; the full exact integration gate remains required.

For a large priority ternary it acts only after proving a narrow shape:

- the destination has one directly declared, unsigned, numeric packed range;
- the chain is syntactically flat; and
- every true arm and its default are unsigned, explicitly sized literals of
  exactly that destination width.

It then constructs false-tail pages as continuous assignments to `wire`s with
the same packed range. Every page preserves the original `?:` operator and
arm ordering for stable values after combinational settling. Any source whose
type or syntax cannot be proven falls back to the unmodified assignment. This
is intentionally conservative: keeping an
unsupported expression large is safer than silently altering Verilog sizing or
four-state conditional semantics.

### Separately measured build stages

For Verilator, the runner uses two commands with the same semantic options:

1. `verilator --cc --exe --main ...` performs parsing, elaboration, and C++
   generation.
2. `make -C obj_dir -f Vtb.mk -j <build-jobs> Vtb` compiles, archives, and
   links the generated C++.

It records normalizer time, fixture-generation time, front-end/code-generation
time, native C++ build time, runtime time, generated-C++ count/bytes, and
binary bytes. Existing
`--verilator-jobs` remains a compatibility alias; new `--verilate-jobs` and
`--build-jobs` allow independent sweeps.

The matrix is intentionally one-factor-at-a-time: establish a quiet baseline,
then vary Verilator jobs, make jobs, partition sizes, and finally Verilator
runtime threads.  Each selected configuration must first show forward progress
on a bounded probe, then pass a frozen one-case exact smoke test, then the
unchanged four-case exact gate.  Instrumented profiling is diagnostic only and
is never used for comparative throughput claims.

## Acceptance criteria

- Unit tests cover zero/positive heartbeat rendering, runtime corpus selection,
  stage command construction, and no generated procedural normalization.
- A four-state SV self-test compares original and normalized OR/ternary
  expressions across `0`, `1`, `X`, and `Z`, including page boundaries.
- The actual RC normalizer reports its transformed-page counts and raw versus
  normalized SV sizes.
- The canonical build requires the four-state normalizer derivation and
  confirms that the target `fsm0_in` and `fsm0_write_en` expressions were
  actually paged without adding procedural blocks.
- The normal performance target builds with heartbeat disabled; the dedicated
  first-output diagnostic remains explicitly verbose.
- The exact frozen one-case and four-case contracts stay intact.  No cost
  configuration is promoted unless it yields their exact six raw codes and
  lowest-index argmax.
- A durable Nix result records each chosen configuration and its stage metrics.

## Non-goals

- No approximate nonlinear functions, reduced precision, pruning, sparsity,
  altered reduction order, or retraining.
- No replacement of the Calyx-generated DUT with a behavioral model.
- No claim that a bounded forward-progress probe proves full equivalence.
- No attempt in this phase to solve the measured serialized floating-point
  compute latency; that requires a separately scoped structural kernel change.
