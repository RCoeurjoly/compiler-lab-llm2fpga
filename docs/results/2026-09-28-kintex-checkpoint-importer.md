# Kintex routed-checkpoint importer diagnostic

## Scope

An isolated nextpnr diagnostic, not an accelerator correction or board acceptance.
The existing geometry diagnostic and production tools remain unchanged.
No model, arithmetic, placement, route, clock, constraints or board image are changed.

## Current result

The full existing production checkpoint now reloads without packing, placement
or routing. Complete configuration and semantic preservation checks pass;
the diagnostic JSON/FASM/SDF exports are retained in
`.superpowers/sdd/2026-09-09-tinystories-16-token-board/checkpoint-recovery-20260928/`.
This fixes the diagnostic export path, not hardware inference. The last board
result remains `[11,1375]`, versus `[11,612]`. See the final section for the
actual preservation evidence, tool paths and timing limitations. Earlier
failures below are chronological evidence, not the current importer status.

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
though the existing timing classifier ignores these ports. The later actual
chipdb audit below establishes a wider limitation: this exact database has
zero cell-timing tile types. LUT/carry cell delays use fallback estimates, and
BRAM/DSP internal paths are omitted. Thus neither the original Fmax nor this
SDF is timing qualification, even on nominally covered paths. Internal arcs,
setup/hold requirements, clock skew and coverage require separate analysis.
The importer defect is not established as the physical inference mismatch's
root cause.

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

## Real sentinel reload: additional lost selectors and site variants

The slice-selector importer passed its reduced CLI regressions but the actual
prepared CSR sentinel exited 255 at the BUFGCTRL IGNORE1 inversion pair. Its
original parameters and original FASM agree on all six control inversions for
each of the three placed BUFGCTRL cells. Read-only chipdb inspection confirms
the parallel input PIPs and the relative-coordinate mapping for all 32 BUFG
sites. Preparation was extended to validate this actual configuration, not to
select the first matching PIP. The real sentinel and production preparations
validate three and four BUFG sites respectively, preserving their original
cells and routes.

The first extended tool build failed because the patch hunk declared 45 new
lines instead of 46, omitting its closing brace during application. This was
corrected and the next isolated build passed. However, the real sentinel
reload still exited 255, now on
`SITEWIRE/IOB_X0Y174/INBUF_EN_OUT->SITEWIRE/IOB_X0Y174/I`.
Thus reduced test success did not establish integration success.

The exact chipdb identifies this as IUSED PIPs 50 and 62 in
`LIOB33_X0Y173`, belonging to site variants 0 and 1. The original checkpoint
places the clock PAD and input buffer at `IOB_X0Y174/IOB33/...`, identifying
the active variant rather than an inversion setting. Source inspection
confirms that cell BEL bindings are restored before routed PIPs. The ongoing
correction therefore resolves candidate site variants from those existing
bindings before applying explicit inversion settings; absent or conflicting
placement evidence remains an error. Its actual I/O public-CLI reproduction
failed on the preceding build even with the correct placed buffer present.

The actual sentinel reload, full route/FASM equivalence, production SDF
export and hardware inference remain pending until verified with this
ordering correction. No placement, route, bitstream, accelerator, clock,
constraint or board state has been changed. Small test counts are regression
safeguards, not acceptance milestones.

### Verified sentinel physical-configuration gate

Independent BEL metadata inspection shows that `IOB33/INBUF_EN` and
`IOB33/PAD` belong to chipdb variant **1**, not the initially presumed variant
0. The reduced test expectation was corrected to IUSED PIP 62 after this
independent audit; the importer already selected the actual placed variant.
The corrected pinned check is
`/nix/store/lwaas7fdbhj10i6ap084nb66psmgcaf6-nextpnr-kintex-checkpoint-identity`.

Using its tool
`/nix/store/h8sj3vmw0csqw0y9p9r2q51qrx4h649g-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`,
the actual prepared sentinel now reloads with `--no-pack --no-place --no-route`
and emits JSON, FASM and SDF. Independent comparison verifies 654 cells and
668 nets: cell types/parameters, named bit connections, BEL placement and
strength, all physical PAD attributes, and per-net route wire/strength/PIP-
presence multisets agree. All 8,302 original FASM feature lines agree after
ignoring order, whitespace and comments. The SDF contains 789,874 bytes.

Raw JSON equality is not claimed: the writer renumbers net IDs, omits
disconnected cell ports and drops the logical top-level port table. Comparison
uses named-net identities; physical PAD metadata and original FASM are
unchanged. This exported checkpoint is diagnostic, not replacement compiler
RTL. Exact lost historical PIP indices remain unproven.

### Production gate still fails: canonical interconnect alias

The same no-route production reload, bounded to 120 seconds and 20 GiB virtual
memory, exits 255 on
`INT_L_X20Y149/WL1BEG3->INT_R_X19Y149/IMUX31`. It emits no accepted production
SDF. A read-only chipdb/FASM audit finds two ordinary tile-routing candidates
with the same canonical source/destination nodes and timing class 206:

- PIP 3422, `INT_R_X19Y149.IMUX31.WL1END3`: present in original FASM.
- PIP 3537, `INT_R_X19Y149.IMUX31.WR1END_S1_0`: absent in original FASM.

Thus the original FASM retains a unique physical switch choice where the
checkpoint's canonical arrow loses it. The next correction must use this
independent routing configuration, not first-match selection or an inversion
setting. Production reload/FASM equivalence, physical timing localization and
the two-token board gate remain pending; the passing small sentinel is not a
substitute for them. No production route or board image changed.

