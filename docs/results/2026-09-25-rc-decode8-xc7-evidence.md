# RC decode-8 implementation-gate diagnostic

Status: implementation gate stopped at Yosys timeout; no P&R or bitstream
claim.

The input is the canonical compiler-generated W4A8 Representative Core
decode-8 snapshot, whose decompressed SystemVerilog SHA-256 is
`62255f24c12c11b699c972b824fb2cb4119d94f733d57124117b9c00a5e18fa6`. The
synthesis frontend normalizer completed and produced normalized-SV SHA-256
`156a23f93b3ccff8a80ef49c2c08fe5b4cbf29329aa9ac2f91d9b2410748f08b`.

The Nix evidence derivation completed with durable output after the flow fixes
in commits `1e15681`, `1311e6a`, `32326e2`, and `5f22297`:

- the diagnostic XDC is materialized inside the derivation;
- canonical gzip snapshots and local scripts are rematerialized under fresh
  store names, avoiding stale zero-byte Nix paths;
- Yosys and nextpnr each have a 600-second bound;
- the receipt survives a tool timeout.

Observed result:

```text
yosys-status.txt: 124
nextpnr-status.txt: not-run: Yosys mapped JSON was unavailable
fit: undetermined
timing: unavailable
```

The bounded run therefore establishes a current implementation bottleneck in
Yosys on this generated phase, before mapping or placement. It does not
invalidate the previously recorded bit-exact compiler/RTL simulation result,
and it does not claim PCIe, DDR3, bitstream, or board inference.

## Pass-localization experiments

Two temporary replays used the exact normalized source and the same synthesis
script:

1. Removing only the explicit post-techmap `alumacc` pass still timed out
   after 700 seconds, during the following optimizer work on about 406,000
   cells.
2. Removing both post-techmap `alumacc` and `opt` progressed farther, into
   Xilinx memory library mapping, but also timed out at 700 seconds.

Therefore no single post-techmap pass is yet proven to be the sole blocker.
The evidence points to the representation/scale of the generated netlist and
the later memory-mapping stage. These experiments remain diagnostic; no
semantics-changing pass omission has been adopted as a production flow.
