# RC observable-equivalence design

## Status and objective

**Status:** approved by the active goal to establish reproducible PyTorch to
SystemVerilog functional equivalence for the fixed representative core.

Build an evidence-backed comparison between the frozen V=6, context-length-8
PT2E W8A8 reference and the generated Calyx SystemVerilog through Verilator.
The gate has two tiers:

1. a strict four-context frozen regression gate; and
2. deterministic durable shards that together compare every one of the
   `6^8 = 1,679,616` token contexts.

The PT2E exported program is the only numerical acceptance authority.  The
gate compares the six signed int8 codes at output `[0, 7, :]` and their
lowest-index argmax.  It does not weaken a timeout, an incomplete transaction,
or a diagnostic output write into a pass.

## Evidence and boundary

The earlier matmul test establishes the useful basic pattern: calculate a
golden result in PyTorch, drive generated SV, compare exact values in
Verilator, and fail on mismatch or timeout.  Its fixed one-vector, generated
testbench cannot serve the RC's complete finite domain.

The current RC fixture is a four-case smoke scaffold, not an equivalence
proof.  It embeds reference cases in the testbench, can print a result after
an output write without observing `done`, and only clears token memory between
sequential cases.  The last condition is materially unsafe: the generated
`main_1` exposes 146 external memories.  Static write-enable analysis of the
actual SV finds that ports `0..25` and `27..45` are DUT-immutable, while output
port `26` and scratch ports `46..145` are potentially mutable.  The mutable
set contains 2,476 words (66,192 bits).

This work keeps raw generated SV, PT2E export, image bytes, memory response
latency, and W8A8 arithmetic unchanged.  It changes only the verification
fixture, oracle artifacts, Nix wiring, and evidence records.

## Design

### Image-backed transaction wrapper

The runner derives an ABI receipt from the actual generated `main_1` source:

- every `arg_mem_N` port must have a width and capacity;
- every port's write-enable expression must be classified conservatively;
- only a write enable that is syntactically proved always zero is immutable;
- an unsupported or changed classification rejects fixture generation rather
  than silently reusing an image with a different ABI.

The initial process loads the frozen image only into its declared image-backed
ports.  It initializes token port `25`, output port `26`, and all scratch
ports explicitly.  The receipt records the per-port class, width, depth, and
a digest of the normalized classification.

Before **every** transaction, while reset is asserted, the testbench:

1. zeroes `mem26` and every scratch memory `mem46..mem145` through its
   declared capacity;
2. writes the eight token IDs to `mem25[0..7]` and zeros remaining input
   capacity, if any;
3. clears memory-response values, request/completion counters, output masks,
   and latency counters; and
4. holds the existing reset timing contract for three clock edges before
   deasserting reset and asserting `go`.

Image-backed ports are not reloaded per transaction.  The memory-service
model instead fails immediately if the DUT requests a write to any
DUT-immutable port.  This protects the image and turns a lowering/ABI change
into an auditable rejection.  The one-cycle memory response protocol remains
the existing fixture protocol.

The implementation must demonstrate reset equivalence before using a
multi-context shard: each frozen context run in a fresh process must have the
same raw codes, argmax, and completion status as the same contexts in one
process with the transaction reset sequence.

### Strict completion and observables

Equivalence mode has no early-output option.  `--stop-after-output` and
output-write tracing remain explicitly named diagnostics and are rejected by
the equivalence CLI.

For each context, the fixture records the launch edge and requires all of the
following:

- `done` is sampled before the candidate's versioned conservative cycle
  bound;
- each final-logit address `mem26[42]` through `mem26[47]` was written during
  that transaction;
- after `done`, the fixture waits two clock edges so simultaneous nonblocking
  writes settle, rejects a late final-logit write, then samples all six values;
- the expected record's reserved bits are zero, every expected argmax is in
  `0..5`, and the argmax computed from sampled raw codes uses the lowest
  index in a tie; and
- all six sampled signed int8 codes and the independently compared argmax
  equal the PT2E record.

A timeout, absent final write, invalid write sequence, immutable-memory
write, malformed record, raw-code mismatch, or argmax mismatch emits a
counterexample packet and fails the shard.  A result line alone is never
evidence of success.

### PT2E oracle records and deterministic enumeration

The shared enumeration is base-six lexical, most-significant token first and
rightmost token fastest.  It uses half-open ranges `[start, stop)` over
`[0, 1,679,616)`.  The context for ordinal `k` is decoded from `start + k`;
therefore it need not be duplicated in each full-domain payload record.