### Original-FASM interconnect recovery reaches the BRAM boundary

The isolated diagnostic importer now accepts `--checkpoint-fasm` and selects
an ordinary INT switch only when exactly one matching physical feature is
present in that original FASM. Neither absent nor conflicting evidence is
accepted. The real production reload using
`/nix/store/r1684krhnhwjbzvn10nw4cxqh8zwym7m-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`
gets past the interconnect alias but exits 255 at
`SITEWIRE/RAMB18_X2Y87/CLKARDCLK->SITEWIRE/RAMB18_X2Y87/CLKARDCLKINV_OUT`.
Its log is `/tmp/kintex-fasm-production-reload.z4Lqwm/reload.log`; no accepted
production SDF was emitted.

Independent evidence for this next ambiguity:

- The actual placed cell is `core.v_weight_codes_i8.mem.0.9`, type
  `RAMB18E1_RAMB18E1`, at `RAMB18_X2Y87/RAMB18E1`.
- Its port-A clock inversion parameter is absent, meaning the pinned writer's
  default false; the original `BRAM_L_X26Y215.RAMB18_Y1.ZINV_CLKARDCLK`
  feature independently agrees.
- The pinned database contains PIPs 376 (`CLKARDCLK`) and 377
  (`CLKARDCLK_B`) with identical endpoints and timing class 4.
- Lower RAMB18 sites use RAMB18 BEL variant 1; RAMB36 cells use variant 2.
  The tilegrid's default site labels (`FIFO18E1`, `RAMBFIFO36E1`) are not
  the placed cell type. Recovery must distinguish these, not assume variant 0.

Preparation now checks all eight supported inversion parameters against the
original FASM for each occupied RAMB18 half, including both halves of every
RAMB36. The actual production image validates 872 BRAM cells. Read-only
inspection verifies absolute-Y parity against relative half for all 1,910
RAMB18 sites in the pinned database. Removing the 20,723 added recovery
settings from `/tmp/kintex-bram-production-recovery.z5qtBo/prepared.json`
recovers the complete original JSON exactly; no cells, connections, memory
initialization, placement or routes were modified.

Executable CLI reproductions fail on the preceding tool for both clock
polarities and both placed BRAM variants. The bounded isolated build and the
full production no-route reload remain pending for this extension. This is
recovery of a diagnostic view of the existing bitstream, not an accelerator
fix and not evidence that the hardware token mismatch is resolved.

### Real production retries: LUTRAM coverage and next DSP selector

The built BRAM-aware tool is
`/nix/store/fr18v4sbx5mq7jrdz74bn6r57k7nn9jv-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`.
It successfully imports both polarities of the actual RAMB18 clock pair and
the placed lower-RAMB18 and RAMB36 variants. On the full production checkpoint,
`/tmp/kintex-bram-production-reload.cSKCYl/reload.log` exits 255 after passing
the previous BRAM failure, at the clock of LUTRAM-only `SLICE_X122Y330`.

That site contains four packed `RAMD64E` cells with non-inverted active write
clocks and no FF. The preparation helper had covered FF clock users but not
distributed-memory clock users. Including independently matching RAMD64E
parameters/FASM lets the next full retry reach a tied-off ROM clock at
`SLICE_X122Y181`, logged in
`/tmp/kintex-lutram-production-reload.WX5owj/reload.log`.

The complete original design distinguishes two real populations: 12,224
RAMD64E cells have active, non-inverted write clocks; 24,760 have inverted
packing parameters but clocks tied to `$PACKER_VCC_NET`. For tied-off clocks,
the packing inversion is not the shared slice-clock setting. The pinned
`write_ffs_config` defaults that setting to non-inverted when no FF occupies
the site. Preparation validates that default against original `NOCLKINV`
FASM, while retaining any shared active clock polarity established by FFs or
RAMD64E cells. It rejects conflicting evidence rather than using a tied-off
ROM parameter to select the physical clock switch.

The resulting actual preparation is
`/tmp/kintex-allclock-production-recovery.GxtXnu/prepared.json`. The latest
independent whole-JSON comparison confirms that removing only its 29,654
added recovery settings reproduces the complete original checkpoint exactly.
The latest
pinned executable check completes successfully at
`/nix/store/x64wjd4lgq6p5yfz6m767b8grx07x9in-nextpnr-kintex-checkpoint-identity`;
this remains a tool regression check, not production inference acceptance.
The subsequent complete no-pack/no-place/no-route reload exits 255 at
`SITEWIRE/DSP48_X5Y98/INMODE0->SITEWIRE/DSP48_X5Y98/INMODE0INV_OUT`.
Its log is `/tmp/kintex-allclock-production-reload.Ex03Fp/reload.log`.

The actual placed DSP48E1 has `IS_INMODE[0]_INVERTED=1`; original
`DSP_L_X54Y245.DSP48.DSP_0.ZIS_INMODE_INVERTED[0]` is absent, agreeing with
the pinned writer's inversion rule. That rule ORs each vector parameter bit
with the corresponding per-bit packing override. Any next DSP recovery must
validate both forms, not read only the original vector parameter. No DSP
recovery selection has yet been implemented, and no accepted full production
SDF/FASM export exists. The board mismatch remains unlocalized.

