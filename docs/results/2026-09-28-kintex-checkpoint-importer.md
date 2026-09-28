# Kintex routed-checkpoint importer diagnostic

## Scope

An isolated nextpnr diagnostic, not an accelerator correction or board acceptance.
The existing geometry diagnostic and production tools remain unchanged.
No model, arithmetic, placement, route, clock, constraints or board image are changed.

The one-ROM compiler mapping was committed separately as diagnostic checkpoint
`2a92742`, after 52 focused tests passed. Its generated-RTL two-token result is
`[11,612]`; its measured board result remains `[11,1375]`. The repository-wide
suite has previously recorded unrelated historical failures and is not claimed green.

## Reproduction and correction

The public `--json --no-pack --no-place --no-route` command crashes while loading
an existing routed checkpoint. `getPipName` emits wire-to-wire arrow names,
whereas `getPipByName` previously accepted only SITEPIP and legacy numeric names.
The small fixture `tests/fixtures/nextpnr/kintex-routed-arrow.json` reduces the
same defects to two real routed sentinel nets. The original geometry package
exits 134 with `std::out_of_range` in 0.07 seconds.

Patch 0040 adds arrow-name import via canonical source/destination wire IDs and
downhill PIP enumeration. It preserves both old parsing branches and refuses
unknown or ambiguous names instead of silently choosing a different route.
The first arrow-only correction passed the local-site case but failed the full
sentinel on `INT_R_X25Y181/LOGIC_OUTS0->INT_R_X25Y180/SS6A0`.
`getWireByName` returned tile-local aliases where `getWireName` had emitted
canonical multi-tile node names. The isolated patch also canonicalizes named
wire lookup; the second fixture net reproduces this failure against the
arrow-only tool. This is necessary for both PIP endpoints and root-wire binding.
The Nix package is `nextpnr-kintex-checkpoint-diagnostic`; its base package still
evaluates to the unchanged geometry diagnostic store path
`/nix/store/h8wh17487a7wysalqnpf6xs68gc646h3-nextpnr-xilinx-kintex-geometry-diagnostic-0.8.2`.

## Repeatable checks

Build with bounded resources:

```sh
timeout --kill-after=10s 1800 nix build --impure \
  .#nextpnr-kintex-checkpoint-diagnostic --no-link --max-jobs 1 --cores 2
```

Use that package's `bin/nextpnr-xilinx`, the existing pinned Kintex chipdb and
the following arguments, first for the reduced fixture, then the CSR sentinel,
then the exact one-ROM production routed JSON:

```sh
nextpnr-xilinx --chipdb CHIPDB --json ORIGINAL.json \
  --no-pack --no-place --no-route --write RELOADED.json --sdf ROUTED.sdf
nix develop --impure -c python \
  scripts/diagnostics/check_routed_checkpoint_identity.py ORIGINAL.json RELOADED.json
```

The identity checker compares cell types, assigned BELs and parameters, plus
every net's exact sorted `(wire,PIP,strength)` triples. It ignores only JSON
enumeration order. Its four focused tests cover order independence, changed
resources/strengths, duplicates and malformed triples.

## Timing limitations

SDF interconnect export can expose routes terminating on BRAM/DSP ports even
though the existing timing classifier ignores these ports. It is not full
timing qualification: BRAM/DSP internal arcs, setup/hold requirements and
coverage still require separate analysis. The importer defect is not established
as the physical inference mismatch's root cause.

## Actual validation outcome

The isolated canonical-wire build completed successfully:
`/nix/store/4ic30a652ns02lcsj30fy6xh6fb2ffvs-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`.
Both reduced routed nets reload with identical cell parameters and exact
`(wire,PIP,strength)` triples. Four identity-checker tests pass.

The complete CSR sentinel does **not** pass. It exits 255 on an ambiguous name:
`SITEWIRE/SLICE_X36Y184/CLK->SITEWIRE/SLICE_X36Y184/CLKINV_OUT`.
Two distinct PIP IDs produce this same spelling. The patch deliberately refuses
to choose one arbitrarily. Thus the old exported route names are not sufficient
to reconstruct the exact route; correcting the parser alone cannot establish
route identity. No production-checkpoint SDF export, route-preservation acceptance,
or physical timing conclusion is claimed.

Further work must preserve unique PIP identity in new checkpoints and recover
the old candidate's ambiguous selections from independent exact configuration
evidence (such as its original FASM), or use a newly serialized checkpoint from
the original routing context. Replacing this refusal with first-match selection
would hide lost configuration information and is not an acceptable fix.
The user explicitly approved committing this failed experiment as a diagnostic
checkpoint and continuing with bounded configuration-preserving recovery.
This checkpoint records the full-sentinel failure, not a completed importer fix.
Commit `2a92742` is unaffected.

## Unique-identity serialization follow-up

The failed importer diagnostic was committed as `ce5c1b6` with explicit user
approval. A subsequent isolated patch, 0041, emits `PIPID/tile-name/index` names,
qualified by the exact pinned chipdb. It does not change routing decisions.
The chipdb confirms the affected site's parallel PIPs 148 and 149 have the same
source/destination and timing class but different CLK/CLK_B selectors.

