# RC serving cache-chain equivalence

Status: **passed for the three compiler-generated semantic phases**. This is
still a transaction-level/native-SV result; it is not PCIe, DDR3, synthesis,
P&R, bitstream, or board evidence.

## Root cause found

The earlier W4A8 serving bundle exported `prefill-8`, `decode-8`, and
`decode-9` independently. Each phase constructed a fresh source model and
derived its cache from the unconverted source invocation. Consequently the
decode input cache did not equal the preceding converted prefill/decode output
cache. The phase shapes looked compatible, but the value-level autoregressive
contract was broken.

`materialize_w4a8_bundle` now chains the converted output explicitly:

1. `prefill-8` starts from an empty cache.
2. Its converted logits select the next token with the frozen lowest-index
   argmax rule.
3. Its four converted cache leaves are reconstructed into the next phase's
   dynamic cache.
4. The same procedure feeds `decode-9` from converted `decode-8` output.

The export tests cover both token/cache forwarding and invalid prefill/cache
arity. The corrected Nix artifacts prove the value chain independently of the
RTL simulation:

| boundary | SHA-256 values |
| --- | --- |
| prefill output cache leaves | `89919a14`, `506b88f7`, `6b2cde06`, `146a45ce` |
| decode-8 input cache leaves | exactly the four prefill hashes above |
| decode-8 output cache leaves | `9ed34f27`, `af04ca73`, `04a60482`, `8c045c1a` |
| decode-9 input cache leaves | exactly the four decode-8 hashes above |

## Exact compiler-generated simulations

All three phases were lowered through the pinned PyTorch → MLIR → SCF →
flat-SCF → Calyx → SystemVerilog route and run with
`scripts/pipeline/run_rc_serving_w4a8_sv.py` inside `nix develop`. Every
observable output matched its authenticated PyTorch reference bit-for-bit
(zero maximum and mean absolute error).

| phase | generated SV SHA-256 | flat-SCF SHA-256 | compile / simulation |
| --- | --- | --- | --- |
| prefill-8 | `4d7bb7685a613b19e77cdabb7ef9073864c77de64558c9d0f7027f1d3f293e5b` | `5fd9efe083f44b29d961a50f8d8487e094a88c5d0c15e0465b133a47cb9829e9` | 487.78 s / 511.34 s |
| decode-8 | `9a980022f1c681bb38adc90cdaf3075b9a7e6e2f635ee00c8179f8b79b10791d` | `2125bcb5a45932e8a192281ff8244d001ef19576a1e28ec990fe8934aa5fd61e` | 376.32 s / 60.26 s |
| decode-9 | `fb86b36e4e2db9f2eeea8636bf816c8f60c30648c58f78ba9cae68115c52d2d1` | `56d110fdf071a16b04d6eed5195d27947dd1ec4a9d2a8f636b5e73592915cc95` | 376.32 s / 61.25 s |

The immutable phase packages are:

- `i3b5949ny5pqhb4xl61z2f49qz0545an-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-pytorch-exported`
- `s9bnv6jpkdgp5r9gfnjdbjkgyml8kwn9-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-8-pytorch-exported`
- `cg159n1am3x5x9gw7axy1yfyfwv1vdav-tinystories-w4a8-rc-serving-mask10-vocab6-width2-decode-9-pytorch-exported`

The corresponding simulation receipts were written during verification to
`/tmp/rc-prefill8-chain-o2/report.json`,
`/tmp/rc-decode8-chain-o2/report.json`, and
`/tmp/rc-decode9-chain-o2/report.json`; their SHA-256 values are, respectively,
`e6e50e4834e8d6de5c0eb1a6950f0464e744a6e9976bd7fb43c4c84b33bff8c2`,
`2e0188f566ee6f05f74fcd0d480291c0c6f01f7d7874cb1b5a8c7679aa8aef3e`, and
`66e33eba4d22dfe4bdd8bde45f7bf4c4aa4e4ce524febedc04e779008cb6d850`.

## Boundary and remaining work

This closes the RC's exact three-phase compiler semantic gate and demonstrates
that the compiler route can represent stateful autoregressive cache handoff for
this reduced contract. It does **not** establish full TinyStories-1M lowering,
PCIe ingress, UberDDR3 calibration or image loading, FPGA fit/timing, a
bitstream, or board inference. The next gate is to expose this same chained
phase ABI through the RC platform wrapper and prove image load/readback before
attempting physical inference.

## Integrated export repair

The first wholesale integrated-export attempt failed before MLIR lowering. It
re-quantized the float serving module in one calibration pass, rather than
preserving the phase-frozen programs. The first qparam divergence was in
`decode-8` (zero-point `-127` in the frozen phase versus `-128` in the
integrated conversion); `decode-9` then diverged again (`-88` versus `-79`).
The resulting integrated outputs were not equivalent: prefill matched, but
decode cache leaves and tokens did not.

The repair composes the three already-converted phase programs and exports that
composition. This preserves all 489 frozen quantize/dequantize nodes instead
of recalibrating them. The corrected Nix receipt is:

- integrated export: `/nix/store/43l65zdd0hyp0c4mw2580pdyw4m24za3-tinystories-w4a8-rc-serving-integrated-pytorch-exported`
- exported program SHA-256: `89653bb633e6137a27ef56d8ea4fc6ce70e0347851f33e5c5709e6c0db019712`
- compiler phase ABI SHA-256: `c941f2129d91d407dfc4aa1db1b8f35ee0cf818edaa4d6b20e5155a959956c6c`
- `frozen_phase_outputs_equal`: `[true, true, true]`
- `frozen_phase_qparams_equal`: `true`
- save/reload equality: `true`

The Nix phase-ABI receipt is `/nix/store/8rkz3l80r4a45lgx8zfxz6zqwnz424jx-tinystories-w4a8-rc-serving-phase-abi-verification/report.json`,
SHA-256 `101e32f60f6755e28092558c6ed21109039d0e2c0371e50844ae9e65936df422`.
It records the corrected cache chain and all three generated flat-SCF/native-SV
phase hashes. The integrated output ABI emits last-token logits (`[1, 6]`),
while each internal phase retains its full sequence logits; this shape is now
explicitly normalized at the compiler-owned boundary.
