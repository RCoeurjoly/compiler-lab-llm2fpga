# Compiler DDR3 placement-path diagnosis

This is **placement-estimated timing**, not routed timing, a usable bitstream,
or hardware inference acceptance. The original seed-15 routing job was still
running when this diagnosis was recorded. No production RTL, transport, clock,
constraint or tool pin was changed for this experiment.

## Evidence

The diagnostic placement completed with exit status 0. Its reported placement
costs and six clock-frequency estimates match the original routing run's
placement stage. Detailed failing paths and all six estimates are preserved in
`artifacts/diagnostics/2026-09-17-shared-ddr3-simulation/static-wait-placement-paths.log`.

| Clock | Estimate | Required | Named path |
| --- | --- | --- | --- |
| rowstream_clk | 18.43 MHz | 83.33 MHz | compiler context_tokens_read_data[8] through token_weight_codes_i8_b0_addr0[6] to memory_arbiter.last_grant_group[3] |
| pcie_user_clk | 58.16 MHz | 62.50 MHz | pcie_ingress.ingress.wdata_q[17] to m2_full_block_input_vector_o[364] |

The rowstream path is estimated at 54.2 ns: 4.3 ns logic and 50.0 ns estimated
routing. The PCIe path is estimated at 17.2 ns: 2.0 ns logic and 15.2 ns
estimated routing. These estimates do not establish actual routed delays.

Source inspection links the rowstream path to the compiler external-memory
request boundary: `seq_mem_d1_external.ext_req_valid` includes the combinational
comparison `response_index != addr0`, and the arbiter derives group selection
and `last_grant_group` from these request-valid bits. This identifies a concrete
path to investigate; it does not prove a specific pipelining change correct or
sufficient. Any later fix needs request/response, scheduler and exact-token
regressions, plus a new synthesis and routed timing result. Do not change the
validated PCIe or DDR3 implementation based on these estimates alone.

## Reproduction and provenance

Production nextpnr derivation:
`/nix/store/g138pa95pn2iw34rddxjdjfp2f99vpa3-nextpnr-xilinx-0.8.2.drv`.
Diagnostic derivation:
`/nix/store/fc75my8285h9bkcbwcqf0l2qpzpiq8w3-nextpnr-xilinx-0.8.2.drv`.
Both use `/nix/store/rzmrkc8aff649333zc7rfc6pdzmsimqy-source`.
The derivation environment comparison differs only in the output path and this
diagnostic postPatch replacement in `common/placer1.cc`:

```cpp
// Original:
timing_analysis(ctx);
// Diagnostic:
timing_analysis(ctx, true, true, true, false);
```

This enables `print_path`; histogram, fmax and warn-on-failure retain their
original default values. The diagnostic tool was built under a 1,800-second
timeout, two build cores, one Nix job. Its executable is
`/nix/store/hjlrgmcpj3g17r6d8z700v791q0g1vv3-nextpnr-xilinx-0.8.2/bin/nextpnr-xilinx`.

The placement diagnostic used the arguments and immutable inputs in
`static-wait-route-launch.json`, but the diagnostic executable, `--no-route`,
no `--fasm`, and a separate `--write` destination. Its timeout was 1,800 seconds.
It retained `--placer-budgets --router router1 --seed 15`, the original XDC,
chip database and pre-pack script. No timing-allow-fail or no-tmdriv override.

Input netlist SHA-256:
`7c0d56a27079c02afd41fc9926c97f88c7508b9cae594526e6dd61ad326457cc`.
Full diagnostic log SHA-256:
`719e18f0c743dba82f043d583f98b886d25a6c12d01fbf7378eb21459dd69abf`.
Placed diagnostic JSON SHA-256:
`955206c8117c45b306e759a7e5619340b4fd2080647cab4d36efaf4b675abb4e`.
The full log/JSON remain temporary at
`/tmp/compiler-ddr3-current.2Z9Mo4/static-wait-placement-diagnostic.{log,json}`;
the tracked excerpt preserves log lines 1395–1523 and 1614–1619. Neither the
placed JSON nor its exit status is timing acceptance.

## Subsequent original-tool routed result

The original, unmodified nextpnr job subsequently finished routing in
10,255.74 router seconds and exited **1**, not a timeout. It reports
**26.39 MHz, FAIL at 83.33 MHz** for `rowstream_clk` and **90.97 MHz, PASS at
62.50 MHz** for `pcie_user_clk`. The PCIe placement estimate was therefore not
a routed failure; do not modify the validated PCIe transport based on it.