Source inspection also found that the old getPipName copied TileTypeInfoPOD and
TileInstInfoPOD objects containing self-relative pointers; their offsets are
valid only at the original mapped addresses. The new numeric naming avoids
these copies as well as selector-name collisions. This is a checkpoint writer
defect, not established as the inference mismatch's cause.

The public CLI regression first failed on the old diagnostic tool. Its initial
new-tool run exposed stale ROUTING attributes during no-route JSON export.
Patch 0041 refreshes those attributes from actual bound resources before
writing. The final Nix check passed all nine tests, including two reloads,
preservation of the second parallel selector, invalid-ID rejection, unambiguous
legacy-arrow import and fail-closed ambiguous legacy-arrow import:

```sh
nix build --impure .#checks.x86_64-linux.nextpnr-kintex-checkpoint-identity \
  --no-link --max-jobs 1 --cores 2
```

Receipt: `/nix/store/42b5hgzzkxdacf0djvcmws25jhwijc4d-nextpnr-kintex-checkpoint-identity`.
The check pins its tool and chipdb as Nix dependencies and does not program hardware.

The repository-wide unittest run was separately bounded to 180 seconds and
exited 124 during `test_full_pinned_loader_shell_bar_fixture`, without a final
suite result. No FAIL/ERROR test statuses had been observed before termination;
this is incomplete verification, not a green suite. The user explicitly approved
the serializer follow-up as a diagnostic checkpoint despite this incomplete
repository-wide verification. Recovering ambiguous names in the
old full sentinel/production checkpoint and proving equivalent original FASM
remain pending; no production SDF timing or hardware inference success is claimed.

## Legacy slice-clock evidence preparation

The test-first `prepare_legacy_clock_recovery.py` helper validates the placed
SLICE_FFX cells' original FF types and boolean clock-inversion parameters
against the original FASM and pinned tilegrid. It rejects missing, conflicting,
unsupported or mismatching evidence before writing any derived design. Its
only design mutation is explicit `checkpoint/selector/<site>/CLKINV` settings;
cell parameters, placement and routing attributes are preserved. Original
files cannot be overwritten. CLK versus CLK_B is a physical-configuration
normalization, not proof of the lost historical PIP index.

The positive tests first failed because the helper was absent; all seven
preparation tests now pass. The expanded pinned Nix check passes all 16 tests:
`/nix/store/0gzd9z4wp5gj470k64rqr15j8nvd2wga-nextpnr-kintex-checkpoint-identity`.
Actual original-artifact runs also passed: the CSR sentinel validates 274 FFs
at 118 sites, and the one-ROM two-token candidate validates 16,622 FFs at
7,451 sites. Both receipts explicitly mark historical PIP identity and full
route/FASM equivalence as unproven.

The isolated importer does not consume these settings yet. Full-sentinel
reload, wire/strength preservation, equivalent original FASM and production
SDF export remain pending. No accelerator RTL, route, bitstream, programming,
clock or constraint changed. This helper result is not hardware acceptance.

An initial repository-wide run used bare pinned Python, outside the project's
development environment. A focused reproduction identified missing `torch`
and missing `iverilog`; that run is not valid project-suite verification.
The suite was rerun with `nix develop --impure -c timeout ... python -m unittest
discover -s tests -v` and a 180-second limit, so the declared dependencies are
available. The isolated preparation/checkpoint check remains independently
Nix-reproducible and passed as recorded above.

The correctly configured broad run exited 124 at the 180-second deadline
during `test_selection_capture_and_response_boundaries` in
`test_external_memory_arbiter_staging`, without a final suite result.
It recorded twelve ERROR statuses in `test_continue_pcie_smoke_lifecycle`
and one FAIL in `test_exact_pipeline_source_closure`. This
is failed and incomplete verification, not a green suite. The user separately
approved committing the preparation helper as a diagnostic checkpoint despite
these verification limits. The earlier serializer approval was not treated as
standing permission for subsequent checkpoints.

A separate Nix-shell reproduction of those two test modules completed:
17 tests, one failure and twelve errors. The lifecycle module refuses import
with `reviewed lifecycle backend changed; refusing import`; the source-closure
test finds an allowlist mismatch. Those runtime scripts and allowlist were
not changed by this preparation step. No blanket repository-suite pass is
claimed, and these existing verification failures are not silently repaired
as part of the checkpoint recovery.

An independent whole-JSON comparison of the actual derived artifacts confirms
that the sentinel adds exactly 118 selector settings and the production
candidate adds exactly 7,451. Removing only these newly added settings makes
each parsed JSON document equal to its original in full, including cells,
parameters, placement, connections, seed and routing triples. This validates
preparation's preservation contract, not the still-pending importer reload or
physical FASM equivalence.

Immediately before the approved commit, all 16 focused tests were rerun
against the pinned diagnostic binary and chipdb: exit zero in 2.549 seconds.
Full importer/FASM recovery and hardware acceptance remain pending.