Read-only chipdb inspection identifies the exact DSP pair in tile 52783:
PIPs 423 (`INMODE0`) and 424 (`INMODE0_B`), both source/destination indices
2471/2299, timing class 4, site-internal flags 3 and variant 0. The original
parameter/FASM evidence identifies the inverted input, but full physical
configuration equivalence must still be verified after the entire import.

The repository-wide Nix suite run in
`/tmp/kintex-bram-importer-nix-suite-20260928.log` times out after 180 seconds
and records twelve errors in `test_continue_pcie_smoke_lifecycle`. The fresh
final-helper run at `/tmp/kintex-allclock-importer-nix-suite-20260928.log`
also exits 124 after 180 seconds, recording those twelve lifecycle errors and
the failure of
`test_exact_pipeline_source_closure.ExactPipelineSourceClosureTest.test_runtime_source_is_exactly_the_sorted_referenced_basename_set`.
Neither a full-suite pass
nor a completed production recovery is claimed. The cohesive importer recovery
remains uncommitted because its real production gate is unfinished; no new
failed-checkpoint commit permission is inferred from earlier approvals.

### DSP-aware recovery preparation

The preceding production failure was reproduced through the public importer
for both polarities of each supported DSP family: INMODE, OPMODE, ALUMODE,
CARRYIN and CLK. All failed on the prior diagnostic tool, before adding DSP
support. Independent chipdb inspection verifies the relative-half mapping
against absolute-Y parity for all 1,920 DSP sites.

Preparation now validates each vector-mask bit OR the corresponding packed
per-bit override against the original complementary `ZIS_*_INVERTED` FASM
feature. It rejects out-of-range masks, contradictory FASM, unknown placed
types and conflicting existing selections. The actual production image
validates all 190 placed DSP cells. A negative control on the full original
design flips only `DSP48_X5Y98`'s `IS_INMODE[0]_INVERTED` parameter in memory;
preparation rejects it at the exact corresponding FASM feature. No original
file is modified by that negative control.

Removing only the 33,074 recovery settings from
`/tmp/kintex-dsp-production-recovery.raqoXg/prepared.json` reproduces the
entire original design exactly. The ongoing isolated DSP-aware tool build
has derivation
`/nix/store/m79nxcyh9cnn4v6ync2b7zlysvayg767-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2.drv`.
Full production import/export and original-FASM equivalence remain pending.
No accelerator, route, bitstream, constraints or hardware state changed.

### DSP passes; next evidenced selector is the MMCM

The DSP-aware diagnostic tool builds successfully at
`/nix/store/n9a8qagvm3kvlb1pw6c437s79irgi9g3-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`,
with its completed pinned check at
`/nix/store/v7pn2xqrv0gwc6pf6frl2sn3r8drn1dw-nextpnr-kintex-checkpoint-identity`.
The real production reload now passes the DSP inversion families and exits
255 on
`SITEWIRE/MMCME2_ADV_X0Y3/CLKINSEL->SITEWIRE/MMCME2_ADV_X0Y3/CLKINSELINV_OUT`,
logged in `/tmp/kintex-dsp-production-reload.fvOwUG/reload.log`.

The original cell is `clock_generator.mmcm`, type
`MMCME2_ADV_MMCME2_ADV`. Its CLKINSEL inversion defaults false, and the
original `INV_CLKINSEL` feature is absent. Its RST, PWRDWN, PSEN and PSINCDEC
inversion parameters are true and the corresponding original `ZINV_*`
features are present. Those historical names are misleading: the pinned MMCM
writer emits them directly for true inversion, not complemented inversion.
Recovery preserves that actual rule rather than changing the configuration.

Independent chipdb inspection identifies the five primary inversion pairs in
`CMT_TOP_R_LOWER_B_X8Y165`: RST 166/167, PWRDWN 168/169, PSINCDEC 170/171,
PSEN 172/173 and CLKINSEL 174/175. All share their respective endpoints,
timing class 4 and site variant 0. Public-CLI reproductions fail before the
MMCM extension for both inputs of each pair.

Preparation now validates the sole placed MMCM's input selections, requiring
its original IN_USE feature. Its derived image at
`/tmp/kintex-mmcm-production-recovery.Cs8IrF/prepared.json` is independently
identical to the original after removing only 33,079 recovery settings. The
frequency, divider and other cell parameters are unchanged. The MMCM-aware
tool build and full-production reload remain pending; no board or production
tool change occurred.

The DSP-stage repository-wide Nix suite times out after 180 seconds at the
loader-shell BAR fixture, with no FAIL/ERROR statuses observed before
termination; it is incomplete, not a pass. Its log is
`/tmp/kintex-dsp-importer-nix-suite-20260928.log`. The final MMCM-stage
repository-wide run is pending separately.

### MMCM import reaches a post-route timing-graph failure

The MMCM-aware tool completed at
`/nix/store/4lxykpaiq3c8mhqbgc23zd0jwcxa1ns6-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`.
Its actual full production reload, logged in
`/tmp/kintex-mmcm-production-reload.GHPFC2/reload.log`, restored the routing
selectors but exited 255 during timing-budget annotation, before JSON, FASM
or SDF exports. Production physical-configuration equivalence remains unproven.
The MMCM-stage broad suite also timed out after 180 seconds; its log is
`/tmp/kintex-mmcm-importer-nix-suite-20260928.log`. It is not a green suite.

