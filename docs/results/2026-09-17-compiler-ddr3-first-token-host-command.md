# Compiler DDR3 first-token host command

Do not run this until exact-image first-token simulation passes and the exact
compiler integration has a timing-qualified, programmed bitstream. PCIe
enumeration alone is insufficient. Preserve the loader-only baseline.

The existing host utility can send the four prompt words and request one token,
but its default model size and reference are for the legacy service. Override
both. This reuses transport software, not kev-gpt accelerator RTL.

Run from `/home/roland/compiler-lab-llm2fpga`, substituting the authenticated
compiler image path and a persistent run-receipt destination:

```sh
nix develop .#default -c python3 \
  /home/roland/LLM2FPGA/.worktrees/kev-baseline-limits/scripts/task6/task6_pcie_tinystories_infer.py \
  0000:42:00.0 \
  --reference-json artifacts/reference/tinystories-1m-compiler-ddr3-first-token-reference.json \
  --model-image /path/to/authenticated/compiler-image.bin \
  --model-bytes 4136720 \
  --verify-all \
  --timeout 300 \
  --json-out /path/to/run/first-token.json
```

Before any transfer, verify that the image SHA-256 equals the reference's
`model_image_sha256`. The CLI's length check is not an identity check. Verify
the programmed bitstream's source receipt separately; the compiler adapter
does not authenticate the package-tag CSR. The prompt is `[7454,2402,257,640]`
and the expected output is exactly `[11]`. This is one-token acceptance only.

Do not supply `--expected-trace-hash`: compiler-mode legacy DEBUG/cache/stall
fields are unsupported and driven to zero. The host utility's legacy
`localization` classification is not evidence of an arithmetic fault; a mismatch
requires actual transaction/checkpoint diagnostics. A full-image readback pass
proves transfer integrity, not accelerator arithmetic or timing.

The recipe has been checked against the host utility's reference parser and
transfer-image normalizer without MMIO access. It has not been run on hardware
for this compiler DDR3 candidate.

The actual command-adapter RTL now also has a behavioral Verilator test in
`tests/test_tinystories_1m_ddr3_command_adapter.py`: four-word prompt order,
held start/valid, rejection of early START, stalled request acceptance/counting,
delayed response forwarding, retained token under backpressure, and clear/rearm.
Its source is byte-identical to the synthesis-pinned adapter. A mutation that
disconnects held `valid` is rejected by the test. The backend in this test is
an explicitly test-only contract fixture; this does not establish actual-model
inference through the command adapter or through PCIe.
