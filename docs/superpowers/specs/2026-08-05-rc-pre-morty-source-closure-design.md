# RC pre-Morty source-closure design

## Status and decision

**Status:** approved direction; awaiting implementation-plan approval.

The V=6 PT2E W8A8 representative-core equivalence proof will bypass Morty.
The DUT is an explicitly named **Calyx pre-Morty SystemVerilog source
closure**, compiled by Verilator from a canonical ordered set of generated and
library sources.  It is not described as a Morty-bundled `main.sv` artifact.

This changes packaging only.  It does not alter the PT2E reference, model
image, W8A8 arithmetic, Calyx lowering flags, generated component logic,
memory protocol, or observable acceptance criteria.  The existing
Morty-bundled target remains available and unchanged for users that need it.

The decision follows the current failure mode: native Calyx finishes emitting
the raw 9.77 MB design but its embedded Morty phase does not finish within a
useful build interval.  The raw design contains a 613,929-character FSM
expression that is normalized safely for Verilator.  The normalized raw source
plus its explicit primitive closure passed the pinned Verilator lint check and
completed Verilator C++ generation in about 29 seconds.  That is feasibility
evidence, not yet functional-equivalence evidence.

The relevant Calyx discussion describes Morty as a dependency stitcher added
for float wrappers, not as an arithmetic transformation.  It also calls
comparison to a known-good software result critical for this kind of
multi-tool integration.  This design makes that comparison stricter than the
historical one-file packaging route.

## Goals

1. Materialize the exact pre-Morty Calyx output reproducibly, without scraping
   a temporary file.
2. Define and validate every file, include, macro policy, order, and tool
   input that Verilator consumes.
3. Preserve the strict exact-six-int8-logit and lowest-index-argmax proof
   described in `2026-08-04-rc-observable-equivalence-design.md`.
4. Pass the frozen four-context fresh-versus-sequential gate before producing
   any full-domain result.
5. Retain enough provenance to merge complete deterministic shards covering
   all `6^8 = 1,679,616` contexts.

## Non-goals

- Repair, update, or depend on Morty for this proof path.
- Claim byte identity with Morty's timestamped, nondeterministically ordered
  bundle.
- Concatenate source files, use a glob, or allow ambient include paths as a
  shortcut around an explicit dependency contract.
- Relax any completion, exact-output, argmax, ABI, memory-binding, or shard
  coverage rule from the existing observable-equivalence design.

## Design

### 1. Explicit Calyx raw-emission mode

Patch the pinned Calyx backend with a visible CLI flag:

```text
--emit-pre-morty
```

The flag is valid only when the input imports the float special library.  In
that case Calyx retains its normal validation, inline-primitive emission,
component emission, `--synthesis`, `--nested`, and `-d papercut` behavior but
skips only the existing Morty `do_pickle` call.  Its already-existing copy from
the temporary emission file to `-o` then writes the exact pre-Morty source.

The default is false, so ordinary `-b verilog` retains the existing Morty
behavior.  The flag is deliberately not an environment variable: it must be
present in compiler logs and in the producer receipt.

The patch changes:

- `src/cmdline.rs` to parse `emit_pre_morty`;
- `calyx/ir/src/context.rs` to transport it in `BackendConf`;
- `src/main.rs` to set it; and
- `calyx/backend/src/verilog.rs` to reject misuse and guard the Morty block.

It is packaged as a normal checked-in Calyx source patch in `nix/calyx.nix`.
No Morty source, Cargo lockfile, or flake lockfile change is part of this
route.

### 2. Separate Nix producer artifact

Create a sibling producer derivation named along the lines of:

```text
tinystories-w8a8-rc-polynomial-exp-calyx-native-pre-morty-sv
```

It consumes the same normalized Futil and compiler flags as the current
native-SV target, invokes `-b verilog --emit-pre-morty`, and publishes a raw
generated source under a path outside the current `sv/` directory.  It also
publishes a source-closure manifest and a generation receipt.