The routed rowstream path confirms the same region as the placement diagnosis:
`context_tokens_read_data[13]` through `token_weight_codes_i8_b0_addr0[6]`
to `memory_arbiter.last_grant_group[0]`, totaling **37.9 ns** (3.9 ns logic,
34.0 ns routing), against a 12 ns period. The exact path and result are in
`static-wait-routed-paths.log` and `static-wait-route-result.json` in the
diagnostic artifact directory. The source/destination bits differ from the
placement-estimated worst path; the compiler request-to-arbitration dependency
is the same. This is now routed evidence, not just a placement hypothesis.

The tool emitted FASM and routed JSON despite timing failure. Their hashes are
recorded for diagnosis, **not approval to convert or program**. No bitstream
was generated or programmed. Covered-path PCIe success is not a claim of full
PHY/CDC timing coverage. The next implementation experiment must address the
compiler request path while retaining exact memory-response semantics and the
validated PCIe/DDR3 transport, clocks and constraints.

## Registered-request experiment (not timing acceptance)

The next candidate changes the compiler externalization pass's emitted
`seq_mem_d1_external` primitive: it snapshots the byte address and element
index before asserting a registered request-valid signal. A queued request
remains stable until accepted or reset, even if the client inputs change.
The response byte offset is captured from that registered address at
acceptance. The arbiter, command adapter, DDR3 and PCIe are unchanged.

The focused 14-test external-memory suite passes, including a new behavioral
test for registration, backpressure, changing live addresses, response-byte
selection and queued-request reset. The new registration assertion failed
against the previous combinational primitive. Regeneration of the complete
model changes only this primitive, not the arithmetic or scheduler bodies.
Candidate generated-SV SHA-256:
`75cd4d642a66e50f762a40741e3e42b0bf48f768ced5549226ac13dd81bb0338`.

This introduces an additional request-capture cycle. Full-model first-token
simulation and new implementation timing are still required; the unit tests
do not establish either. The prior passing simulation and failed routed
candidate are preserved separately. No replacement bitstream is qualified.

### Candidate placement result

The registered-request placement-only diagnostic completed with exit 0.
Its rowstream estimate is **30.58 MHz, FAIL at 83.33 MHz**, compared with
18.43 MHz for the preceding placement-only baseline. This is an improvement
in placement estimates, not routed timing closure. PCIe estimates 47.54 MHz
against 62.50 MHz; as the baseline demonstrated, this does not establish a
routed PCIe failure.

The worst rowstream path now starts at `context_tokens_read_data[15]` and
ends at `$auto$ff.cc:337:slice$205084.CE`, totaling 32.7 ns (2.3 ns logic,
30.4 ns estimated routing). Synthesized-netlist bit mapping identifies the
sink register's Q as `token_weight_codes_i8_b143.queued_address[5]`.
The reported limiting path is therefore upstream of the new request
register, not the former arbiter grant-register endpoint. The next source
investigation is the compiler bank-selection/scheduler-to-request-capture
enable cone; this result alone does not authorize an untested RTL change.

Exact rowstream/PCIe paths and clock estimates are preserved in
`registered-request-placement-paths.log` (full-log lines 1388–1465 and
1553–1558). Full log SHA-256:
`2437647ac8d5cb8572327075b639e522a26861c0e884913095fb13452c3536a9`.
Placed JSON SHA-256:
`da5af84a1c2344e54bfb671af00eee394153168cfe8363223d030e379f280a1d`.
Both full artifacts remain under `/tmp/compiler-ddr3-current.2Z9Mo4/` as
`registered-request-placement.{log,json}`. The run used the same diagnostic
nextpnr executable, XDC, pre-pack, chip database, seed 15, placer budgets and
`--no-route` settings as the preceding placement diagnostic, with the new
netlist recorded in `registered-request-synthesis-result.json` and separate
output paths. Full-model simulation is still pending; no route was launched.

### Source-level follow-up

The generated candidate has a combinational `model_read_token_codes_done_in`
expression selecting completion across banks b0–b196. Its `done_out` is a
`std_wire` alias, and `model_read_token_codes_go_in` is
`~model_read_token_codes_done_out & fsm0_out == 9'd13 & tdcc_go_out`.
That go signal controls bank address muxes and selected content enables,
including bank b143, whose queued-address capture enable is the reported
placement endpoint. The bank selector itself comes from context-token bits.