Each oracle shard contains:

```text
shard-<start>-<stop>.hex
shard-<start>-<stop>.json
```

The payload has exactly one lowercase 16-hex-digit 64-bit word plus newline
per context:

```text
bits  7:0   output code 0, two's-complement int8
bits 15:8   output code 1
bits 23:16  output code 2
bits 31:24  output code 3
bits 39:32  output code 4
bits 47:40  output code 5
bits 55:48  lowest-index argmax, unsigned 0..5
bits 63:56  zero
```

The generator loads the exported PT2E module once per shard and evaluates
batch-one `torch.long [1, 8]` contexts under inference/no-grad mode.  It
validates the exact int8 `[1, 8, 6]` output shape, checks the frozen
four-case `reference.json` against that same evaluator before writing records,
streams the payload while hashing it, and writes complete metadata only after
record-count, field, padding, size, and digest validation.

Shard metadata binds the exported program and manifest hashes, reference and
image hashes, image manifest hash, generator and contract hashes, Python and
PyTorch versions, configured PyTorch thread count, enumeration specification,
record format, exact payload hash/size/count, and generation timing.

The compiled SV fixture reads one record at a time from the payload at runtime
and decodes the corresponding lexical context from the supplied start index.
This avoids compiling the testbench once per context or once per shard.
The four frozen smoke gate uses four independently addressable one-record
lexical shards, mapped back to the named corpus cases in its result manifest.

### Result shards, merging, and evidence

Each SV result shard binds its exact oracle metadata and payload hashes,
normalized-SV hash, raw-SV hash, runner/fixture hash, ABI receipt hash,
reference-image hashes, Verilator and host/tool versions, range, declared
cycle bound, count, latency minimum/maximum, and wall-clock throughput.  It
records a complete pass only after every record in its range passes.

On first failure it emits a durable counterexample packet containing the
lexical index and tokens, expected and observed codes and argmax, completion
state/cycle count, final-address write mask, immutable-memory write state,
the timing contract, and a bounded trace sufficient to replay the run.

The merger sorts shard receipts by `start` and rejects any different receipt,
schema, record format, payload digest/count mismatch, incomplete status,
duplicate range, overlap, or gap.  It emits `coverage.complete: true` only if
the exact ordered union is `[0, 1,679,616)` and publishes each component
digest.  Result and coverage artifacts are Nix-produced or checked-in durable
outputs, never transient work directories.

### Execution tiers

1. Render and unit-test the strict ABI/fixture/oracle format.
2. Generate and run a `[0,1)` strict lexical smoke; establish one genuine
   `done` and final-output completion.
3. Generate the four named frozen one-record shards and require exact raw-code
   and argmax equality in both fresh-process and one-process-reset forms.
4. Run a bounded multi-record throughput probe with diagnostic tracing
   disabled.  Publish contexts/s, cycles/context, resource use where
   available, and projected full-sweep cost.
5. Freeze a deterministic shard plan from that measurement; run all shards;
   merge only complete successful receipts.

If the probe shows the full execution impractical, publish the scalability
blocker and keep the candidate provisional.  Do not replace exhaustive
coverage with sampling or call smoke evidence functional equivalence.

## Acceptance criteria

- The four frozen contexts pass exact codes and lowest-index argmax with a
  strict `done`/final-write completion sequence.
- Fresh-process and sequential transaction-reset results agree exactly for the
  frozen contexts.
- All fixture memory classes are derived from the actual SV and recorded;
  unsupported ABI changes fail safely.
- Oracle payloads are directly generated by the frozen PT2E evaluator and
  pass self-validation and frozen-reference preflight.
- Diagnostic early-output paths cannot be invoked by a passing equivalence
  command.
- Every full-domain result shard includes exact oracle, DUT, ABI, tool, range,
  count, digest, and latency provenance.
- The merged manifest proves disjoint complete coverage of `[0, 1,679,616)`.
- A full manifest is not produced if a shard fails, times out, or is absent.

## Non-goals

- No claim about larger vocabularies, longer contexts, full TinyStories,
  internal signals, board timing, or general operation-level equivalence.
- No behavioral model, altered arithmetic, changed image, or modified
  generated SV in the verification path.
- No acceptance based on a first output write, a partial prefix, a sampled
  corpus, or a timeout without a durable rejection record.
