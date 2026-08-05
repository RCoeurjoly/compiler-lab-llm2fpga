# V=6 PT2E W8A8 RC first-output latency diagnosis

## Scope

This is a bounded simulation diagnosis, not an equivalence result. The
simulation uses the frozen reference image and the generated Calyx-native SV
fixture. The four-query gate remains unrun.

## Reproducible artifacts

- Fast fixture/run derivation:
  `/nix/store/qv0hhzh9w2wwi95hkmcwp5k3cvcma5m6-tinystories-w8a8-rc-first-output-run-ascending`
- 340-second cached heartbeat run:
  `equivrun`, with runtime metadata reporting `exit_status=124`.
- The fixture explicitly materializes `mem0.hex` through `mem45.hex` and runs
  the simulator from that directory. Missing memory-file warnings are absent
  from the valid run artifact.

## Measurements

The durable short probe reaches 1,000 cycles with 120 memory requests and 120
memory completions, without an output write. The longer run reaches 304,265
cycles and 20,983 requests/completions, also without an output write. Its FSM
has advanced to state 4,730.

The request and completion counts remain equal in the observed heartbeats.
There is therefore no evidence that the simulator is stalled on an unreturned
memory response. The observed latency is dominated by the serialized Calyx
control schedule and the datapath operations it sequences, rather than by the
image-backed memory handshake in this fixture. This does not isolate Softmax
or `math.exp` internally; those remain candidates within the generated
schedule and require state-level instrumentation or a semantics-preserving
operator boundary to separate.

## Initial state correlation

The highest-residency state `1652` appears in `model.futil` as `bb0_1652`:
it runs `std_mulFN_36` and writes `mulf_36_reg`. Its enclosing control contains
an 8-by-2 repeated loop, matching the observed 128 repetitions of the dominant
state transitions. This is direct evidence of serialized floating-point
multiply loop work in the generated Calyx schedule. It is not evidence that
the operation is incorrect, nor yet a license to replace it; it identifies a
candidate region for an equivalent scheduling or component-boundary
optimization.

## Consequence

Do not launch the four-query gate blindly. The next experiment should preserve
the same PyTorch/SV contract while adding state-region or operator-boundary
counts, or use a formally equivalent simulator optimization. No logits or
token ID have been observed, so functional equivalence is not demonstrated.