The first reported output is LUT2
`core.$abc$371266$auto$blifparse.cc:557:parse_blif$377777.O6`, placed at
`SLICE_X75Y280/A6LUT`. Its physical A1 connection shares O6's net, but its
logical mappings contain only A3/I0 and A4/I1. An independent inspection of
the entire original checkpoint finds 87 direct LUT self-feedback links;
every one is on an input without a logical-port mapping.

The pinned `xilinx/arch_place.cc:920` post-route legalisation shares physical
inputs while retaining each LUT's logical inputs in `X_ORIG_PORT_*`.
`xilinx/fasm.cc:400` uses only mapped inputs to construct the actual truth
table. Conversely, `xilinx/arch.cc:1208` treats connected physical LUT inputs
as timing dependencies, including those unused by that LUT's function.
An executable one-LUT reproduction fails with the same timing-graph error;
mapped feedback and an unrouted feedback control are also rejected.

Diagnostic patch 0044 excludes an unmapped input arc only after routing,
for an ordinary LUT with complete logical-input mappings and an output
mapping. It changes no cells, connections, placement, route or FASM-writing
logic. The isolated Nix build is pending. This is not evidence of timing
qualification, nor of a corrected second token; the full export/equivalence
gate must still run before relying on the production SDF.

### Independent review: evidence preparation must reject stale selectors

Review reproduced an authorization gap: a pre-existing MMCM selector
survived preparation despite no corresponding placed cell or FASM evidence.
The executable helper regression fails before the correction (preparation
returns success), and now rejects that input without output files.
Preparation tracks independently validated selector keys and rejects every
pre-existing recovery key outside that set. Low-level importer tests that
manually supply settings prove selector lookup only, not the complete
evidence-validation chain.

The stricter helper also processes the full original production image at
`/tmp/kintex-validated-production-recovery.PkKlzg/prepared.json`. Removing
only its 33,079 validated recovery settings gives complete JSON equality
with the original, independently checked. The receipt validates 16,382
slice sites, 16,622 FFs, four BUFG sites, 872 BRAM cells, 190 DSP cells and
one MMCM, plus the recorded LUTRAM clock sites. No model or board state
changed. Full route/FASM equivalence is still explicitly false.

### Full production preservation gate passes

The refined isolated diagnostic is
`/nix/store/vzrcgvcgld6pgphxlnl7lvxmb6xdzgy5-nextpnr-xilinx-kintex-checkpoint-diagnostic-0.8.2`
(derivation `nj9hq4knf8l61p18jc5glyfv82bb67yx`). Its final Nix check output is
`/nix/store/7jfcvk5xxxkrs2s9mn9kspw7qbl9y60s-nextpnr-kintex-checkpoint-identity`
(derivation `plxr7i4kgn2sjri54ln0bqrgdgxwc039`). The actual prepared production
checkpoint reload exits zero within its 120-second, 20 GiB virtual-memory
bound, with `--no-pack --no-place --no-route`; neither `--ignore-loops` nor
`--force` is used. The original 30 MHz target remains unchanged.

Independent complete comparisons, not source searches, establish:

- All 2,774,806 original FASM feature lines match as a multiset: zero missing
  and zero added, including configuration vectors, memory contents and routing.
- All 132,911 cells retain their types, parameters, **all** attributes and
  semantic named-net port connections, ignoring only omitted disconnected
  ports and numeric net-ID renumbering.
- All 334,332 nets retain named bit identities, non-routing attributes and
  the complete route-wire/strength/PIP-presence multisets.
- Exact historical parallel PIP IDs remain unrecoverable from the legacy
  serialization; configuration equivalence is established by the complete
  original FASM comparison, not by claiming the old JSON contained those IDs.

Exports and logs were moved from the temporary reload directory to the durable
worktree directory stated above. The stricter prepared input and its receipt
are under `prepared-input/`; the unchanged original production JSON/FASM remain
in `current2/one-rom-cfc-bram/static-image/`. The exported JSON is a diagnostic
view, never replacement compiler RTL or a replacement board image.

The SDF is 185,701,207 bytes and includes 823,414 interconnect records. Excluding
the explicit packer GND/VCC drivers, the longest individual interconnect is
16.358 ns: `core.c_proj_weight_codes_i8.read_addr[5]`, driven by
`SLICE_X32Y251/DFF`, to the RAMD64E weight-ROM read address A6. No single
interconnect in that subset exceeds the 33.333 ns period. This does **not**
establish complete-path timing or exclude a hardware timing fault: paths
combine multiple delays, and BRAM/DSP internal arcs and requirements remain
unqualified. No inference root cause is inferred from this maximum alone.

Review's paired-LUT concern was reproduced as incorrect A6 feedback acceptance
against the first patch-0044 build. The retained refinement never suppresses
A6 arcs and limits the exception to unmapped A1–A5 → O5/O6 arcs with complete
ordinary-LUT metadata. Actual mapped feedback, paired-LUT A6 feedback,
unrouted feedback and incomplete metadata are rejected. Follow-up read-only
review identified no remaining Critical/Important defect in this refinement;
it did not qualify physical timing or hardware inference.

The final repository-wide Nix suite terminated at its 180-second bound in the
full pinned loader-shell BAR fixture, without a final suite result. Its durable
log is `kintex-postroute-final-nix-suite-20260928.log` in the artifact directory;
the suite is incomplete, not green. No standing diagnostic-commit approval is
assumed. No board programming or accelerator correction occurred. Next:
use the preserved physical diagnostic to localize the second-token mismatch,
including uncovered memory/DSP paths; do not select a compiler/RTL fix solely
from passing small regressions or the maximum route delay.

