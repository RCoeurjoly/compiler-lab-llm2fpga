# Loaded-image ownership-mux simulation

This is test-only RTL/C++, not accelerator implementation RTL. The production
candidate and active routing experiment remain unchanged.

The host driver writes all 4,136,720 image bytes through the pinned production
ownership mux, reads every word back and compares with the input file, then
supplies the frozen four-token prompt. The memory model starts without
`readmemh` initialization. It inserts periodic request stalls and delayed
responses. The expected inference result remains token 11; a successful load
alone is not inference acceptance.

The corrupt-write negative control returned 2 at line 17, word 0, as expected.
The clean load-only run returned 0. Full inference is launched but not yet
verified in `launch.json`. All test doubles remain below the production
Wishbone ownership boundary; PCIe and DDR3 physical interfaces are not modeled.

Reproduce from the repository root using the unchanged payload-reset model:

```sh
nix develop .#default -c timeout --signal=TERM --kill-after=10s 1800 \
  verilator --cc --exe --build --timing -j 2 -O3 -Wno-fatal \
  --top-module command_integration_wrapper \
  --Mdir /tmp/compiler-ddr3-owner-sim.lXS9X3/obj \
  /tmp/compiler-ddr3-payload-reset.tywJVR/model.sv \
  /nix/store/9zbn7rgdgpw2q7h92sj22h3m4b446d5a-llm_external_memory_arbiter.sv \
  /nix/store/4n5p2q9c3im9qrizysw6jcfc4ni0xc39-tinystories_1m_ddr3_backend.sv \
  /nix/store/dn9gwzarhz2kdlc9z8v7h7s6q1fpz7qr-tinystories_1m_ddr3_command_adapter.sv \
  /nix/store/5f2fppa4a3636py498f4pv5500dsizfm-task6_wishbone_owner_mux.sv \
  "$PWD/artifacts/diagnostics/2026-09-18-owner-mux-simulation/owner-integration-wrapper.sv" \
  "$PWD/artifacts/diagnostics/2026-09-18-owner-mux-simulation/owner-integration-driver.cpp"

timeout --signal=TERM --kill-after=10s 10800 \
  /tmp/compiler-ddr3-owner-sim.lXS9X3/obj/Vcommand_integration_wrapper \
  +MODEL_BIN=/tmp/compiler-ddr3-current.2Z9Mo4/image.bin
```

Use `--load-only` to stop after readback and `--load-only --corrupt-write`
for the negative control (expected exit 2). The build and run directories are
temporary; sources and the measured load results are tracked here. Candidate
regeneration and image provenance are documented in the payload-reset report
and the model-image manifest. Never substitute another source merely because
it has the same filename; check the receipt hashes.
