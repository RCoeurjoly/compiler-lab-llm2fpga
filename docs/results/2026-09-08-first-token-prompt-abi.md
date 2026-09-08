# First-token prompt ABI repair

The first-token goal uses the full compiler-generated TinyStories-1M model,
BRAM only, the validated 30 MHz clock, and the existing 64-bit USER1 transport.
The authenticated prompt is `[7454, 2402, 257, 640]`; its first reference token
is `11`. The existing fixture verifier passed for artifact
`31fbd1e3f5b13d7b07466a72e9c6a551ffc00bd4fee375241f095ba5b5cda677`.
This check did not perform a fresh eager-model replay.

## ABI change

Prompt writes (opcode 1) now use command bits `[17:16]` for the index and
`[15:0]` for the value. Opcode 6 reads the stored word at index `[17:16]`,
returning its value in response bits `[15:0]` with upper bits zero. Read all
four words after writing all four; write echoes alone cannot prove storage.
Opcode, shift order, TAP sequencing, status, reset, start, and token-read
semantics are unchanged.

This is incompatible with the former overlapping index in `[5:4]`. The v2
host checker requires the rebuilt image; do not run it against the accepted
v1 CSR bitstream and mistake an ABI mismatch for hardware regression. The
historical v1 receipts and accepted bitstream remain unchanged.

## Verification

The actual CSR RTL test failed before the repair: the frozen prompt was stored
as `[640, 7454, 2402, 0]`. After the repair, three write/readback/reset sequences
passed with the BSCANE2-gated DRCK model. The test checks both core-facing
prompt wires and serial readback of every stored word.

The host regression failed against the revised device ABI before its repair.
Afterward, 23 tests passed across `tests.test_tinystories_user1_check`,
`tests.test_tinystories_1m_bram_production`, and
`tests.test_tinystories_1m_bram_image`. A negative host test rejects successful
write echoes when storage is lost. The host checker never issues START.

## Remaining acceptance

The compiler now accepts `generation_steps=1` or `2` (default `2`) through
`generate_production_kernel` and `generate_model_kernel`. It rejects other
values, including booleans and non-integer lookalikes. The one-step output
differs from the two-step Calyx text only in `model_step_lt.right`: `2'd1`
instead of `2'd2`. Source-memory descriptors and oracle identity are unchanged;
the provenance records the selected execution length and real context lengths.
The existing audit-generator Futil hash regression also passes. All 25 targeted
tests passed after this change. This is generator verification, not execution.

The simulation runner accepts `--generation-steps 1`, retains default 2,
records compiler provenance, checks observed token commits, rejects commits
beyond the requested execution length, and compares the public `token_id`
port as well as stored selected tokens. Executable C++ checker tests use a
controlled model-port fixture: they are checker tests, not model inference.
All 29 targeted tests passed. The full one-step model also lowered to SV in
1.47 seconds (Futil SHA-256
`55b2ae5a55e7c1931ca627655e48dbafc2c272144f08c48f349a6c23a4160b52`).

The static-image builder also accepts `--generation-steps 1` and binds its
manifest to that schedule's Futil and oracle hashes instead of silently using
the two-step default. Its new test materializes all 240 real immutable source
memories into a temporary image and checks the manifest; the test's SV skeleton
only exercises initialization and is not an inference design. All 30 targeted
tests passed.

The full-model SV run is in `/tmp/tinystories-first-token-sv-20260908`, with log
`/tmp/tinystories-first-token-sv-20260908.log`, under a 1,800-second outer bound.
It has entered actual cycle execution; no completion claim is made here.

Full generated-SV execution, a new physical build, and three
independent FPGA reconfigurations with exact first-token inference remain
unperformed. No inference success is claimed. Accelerator timing coverage
remains incomplete; functional success will not imply full timing qualification.
