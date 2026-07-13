# Full TinyStories PT2E W8A8 TOSA–Handshake scout

Date: 2026-07-13

## Outcome

The full TinyStories PT2E W8A8 model successfully lowered through TOSA,
Linalg, CF, Handshake, and Handshake external-memory preparation without using
Calyx. It failed while lowering Handshake to HW: `circt-opt` was killed with
exit code 137 after its resident set had reached at least 27,373,360 KiB in a
point observation. No HW artifact, SystemVerilog, or Yosys statistics were
produced.

This establishes that TOSA can rejoin the Task 3 Handshake backend. It also
shows that the full PT2E graph causes a severe Handshake IR and memory
explosion before SV.

## Route

```text
Full TinyStories PT2E W8A8
-> Torch-MLIR
-> TOSA legalization and validation
-> Linalg
-> CF
-> Handshake
-> Handshake external-memory preparation
-> HW (failed)
-> SV (not reached)
-> Yosys (not reached)
```

Calyx: not used.

Command:

```sh
scripts/pipeline/monitor_build.sh \
  /tmp/full-tinystories-w8a8-tosa-handshake-scout 5 -- \
  nix build .#tinystories-w8a8-via-tosa-yosys-stat \
  --no-link --print-out-paths -L
```

## Terminal frontier

The last successful artifact was `hs-ext`. The next derivation ran:

```text
circt-opt ... -lower-handshake-to-hw -canonicalize
```

and terminated with:

```text
Killed
builder failed with exit code 137
```

The monitored command ran for 1,339 seconds and exited 1. The generic monitor
sampled only the Nix frontend and reported 552,804 KiB peak RSS. Because Nix
executes the compiler under `nix-daemon`, that worker was not a descendant of
the frontend and was absent from the monitor's process tree. A direct `ps`
observation recorded the active `circt-opt` worker at 27,373,360 KiB RSS. This
is a lower bound, not a sampled peak.

## Artifact growth

| Stage | Lines | Bytes |
|---|---:|---:|
| Torch MLIR | 3,025 | 27,233,314 |
| Raw TOSA | 6,155 | 27,430,773 |
| Linalg | 30,019 | 28,911,438 |
| CF | 131,303 | 33,326,877 |
| Handshake | 30,556,692 | 1,766,701,841 |
| Handshake external-memory preparation | 30,718,121 | 1,805,393,024 |

The CF-to-Handshake conversion expands a 33 MB, 131-thousand-line artifact
into approximately 1.77 GB and 30.6 million lines. The failure is therefore
not a TOSA legality problem. It is a full-graph Handshake scalability problem.

## Remaining floating-point computation

The CF artifact still contains 4,252 classified floating-point operations:

| Operation | Count |
|---|---:|
| `arith.mulf` | 1,129 |
| `arith.cmpf` | 953 |
| `math.floor` | 478 |
| `arith.sitofp` | 279 |
| `arith.subf` | 264 |
| `arith.fptosi` | 239 |
| `arith.maximumf` | 239 |
| `math.ceil` | 239 |
| `math.roundeven` | 239 |
| `arith.addf` | 141 |
| `math.rsqrt` | 17 |
| `arith.divf`, `math.exp`, `math.powf`, `math.tanh` | 8 each |
| `arith.minimumf` | 3 |

HW and SV were not generated, so there is no final external floating-point
primitive mapping to inspect. Even if this route later reaches SV, that alone
will not establish integer-only hardware: PT2E W8A8 remains QDQ-heavy and the
compiler input still contains substantial floating-point computation.

## Interpretation

TOSA plus Handshake is structurally viable, and it avoids the Calyx
`math.floor` rejection. It does not currently provide a practical full-model
SV path: Handshake lowering expands the graph by roughly two orders of
magnitude in text size, and Handshake-to-HW exhausts host memory.

The next useful investigation is to compare this expansion with Task 3 at the
same boundaries and determine whether PT2E QDQ scaffolding is being converted
into replicated control/dataflow. Reducing or fusing that scaffolding before
CF-to-Handshake is more promising than simply allocating more host memory.

Machine-readable evidence is in
[`artifacts/full-tinystories-pt2e-w8a8-tosa-handshake-scout/result.json`](../../artifacts/full-tinystories-pt2e-w8a8-tosa-handshake-scout/result.json).