### Actual timing-coverage audit and reconstructed memory-path candidate

Running the existing `check_xilinx_chipdb_timing.py` against the exact routed
chipdb reports device `xc7k480tffg1156-1`, one speed grade, **zero timed tile
types**, 127 wire timing classes and 260 PIP timing classes. Its status is
`missing_cell_timing`, not timing closure. This is broader than the previous
BRAM/DSP-only disclaimer: ordinary LUT/carry delays also fall back to estimates.
No Vivado executable is available on the inspected PATH or under `/opt`.

The actual routed JSON contains 190 DSPs, all with AREG, BREG, CREG, DREG,
ADREG, MREG, PREG, ACASCREG and BCASCREG equal to zero. After decoding packed
input inversion against the actual constant nets, every DSP has effective
`(OPMODE, INMODE, ALUMODE) = (5, 0, 0)`, matching the pinned Yosys
`xc7_dsp_map.v` pure combinational 25×18 multiplier configuration. The SDF
contains empty cell blocks for these DSPs. No directly connected DSP-to-DSP
input bits were found; no cascaded arithmetic failure is inferred.

A read-only diagnostic reconstructs the complete directed graph from SDF
interconnect and non-FF IOPATH records, cuts FF clock-to-Q arcs, and seeds
only Q ports in the actual accelerator clock domain. For these known
combinational multipliers, it adds explicitly hypothetical **zero-delay**
A/B→P dependencies, respecting operand/product bit positions. It also computes
a route-only result with all cell delays set to zero. All 976,460 graph nodes
are topologically visited, and 13,926 same-clock D endpoints are reachable.
This is not vendor STA: DSP intrinsic delay, accurate cell delay, setup/hold,
clock skew and functional path sensitization remain unverified.

The longest SDF-estimated path does **not** traverse a DSP. It is:

`c_proj_weight_codes_i8.read_addr[5]` (`SLICE_X32Y251/DFF`) →
`c_proj` weight LUTRAM and selection muxes →
`c_proj_weight_codes_i8.mem$rdreg[0]$d[3]` (`SLICE_X49Y194/DFF`), whose Q
is named `c_proj_gemv_mac_right[3]`.

It totals **33.747 ns** with the exported fallback cell/clock-to-Q estimates,
against a 33.333 ns clock period. Interconnect alone totals **31.847 ns**;
no route-only endpoint exceeds the period. The largest segments on this path
are 15.900 ns into `mem.0.950/DPR1/A6`, 5.400 ns between selection LUTs, and
3.180 ns from an upstream mux to a selection LUT. This identifies a specific
weight-ROM address/read-data path for the next localization experiment, not
a proven physical violation or the first observed arithmetic mismatch.

No compiler, RTL, mapping, route, image or board change was made during this
analysis. Do not change DSPs merely because they are unregistered, and do not
select a ROM rewrite from the estimate alone. The next gate must bind this
candidate to the actual failing memory/arithmetic boundary or establish an
independently validated timing diagnosis before retaining a backend correction.

### Functional sensitization and the actual operand schedule

Further read-only inspection binds the slow leaf to the authenticated image,
but also finds an important reason **not** to select it as the hardware root
cause. The routed `mem.0.950/DPR1` RAMD64E INIT matches exactly one 64-word
bit plane of `image-c_proj_weight_codes_i8.hex`: base address 22784, bit 3.
This is layer 1, output channel 25. The real consecutive GEMV addresses
22815 and 22816 (input indices 31 and 32) contain codes 210 and 171,
respectively, so the bit changes from zero to one. The numbered physical
leaf name is not a reliable image-offset formula; the association is from
comparing the actual INIT against every image chunk and bit plane.

Sensitizing a ROM leaf does not establish a single-cycle capture deadline.
The unchanged normalized compiler SV establishes the following schedule:

- Top FSM state 317 enables `c_proj_gemv_read_operands`; the ROM output
  register captures only while this group is enabled.
- State 318 runs `early_reset_static_par_thread16`. At static counter 0
  it increments the GEMV input index. Activation scaling runs at counters
  0–2, the MAC at 3–5, and accumulation at 6. The static counter resets
  at 6 and the registered wrapper completion advances the top FSM to 319.
- State 319 evaluates the next input-index condition before re-entering
  state 317. No operand read is enabled during state 318 or 319.
- The memory address expression continuously reflects layer, output and
  input-index registers; it is not forced to zero outside the read group.
  `read_addr` samples it each clock, but `read_out` is enable-gated.

Thus the identified index-31→32 transition occurs early in an arithmetic
group, with several subsequent clocks before the next enabled ROM-output
capture. The graph's one-period comparison does not by itself demonstrate a
functional failure on this transition. This is source/control-schedule
analysis, **not** a physical capture observation, an executed timing
simulation, a validated multicycle constraint, or permission to weaken XDC.
Other address changes and paths still need their own launch/capture analysis.

The MAC primitive also needs schedule-aware analysis: the generated
`std_fp_mult_pipe` loads operand registers while `go` is high, computes a
registered product from their previous values, and holds that product when
`go` is low. The three-cycle MAC group can overwrite an initially invalid
product before accumulation. Merely observing unregistered DSP primitives
or a blank DSP SDF cell is not proof of an arithmetic failure.

