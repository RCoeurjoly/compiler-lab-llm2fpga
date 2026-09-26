# RC prefill-8 exact compiler-generated RTL equivalence

The current compiler-generated RC native-SV closure completed the exact
prefill-8 transaction-level simulation after optimizing only the Verilator C++
host executable. No RTL, Futil, model image, memory ABI, or testbench
transaction was changed.

## Authenticated inputs

| artifact | SHA-256 |
|---|---|
| flat-SCF input | `5fd9efe083f44b29d961a50f8d8487e094a88c5d0c15e0465b133a47cb9829e9` |
| Futil handoff | `ad341b31e06ddc57ededf8336c511713c7a450ca21cc7324ab3c054e37602115` |
| generated native SV (`vvlf…`) | `9c5605c45624cf385949cccfc4b73a9614d7d072c9b4a6e6eefc2f8b4676e5e1` |
| PyTorch/reference package | `3188f16fa6f89b1ad772c205032cf632389aed4994f210ad4e64ca513ddc5191` |

The generated testbench loaded the same pinned memory image and ran the frozen
eight-token input. The executable was compiled with one Verilator job and C++
`-O2`; this changes simulation speed only.

## Result

```text
DONE cycles=524816
elapsed=507.36 seconds
```

The five semantic output payloads match their authenticated reference payloads
bit-for-bit. The logits output is compared using the generated ABI's 48-word
buffer and its final six words, as required by the serving harness.

| output port | compared words | payload SHA-256 | reference SHA-256 |
|---:|---:|---|---|
| 32 (logits suffix) | 48 → 6 | `1e1751495a4cad0034fe16b815749e71537fce5224615d51f0cac35ba1ad9ed8` | `1e1751495a4cad0034fe16b815749e71537fce5224615d51f0cac35ba1ad9ed8` |
| 33 (cache 0) | 16 | `89919a14be298c7b621bfbea413a173b166a1df54e16ee6f4b5b560b0c2e0470` | same |
| 34 (cache 1) | 16 | `506b88f7965e551c62cb2145bdeeaa9ac5704eef00ddcf71b7258298869da6da` | same |
| 35 (cache 2) | 16 | `6b2cde066041a4278251ac35e80da848841869686a209c8020d09a21495b8b4f` | same |
| 36 (cache 3) | 16 | `146a45ceda43b4d646970a61d684481ab1aedb720dfb78c6e9e0b5cd509fcb0d` | same |

The raw output-file hashes are recorded in
`/tmp/rc-prefill8-o2/receipt.json`; the temporary files are not deliverables.

## Significance and boundary

This is the first current-closure exact RC prefill equivalence result. It
confirms that the compiler-generated RTL and generated memory transaction
interface are semantically correct for this frozen fixture. It does not yet
establish autoregressive multi-token behavior, synthesis or timing closure,
PCIe ingress, DDR3 calibration, a bitstream, or board inference. The roughly
8.5-minute host simulation remains the next iteration bottleneck.
