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
