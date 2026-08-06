# RC context-0 earliest divergence: FP-to-int stale capture

Status: root cause confirmed; strict end-to-end equivalence is not yet
established.

## Frozen counterexample

The unmodified generated closure completes context 0 at cycle 514,871 but
fails the frozen oracle:

- expected final codes: `18,-93,-34,7,20,1`; expected token: `4`
- observed final codes: `-70,26,22,-112,-39,10`; observed token: `0`

Scratch snapshots localize the earliest divergence to the first token
embedding quantization. Port 61 contains the correct alternating f32 words
`3bdc35f4,3ca48aec`; port 62 should contain `[36,88]` repeated, but the stale
closure begins `0,11,37,86,...`.

## White-box trace

The HardFloat divider receives the correct operands and produces the correct
quotients:

| Input | Scale | Quotient bits | Value |
| --- | --- | --- | --- |
| `3bdc35f4` | `39871d03` | `41d09e07` | about 26.077 |
| `3ca48aec` | `39871d03` | `429be146` | about 77.940 |

The next conversion/rounding stage consumes a value one loop iteration late:

- 26.077 is initially subtracted from 0;
- 77.940 is subtracted from stale 26;
- the following 26.077 is subtracted from stale 77.

The Calyx `std_fpToInt` primitive registers `out` on a clock edge and asserts
`done` after its latency. The stale Futil used `fptosi_*_reg.write_en = 1'b1`,
so the destination register captured the old primitive output on the same
edge. It must instead use the corresponding `std_fpToIntFN_*.done`.

## Causal A/B

The existing compiled Verilator model was changed only at the two FP-to-int
captures used by the initial quantizer: f32-to-i32 truncation and final
f32-to-i8 storage. The same 3,000-cycle replay then produced:

```text
QSUB left=41d09e07 right=41d00000 out=3d9e0700
QZERO left=41d00000 right=41200000 out=42100000
QSTORE data=24
QSUB left=429be146 right=429a0000 out=3f70a300
QZERO left=429c0000 right=41200000 out=42b00000
QSTORE data=58
SCRATCH port=62 values=24,58,24,58,24,58,24,58,0,0,0,0,0,0,0,0
```

Hex `24,58` is decimal `36,88`, exactly the oracle-backed quantization. This
establishes the stale capture as the cause of the earliest divergence; it is
not an `exp`, divider, memory-binding, or simulation-normalization error.

## Durable pipeline guard

`scripts/pipeline/fix_futil_fptosi_handshake.py` is an idempotent post-export
guard. For every Calyx group that connects `std_fpToIntFN_N.out` to a
`fptosi_M_reg`, it either:

- replaces an unconditional result-register write with
  `std_fpToIntFN_N.done`, or
- verifies that the correct gate is already present.

A fresh RC export already contains all 130 correct gates, consistent with the
repository's CIRCT patch for this known latency issue. The guard prevents a
stale or unpatched CIRCT export from silently recreating the bug. The focused
unit tests and `nix build .#rc-calyx-fptosi-latency -L` pass.

## Remaining gate

The full native Calyx SV rebuild was stopped after more than 70 minutes. It
remained CPU-bound near 95%, consumed about 28 GiB RSS, and had not emitted
`main.sv`. Therefore the clean full closure and strict 48-code/token context-0
run remain outstanding. No equivalence claim should be made until that run
passes without modifying the oracle or acceptance criteria.
