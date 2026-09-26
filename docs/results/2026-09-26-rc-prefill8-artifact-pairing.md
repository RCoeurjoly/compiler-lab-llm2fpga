# RC prefill-8 artifact-pairing diagnostic

Status: **not qualified**. This run does not establish RC prefill equivalence.

The canonical `run_rc_serving_w4a8_sv.py` harness was run against the exact
resolved reference package and the existing native-Calyx prefill artifact:

- SV: `/nix/store/assf2zarkj7w8rvwvaxi3f8v6wimq1ig-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-calyx-native-sv/sv/main.sv`
- flat-SCF: `/nix/store/hnrx9lj23ay9vrd2glxn8msc7ak3yh81-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-flat-scf/flat.scf.mlir`
- exported/reference package: `/nix/store/yr0xlymj4zkg2mhwf0j4gaf107dc13yl-tinystories-w4a8-rc-serving-mask10-vocab6-width2-prefill-8-pytorch-exported`
- report: `/tmp/rc-prefill8-authenticated/report.json`
- report SHA-256: `a335bdd38dafcd91d97c58451a73890f7a481fdcd33249ccbda254b253065a47`

Compilation completed in 386.04 seconds and simulation completed in 581.90
seconds. The harness returned `status=mismatch`; all five observable outputs
differed. Maximum absolute errors were 0.04525--0.06208, so this is not a
rounding-tolerance issue. The result is not promoted to an equivalence receipt
because the native-SV artifact is not proven to be generated from the same
backend snapshot as the flat-SCF/reference package.

The newer native-Calyx variant was then tested with the same flat-SCF and
reference package. Parallel `-j4 -O3` compilation was killed by the host
(`cc1plus`), so it was retried with `-j1 -O0`. That compile succeeded, but its
simulation exceeded the 900-second bound without producing `done` or output
files. This is a bounded runtime failure, not a semantic pass or mismatch.

## Consequence

The RC prefill phase is currently an evidence gap. Decode-8 and decode-9 have
independent bit-exact receipts, but prefill does not. Before composing the RC
or attempting hardware, the pipeline must make the phase artifacts
content-addressably paired (same flat-SCF/backend inputs) and either:

1. produce a bit-exact prefill receipt; or
2. localize the first prefill divergence with a bounded trace.

No PCIe, DDR3, synthesis, P&R, bitstream, or board claim is made from these
runs.