The current bundled artifact's `sv/main.sv` and `sources.f` remain unchanged.
In particular, raw and bundled sources must never appear together in an
existing generic file list, where another downstream consumer could compile
both definitions accidentally.

### 3. Canonical `rc-sv-source-closure-v1`

The producer writes canonical JSON and a human-readable `sources.f`.  The JSON
is authoritative.  It has at minimum:

```json
{
  "schema": "rc-sv-source-closure-v1",
  "top_module": "main_1",
  "sources": [
    {
      "ordinal": 0,
      "logical_path": "sources/0000-seq.sv",
      "language": "systemverilog",
      "raw_sha256": "...",
      "bytes": 0
    }
  ],
  "include_roots": [
    {
      "ordinal": 0,
      "logical_path": "includes/hardfloat-common",
      "files": [{"logical_path": "HardFloat_consts.vi", "raw_sha256": "..."}]
    }
  ],
  "defines": [],
  "undefines": ["VERILATOR"],
  "verilator_arguments": ["--top-module", "tb"],
  "canonical_sha256": "..."
}
```

Canonicalization uses UTF-8 JSON with sorted object keys, exact integer
representation, no insignificant whitespace, domain-separated SHA-256 inputs,
and an order-sensitive array representation.  The receipt records both raw
and simulation-normalized hashes for each top-level source, plus unchanged
hashes for include-only files.

The source manifest rejects an empty list, absolute or escaping paths,
symlinks, duplicate paths, nonregular files, unsupported suffixes, compiler
flags in a file list, and undeclared macro or include inputs.  It permits only
`.sv` and `.v` compilation units, and literal include files that are explicitly
listed under an ordered include root.  Macro-computed includes, unresolved
includes, include cycles, and `main_1` definitions in include material reject
the closure.

`main_1` must occur exactly once in a top-level source, though it need not be
the first one.  The runner derives the external-memory ABI from that source
only after validating the full closure identity.

### 4. Fixed RC closure contents

For the present float-enabled representative core, the initial canonical source
order is:

1. `primitives/memories/seq.sv`
2. `primitives/float/mulFN.sv`
3. `primitives/float/intToFp.sv`
4. `primitives/float/fpToInt.sv`
5. `primitives/float/divSqrtFN.sv`
6. `primitives/float/compareFN.sv`
7. `primitives/float/addFN.sv`
8. `primitives/core.sv`
9. `primitives/binary_operators.sv`
10. `HardFloat_primitives.v`
11. `HardFloat_rawFN.v`
12. `addRecFN.v`
13. `compareRecFN.v`
14. `divSqrtRecFN_small.v`
15. `fNToRecFN.v`
16. `iNToRecFN.v`
17. `isSigNaNRecFN.v`
18. `mulRecFN.v`
19. `recFNToFN.v`
20. `recFNToIN.v`
21. `RISCV/HardFloat_specialize.v`
22. generated `pre-morty-calyx.sv`

The sealed include-root order is:

1. `HardFloat-1/source` containing `HardFloat_consts.vi` and
   `HardFloat_localFuncs.vi`;
2. `HardFloat-1/source/RISCV` containing `HardFloat_specialize.vi`.

The producer copies or stages these exact files under closure-owned logical
paths; it never retains store paths as the compile contract.  The source list
is deliberately explicit rather than generated by `find`, `sort`, or Calyx's
internal `HashMap` iteration.

Verilator compiles the staged top-level sources in manifest order, then the
generated testbench.  It receives the two staged `-I` roots in manifest order
and a recorded `-UVERILATOR` policy.  That undefines the simulator macro that
would otherwise select wrapper diagnostics that Morty historically removes.
The policy is an input to both MRC and frozen-gate comparison, not an assumed
property of Verilator.

Only the giant generated top-level source is passed through the existing
simulation-only normalizer.  Its continuous-assign paging preserves
four-state `|` and `?:` semantics and does not introduce procedural logic.
Primitive and include bytes remain exact unless a later manifest revision
explicitly says otherwise.