No ROM/DSP rewrite, accelerator change, new route, programming operation, or
board inference occurred. The next useful experiment must observe an actual
incorrect capture or the earliest semantic boundary mismatch, or faithfully
execute an implicated mapped cone; it must not substitute source-pattern
checks or estimated single-cycle maxima for that evidence. The importer
checkpoint remains uncommitted pending the already-requested explicit
diagnostic-commit authorization; the incomplete broad suite is not treated
as passing.

### Executed mapped arithmetic-cone diagnostic

A bounded executable experiment now tests the **existing synthesized**
`c_proj` multiplier, rather than checking source strings or resynthesizing a
replacement multiplier. Yosys extracts the combinational input cone of
`$10466.Y` from the exact one-ROM production `dsp-final.il`, stopping at
operand registers. The extracted cone contains two DSP48E1 primitives,
31 LUT2s and eight CARRY4s. A second extraction adds the existing 48 output
FDREs and exposes their actual clock, reset and enable connections. Only
diagnostic port names are changed; the original production netlist is not.

Nix successfully rebuilds the extraction, compiles both harnesses with the
pinned Icarus package and pinned Yosys `xilinx/cells_sim.v`, executes both,
and requires deliberately corrupted observations to fail:

- Every signed INT8 coefficient is exercised against directed signed-40-bit
  activation boundaries and DSP split boundaries, followed by 10,000
  deterministic random operand pairs. All 12,816 low-48-bit products match
  independent signed multiplication.
- The registered cone matches the same arithmetic plus reset and enable/hold
  expectations through 11,537 cycles, including changing operands during
  disabled captures and reset with enable low.
- Each one-bit observation-corruption negative control exits 1 at its first
  comparison, while the corresponding uncorrupted run exits 0. These are
  checker sensitivity controls, **not** a reproduction of the board bug or a
  red/green accelerator correction.

The successful Nix output is
`/nix/store/fybipx1fa13sayygczw2zskidak4vn5j-tinystories-cproj-mapped-cone-diagnostic`,
derivation `ga6shgcya57ij27j3r0s1wvv8pdpwmsf`. Its `scope.json` identifies
the immutable production input
`/nix/store/5np658085kc0r8d7z5fkwahl89s4zi58-tinystories-two-token-mapped.il`
and tool packages. Extraction logs, generated mapped cones, harnesses,
execution logs and negative-control logs are retained in the output. The
recipe and its rooted `result` link are under the durable worktree artifact
directory `checkpoint-recovery-20260928/mapped-cproj-cone/`, not `/tmp`.
The initial ad-hoc extraction command selected an incorrect module name and
attempted to serialize library processes; that command failed and produced no
valid cone acceptance. The corrected Nix recipe is the authoritative replay.

These results reduce support for a basic functional mapping error in this
particular multiplier/output-register cone. They do not establish equivalence
for all multipliers or the full accelerator. Inputs are exercised at the
operand-register boundary, not replayed from an observed failing FPGA capture;
the input-register/control cone is excluded. Primitive simulation is
functional: no routed delays, bitstream configuration, clock skew or real
DSP/setup/hold timing is validated. The board result remains `[11,1375]`.
No RTL/backend fix, route, bitstream or board operation was performed.

### Complete mapped MAC data-path differential and feedback localization lead

The arithmetic diagnostic now also includes the actual 48 operand FDREs,
48 product FDREs and the LUT implementing their reset/`go` behavior. It
compares against `std_smult_pipe` instantiated from the unchanged normalized
production compiler SV, not a handwritten replacement multiplier. Every
coefficient is exercised in three-cycle `go` bursts at directed activation
boundaries; random changing operands, enables and resets are also compared
cycle by cycle. Products match through all 16,401 observed cycles, including
an independent signed-product assertion after each complete burst. The
corrupted-observation control fails at cycle zero. The unused synthesized MAC
completion signal and the outer scheduler are not validated by this cone.

This additional Nix build exits zero and is rooted at `mapped-cproj-cone/result-full`:
output `/nix/store/ym3ga2ny76rnw4503g2l5y6h9ig8ilxk-tinystories-cproj-full-mapped-cone-diagnostic`,
derivation `4zzxcqxwfwf1rr4024pzvpxhxzm6mjvi`. Its scope binds the exact mapped
input and the compiler-SV reference
`/nix/store/8chfnmvhp0gpxyixznavry7d3j4yp9bm-tinystories-two-token-production.sv`.
It covers functional primitive behavior, not routed delays or FPGA behavior.

The reconstructed SDF graph also checks actual context-memory boundaries.
All nine address-register sources reach all 64 data-register endpoints for
each inspected memory. Maximum fallback estimates are 5.847 ns for key
outputs, 5.863 ns for value outputs and 7.917 ns for block inputs. For driven
write-address/data/enable ports in those three memories, the maximum is
24.625 ns, launched from the CSR `start` register. These estimates do not
identify a period violation or qualify timing. Forty-eight connected memory
write inputs lack an output driver; the first investigated example is an
undriven `$const` net already present in the original checkpoint, not evidence
that the importer lost a driven connection. The analysis explicitly excludes
those from FF-to-input path estimates and fails on a missing **driven** SDF
endpoint. This is not a claim that undriven memory data is always harmless.

A more specific diagnostic result changes the next action. Running the
authenticated eager fixed-point model inside Nix with the unchanged prompt
tokens `[7454,2402,257,640]` gives:

