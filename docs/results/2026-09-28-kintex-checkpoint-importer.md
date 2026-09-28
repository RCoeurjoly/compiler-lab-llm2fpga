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
