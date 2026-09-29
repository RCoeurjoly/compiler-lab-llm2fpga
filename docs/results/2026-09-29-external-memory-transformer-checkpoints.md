# Compiler TinyStories-1M external-memory transformer checkpoints

## Result

The actual compiler-generated full16 accelerator, with 86 external weight/scale
ports, matches the authenticated PyTorch reference through embedding, all eight
transformer blocks, and final layer normalization for the first frozen context
`[7454,2402,257,640]`. Each of the ten checkpoint tensors contains 256 signed
64-bit values (2,048 bytes), representing the four active context rows.

The complete 4,002,704-byte image is first written and read back through the
host Wishbone interface. The positive run takes 226.95 seconds including that
transfer, reaches final normalization after 75,133,217 inference cycles, and
records 3,499,112 balanced requests/responses. Every returned 128-bit word
matches the authenticated image. A deliberately corrupted host write still
fails readback at line 17, word 0.

The corrected externalizer is committed as `3764bc8`. No compiler, arithmetic,
image, transport, clock constraint, or hardware change was made for this
checkpoint run. Test-only observation ports expose existing memory contents;
they do not supply intermediate tensors or generated tokens to the accelerator.
The runner checks each newly published tensor and stops on the first mismatch.

## Durable evidence

- Full run, raw trace, ten tensor dumps, oracle, executed runner and receipt:
  `/nix/store/32z1is6lry03kg1divnx95na4wvr7rdp-compiler-full16-86-port-loaded-image-final-ln-diagnostic`.
- Native simulator, test-only C++ driver, wrapper and build log:
  `/nix/store/x1v4i69ga60nfi65wr577f082lsyg38v-compiler-full16-86-port-owner-boundary-simulator`.
- Unchanged compiler externalization and image:
  `/nix/store/m9d58k28vlq0j8rvrsfv1hbcndbxng9k-compiler-accepted-full16-ddr-weights-preflight`.
- Earlier block-0 bounded run:
  `/nix/store/3m16z82ps0vpjn117jir366gybkh08rl-compiler-full16-86-port-loaded-image-block0-diagnostic`.

The final-normalization receipt has status
`passed-full-image-and-final-ln-only`. Independent post-run verification reads
all ten complete dumps and compares their byte hashes with the frozen oracle;
it also checks the raw trace length and native counter totals. The executed
runner verifies every trace word against image bytes. Nix preserves the exact
sources, tools and inputs; elapsed-time fields are observations, not promises
of identical wall-clock durations on rerun.

## Limits and next action

This is single-clock transaction-level simulation of the actual accelerator,
existing arbiter, registered Wishbone pipeline and production owner mux. It
does not simulate PCIe ingress, controller calibration, DDR3 PHY behavior or
clock-domain crossings. No synthesis, routing or programming was performed.
The accepted first-token BRAM board baseline remains installed.

The run stops before the language-model head: token `11`, autonomous external-
memory generation and hardware inference remain unproven. On-chip full16 board
acceptance remains a separate passing result.

The block-0 trace identifies avoidable broadcast traffic: all 25 packed
token-weight banks receive 256 reads each (6,400 total), and all 25 token-scale
banks receive four reads each (100 total), although existing selectors consume
one bank per lookup. The proposed next compiler optimization is to extend the
existing selected-bank lowering to this packed layout, preserving operation
isolation and requiring checkpoint/first-token equivalence before physical
implementation. That optimization has not been applied or approved yet.

See [operation isolation](2026-09-29-external-memory-operation-isolation.md) for
the stale-response correction and the explicitly red/incomplete repository-wide
verification. This report is a verified simulation result, not a whole-suite
pass or first-token/board acceptance.