| Appended token in diagnostic oracle | Selected next token |
| --- | --- |
| 11 — the correct FPGA feedback | 612 — frozen reference |
| 0 | **1375 — exact failed board result** |
| 5 — one-bit right-shift candidate | 1820 |
| 22 — one-bit left-shift candidate | 11 |
| 640 — repeated final prompt token | 11 |
| 7454 | 612 |
| 2402 | 257 |
| 257 | 1310 |

The correct-context control first reproduces 612. No perturbed tokens were
supplied to an FPGA; this is software-only fault-phenotype exploration.
The model package and HF snapshot are the same Nix-pinned inputs used for the
passing compiler simulation. Script and JSONL are retained as
`mapped-cproj-cone/feedback-perturbations.{py,jsonl}`. The script's first
invocation failed only on repository import-path selection; the corrected
bounded invocation exits zero. A matching argmax is not a unique fingerprint:
this does **not** prove that hardware stored or read zero or establish the
earliest hardware divergence.

The unchanged generated SV writes `model_best_token.out` to both token output
storage and `context_tokens[model_context_length]` in `model_commit_feedback`.
`context_tokens` is an 8×16 **FF-backed** `seq_mem_d1`, not the large weight
LUTRAM. The synthesized fourth-index word has 16 FDREs sharing one enable,
with reset tied low; they are distinct from the public first-token output
registers. Thus a public token-11 read does not prove the context write
succeeded. A targeted fallback SDF estimate across their D/CE/SR inputs gives
17.874 ns at the longest reachable endpoint, again launched from the held
`start` register; no physical violation is established.

Prioritize observing the value written/read at context index 4 and its
commit enable/address/data sequence, rather than rewriting multiplier or
weight-ROM logic. A dropped/zeroed feedback token is now a specific,
board-output-consistent hypothesis. Require an actual boundary observation
or faithful failure reproduction before retaining a fix. Hardware remains
unchanged; current board acceptance is still failed and the pending diagnostic
commit authorization has not been granted.

### Feedback configuration and fresh hardware polling experiment

The retained `mapped-cproj-cone/feedback-frame-audit.py` compares the routed
context-index-4 FDRE configuration against the independently decoded existing
bitstream file. All 16 FDREs across nine sites have the expected zero INIT,
synchronous positive-edge clock, active clock enable and unused reset encoding.
All 169 selected database feature checks match. This is a configuration-file
audit, **not** live FPGA readback or observation of feedback contents; it does
not establish that the registers received the intended write.

A hardware experiment now executes the unchanged failing two-token image
through the validated HS3/MPSSE transport. Transport source hashes match the
prior board receipts. The established isolation helper reports the exact Helios
already deauthorized with the endpoint absent; JTAG detects `0x23751093`,
Kintex-7 XC7K480T. Each run is independently SRAM-programmed, uses the frozen
four-word prompt and issues exactly one START:

| Host behavior during inference | Actual tokens | Elapsed seconds |
| --- | --- | --- |
| Normal status polling | `[11,1375]` | 6.338740 |
| No JTAG scans for eight seconds after START | `[11,1375]` | 8.124352 |

The measured quiet window is 8.000271 seconds. Both runs fail the expected
`[11,612]` checkpoint. The normal run observes one transient zero status;
the quiet run observes none. This experiment gives no support to frequent
status polling as the cause of the token mismatch. It does not identify the
first semantic divergence or prove zero feedback. No accelerator, compiler,
model, constraints, placement, route or bitstream change was made.

Script and receipts are retained under
`mapped-cproj-cone/quiet-jtag-experiment.py` and
`mapped-cproj-cone/quiet-jtag-hardware/`. The first runner attempt incorrectly
allowed only 90 seconds for each 18.7 MB SRAM image at 1 MHz, interrupting both
candidate programming and baseline restoration before inference. Those logs
are preserved separately as `quiet-jtag-hardware-timeout90/`; they are runner
failures, not accelerator evidence. After confirmed termination, the same
experiment was restarted with a bounded 360-second programming timeout.
The corrected runner exits zero after successfully restoring the accepted
first-token image. Its real checker returns token 11 in 3.206894 seconds;
the loader reports SRAM transfer complete and DONE/INIT asserted. Receipt
inspection confirms two failed candidate runs with one START each, the measured
quiet window, and the passing baseline control. The zero runner exit means the
diagnostic and restoration completed, **not** that two-token inference passed.