`latch_external_memory_completion_joins` explicitly skips expressions with
fewer than two top-level AND operands. The selected-bank OR expression is
one such operand, so token lookup bypasses completion registration. By
contrast, the LM-head operand group has three operands and already uses
`llm2fpga_lm_gemv_read_operands_completion_seen` registers.

The next bounded hypothesis is to register this selected-completion result
with the same reset/rearm discipline. This must retain selected-bank
qualification (not accept arbitrary bank completion), reject stale responses
outside the active group, preserve the returned data until consumption, and
handle repeated groups and reset. It requires a failing behavioral fixture,
regression tests, full-model equivalence and a new timing measurement. No
additional RTL change has been applied on the strength of this hypothesis.

### Selected-completion test-first candidate

The subsequent behavioral fixture failed against the previous pass with
`selected completion bypassed register`. The narrow change exempts only
`model_read_token_codes_done_in` from the single-operand skip, using the
existing completion register/reset/rearm mechanism. All 15 focused
external-memory tests pass, including selected/unselected responses, inactive
responses, repeated groups and reset. This is a request-control timing
experiment, not a change to model arithmetic, PCIe or DDR3.

Regenerating from the same accepted compiler input changes only this one
completion assignment into the registered predicate. Candidate SHA-256:
`eefbc34e60006e01f7d33b405298d6cea5c3bb122552fa338665b34db5c948cf`.
Its full-model simulation and implementation timing have not been qualified.
The preceding registered-request simulation continues with its unchanged
executable; its result must not be attributed to this newer candidate.

### Selected-completion placement and route launch

The placement-only diagnostic completed with exit 0 and estimates
**36.28 MHz, FAIL at 83.33 MHz** for rowstream, and **50.96 MHz, FAIL at
62.50 MHz** for PCIe. Rowstream improved from the preceding 30.58 MHz
estimate, but neither estimate establishes routed timing.

The new worst rowstream path is `fsm0.out[8]` to
`$auto$ff.cc:337:slice$203293.CE`: 27.6 ns total, 1.6 ns logic and 26.0 ns
estimated routing. The synthesized endpoint Q maps to
`token_weight_codes_i8_b47.queued_address[13]`. This is the compiler FSM to
request-capture enable path, not the preceding context-token bank-selector
path. No additional compiler modification has been made from this estimate.

`selected-completion-placement-paths.log` preserves full-log lines 1390–1452
and 1555–1560. Full log SHA-256:
`c23576e0c5fbecaea6ea6e1c62c202126bb235f7ba50dbb58d21d5d0ce4f46d0`.
Placed JSON SHA-256:
`a66f4fd561781e4fbda549d8e5709d564c2523a9d2abc37c6a3d637012e423da`.
The full files are `/tmp/compiler-ddr3-current.2Z9Mo4/selected-completion-placement.{log,json}`.

The unmodified pinned router was launched on the same synthesized candidate
to obtain routed timing before choosing another change. Exact command and
input/constraint identities are in `selected-completion-route-launch.json`.
It retains seed 15, router1, placer budgets, original clocks/XDC/pre-pack,
and a 10,800-second timebox. No allow-fail flag, relaxed constraint, alternate
seed or hardware operation. Both compiler-candidate simulations were still
running at launch. Any emitted FASM remains unqualified unless both actual
routed timing and the corresponding full-model functional gate pass.

### Selected-completion terminal outcome

The route session 95952 terminated with exit **124** at the unchanged
10,800-second deadline. The final routing progress line reports 10,427.06
router seconds; placement and other stages also consume the overall deadline.
Neither requested routed FASM nor routed JSON exists. There is **no final
routed timing result**. The frequency reports earlier in the log remain
placement estimates and must not be presented as routed timing.

`selected-completion-route-result.json` records the terminal outcome and full
log hash. The separate `selected-completion-result.json` records the completed
first-token simulation (token 11, 13,116,912 matched requests/responses), using
simulated memory rather than physical DDR3. No bitstream conversion or board
programming occurred. This supersedes the historical running statuses above.

Next investigation: inspect the compiler FSM-to-request-capture control path
identified by placement and its fanout before selecting another compiler
change. The timeout alone does not establish that path as the final routed
critical path, nor justify changing clocks, DDR3, PCIe, or seed. No automatic
longer retry or additional RTL fix has been launched.