### 5. Producer provenance receipt

The producer receipt forms this required chain:

```text
exported.raw.futil + f32 constant-bit proof
  -> normalized model.futil + normalizer identity
  -> patched Calyx executable/package + exact flags including --emit-pre-morty
  -> raw pre-Morty generated source
  -> canonical source-closure manifest and staged closure bytes
```

This closes the important distinction between the raw-Futil file proven by the
current f32 receipt and the normalized Futil file actually consumed by Calyx.
The receipt also records CIRCT, Calyx, HardFloat, Verilator, Python runner, and
Nix derivation identities.

### 6. Strict runner, cache, and result contracts

Retain `--sv PATH` as a one-member compatibility adapter for non-strict
diagnostics.  Strict closure mode requires all of:

```text
--sv-filelist PATH
--sv-root DIR
--sv-closure-manifest PATH
```

All three are mutually exclusive with `--sv`.  The runner stages a private,
fixed-name snapshot:

```text
verilator-work/
  sv/
    0000.sv ... 0021.sv
    includes/00/...
    includes/01/...
    sources.f
    closure.json
  tb.sv
  memory-abi.json
  external-memory-bindings.json
  mem0.hex ... mem45.hex
  obj_dir/Vtb
  compile-metadata.json
```

Run-only validation reconstructs the producer closure from current inputs and
byte-compares every staged source, include, filelist, closure receipt,
testbench, ABI receipt, binding receipt, and runtime memory image before it
may run the cached executable.  No cache metadata hash can be rebased to
approve a different compiler input.

This increments the strict cache schema from v8 to v9, result receipts from
`rc-observable-verilator-shard-v3` to v4, and the frozen-four reducer schema
from v3 to v4.  A result records the full validated closure table and its
canonical digest, not only a single source hash.  The frozen reducer and full
shard merger require one identical closure identity across every receipt.

### 7. Equivalence validation ladder

The implementation is accepted only in this order:

1. Unit-test the Calyx flag: ordinary float output remains bundled by default;
   raw mode fails for non-float input and emits pre-Morty bytes for a small
   float input.
2. Validate closure parsing, staging, source ordering, macro policy, includes,
   ABI discovery, and cache mutation rejection with small synthetic fixtures.
3. Run the existing float MRC corpus through bundled and direct closures,
   including the fptosi latency cases.  Require exact observable agreement and
   lifecycle behavior; do not compare timestamped bundle bytes.
4. Build one strict direct-closure artifact and run a `[0,1)` observable smoke
   transaction to establish genuine completion and raw-logit observation.
5. Run the frozen four contexts in independently compiled/fresh processes and
   a reset-separated sequential process; require exact six-code outputs,
   lowest-index argmax, and one valid completion for every context.
6. Run a measured multi-record throughput probe, freeze a deterministic shard
   partition, execute every shard of `[0, 1,679,616)`, and merge only a
   complete nonoverlapping range with identical closure provenance.

The previous strict fixture remains authoritative for reset, completion,
immutable memory, output-write, oracle, and counterexample requirements.  A
direct-closure pass is still not a broad correctness claim: it is precisely a
proof for the declared V=6 PT2E reference and this declared Calyx source
closure.

## Acceptance criteria

- The raw output is durable, deterministic, explicitly selected by a visible
  Calyx CLI flag, and produced in a separate Nix artifact.
- Every direct-Verilator compilation input is sealed, ordered, declared,
  staged, and hash-bound to its producer receipt.
- A malformed, reordered, omitted, mutated, path-escaping, or macro-altered
  closure fails before simulation.
- The direct closure and available bundled float MRCs agree under the pinned
  macro and lifecycle contracts.
- Frozen-four and full-domain evidence retain all criteria from the existing
  observable-equivalence design while naming the pre-Morty source closure as
  the DUT.