An investigation into direct state observation found a possible next step in
[AMD UG470, readback capture](https://docs.amd.com/api/khub/documents/FOs3lXmlcWxBhTIFxVKyGA/content),
pages 119 and 131: GCAPTURE can copy CLB register state into the configuration
cells used for INIT and allow subsequent readback without adding debug RTL.
This is not yet an implemented or validated diagnostic. Before relying on a
decoded feedback value, prove readback alignment and polarity using known-value
register controls, account for the dummy frame and command sequencing, and
avoid GRESTORE, which could restore captured values into live registers.
No capture command has been issued. The new evidence favors observing the
actual feedback registers rather than another speculative RTL modification.

### Executed configuration-capture observation

The proposed observation was subsequently implemented as an isolated hardware
diagnostic, not accelerator RTL. A read-only preflight successfully reads the
exact device ID `0x23751093` twice, STAT `0x04107afc`, and COR0 `0x02003fe5`
through the existing HS3 transport. This establishes configuration-register
bit alignment, not yet frame/state decoding.

The first capture correctly **failed** its predeclared known-register controls.
Its configuration-register helper reset the TAP after inference. Inspection
of the unchanged board top establishes that TAP reset also asserts system
reset, clearing public-token and CSR-prompt registers; context storage has
tied-low synthesized reset. Thus the diagnostic disturbed its own controls.
That attempt and its passing baseline restoration are retained separately in
`feedback-capture-hardware-tap-reset-contaminated/`. Do not treat it as an
accepted observation. An executed transport-sequence check verifies that the
corrected optional no-reset register-read path emits no TAP reset sequence.

The repeat preserves TAP state from inference through GCAPTURE. It then uses
the documented shutdown/frame-read procedure, with no FDRI writes or GRESTORE.
The six independently known control words all match under exactly one uniform
decoding polarity: public outputs 11 and 1375, and CSR prompts 7454, 2402, 257,
640. The snapshot then decodes context words 0–5 as:

`[7454,2402,257,640,11,1375]`

**The first generated feedback token is present at context index 4.** This
rules out the simple dropped/zero feedback-write explanation for this observed
run. It does not establish the value consumed at the embedding boundary or
identify the earliest semantic divergence. The second token remains wrong.

Hardware run 35131 exits zero only after the original candidate again fails
`[11,1375]`, the capture controls pass, and the accepted first-token SRAM image
is restored and returns 11 in 3.197515 seconds. All raw frame words, individual
FF/cell/site/bit bindings, original inference transactions, and restoration logs
are retained under `mapped-cproj-cone/feedback-capture-hardware/`. The accepted
image is live; no processes from this experiment remain running.

An additional offline decode attempt correctly reports absent frames rather
than inventing a value: `context_tokens.read_out` needs `0x0042289f`, and
`model_context_length.out` needs `0x0000221f` and `0x0040231f`. Retained script
`decode-extra-snapshot.py` and `extra-registers.json` report null values and
explicit missing frames. The next bounded observation should include those
frames and, where feasible, the registered token-address consumer. A
post-completion read-output alone may not prove the earlier consumed value,
because a subsequent write makes that output unspecified in generated SV.
Keep the same known-register controls and unchanged implementation.

### Expanded snapshot and executed embedding-multiplier fixture

The first validated seven-frame snapshot is preserved separately as
`feedback-capture-hardware-initial-seven-frames/`. A fresh bounded capture of
18 frames retains the same six known-register controls, again matches all of
them, and reports:

| Observed register | Value |
| --- | --- |
| First/second output tokens | 11 / 1375 |
| Context word 4 | 11 |
| Context length | 6 |
| Model-row counter | 8 |
| Context read output at completion | 0 |
| Retained token-embedding product | 650962 |
| Retained position-embedding product | 394581 |

The read-output zero is **not** proof that zero was consumed: the final feedback
write makes this output unspecified in generated SV. The row counter ending
at eight also means the retained products cannot simply be compared with
token-11/position-4 products. The position product exactly matches position
row 7, column 63: `33 × 11957 = 394581`, consistent with later padded-row work.
Source token row 0, column 63 has code 77 and scale 50074, whose product is
3855698. The compiler input hex independently contains upper byte `0x4d` at
bank 0, word 7 (`4df80cc306e9d2ee`). The observed token product 650962 equals
`13 × 50074`, but this arithmetic fingerprint is not yet proof of a corrupted
memory bit, an incorrect consumed operand, or the earliest active-path fault.
The additional operand-register decode explicitly reports absent token-operand
frames; position operands have already returned to zero by completion. Thus
post-completion operands cannot automatically identify the earlier multiply.

Hardware run 31626 terminates zero after the controls pass and the accepted
first-token SRAM image is restored and returns 11 in 3.203622 seconds. No
production accelerator, backend, transport, clock, constraints or bitstream
was changed. The expanded snapshot and raw frame data are in
`feedback-capture-hardware/`; `embedding-product-oracle.{py,json}` computes the
scoped scalar predictions directly from the pinned, authenticated package.

An actual mapped embedding multiplier diagnostic now executes two DSP48E1s,
23 LUT2s and six CARRY4s extracted from the unchanged synthesized design. The
first extraction selected a registered output and produced an empty module;
the corrected extraction starts at the evidenced output-register D alias
`$12975.Y`. The first arithmetic fixture then wrongly drove scale bits above
bit 16 even though the source mapped `rtmp[63:17]` are physically tied zero.
Its failure is a fixture-domain error, not a demonstrated Yosys defect.
All authenticated token-embedding scales range from 14525 to 105952 and fit
the real boundary. The revised fixture keeps the synthesized zero-bit
precondition; an explicit invalid-domain control still rejects violations.

Nix derivation `3kd9klwa68c4bxzz7bga1zmf7m99pd8b` completes and produces
`/nix/store/ld8frrakki9hahhlsdgvab4gg3din8ib-tinystories-embedding-mapped-cone-diagnostic`,
rooted as `mapped-cproj-cone/result-embedding`. Executed simulation matches
signed integer multiplication across all INT8 coefficients at valid directed
scale boundaries and deterministic random inputs, including `77 × 50074`.
Deliberately corrupting the observed result fails immediately; the invalid
cutpoint-domain control also fails. This proves the scoped combinational
mapping behavior, not clocked scheduling, memory correctness, physical timing,
configuration, or inference. Do not claim that it reproduces the hardware
mismatch. Next prioritize a faithful memory/operand observation or simulation
before applying a compiler, ROM or DSP fix.
