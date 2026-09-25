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

A bounded pre-memory-map replay completed in about eleven minutes and
captured the first Xilinx-mapped statistics before the expensive memory
library pass. The top module contained 313,593 cells, 1,241 memories,
101,931 mux cells, 68,971 OR cells, and 266 DSP48E1 cells. This confirms that
the dominant cost is the compiler-generated control/data representation, not
PCIe or DDR3 integration. The temporary JSON backend probe itself stopped on
an FDCE primitive-process limitation; the statistics remain valid because they
were emitted before that probe.

A third replay passed `-nobram` to the final `synth_xilinx -run
map_memory:` stage. It also timed out at 700 seconds, this time while
entering `MEMORY_LIBMAP` for LUTRAM-only legalization. Disabling BRAM
selection is therefore not a sufficient workaround; the mapping cost is
driven by the number and shape of generated memories, not one physical-memory
family.

A fourth replay restricted `memory_libmap` to the Xilinx LUTRAM library only
(with the BRAM library and its candidates removed). It still timed out at 700
seconds while entering `MEMORY_LIBMAP`. Candidate-library breadth is therefore
not the primary cause; reducing the number/shape of memories before Yosys is
the next evidence-backed direction.

## Packed done-buffer normalization

The synthesis frontend now rewrites the six generated declarations of the
form `logic done_buf[1:0]` to `logic [1:0] done_buf`. Bit-select semantics are
unchanged, but the packed form prevents Yosys from importing each pipeline
pair as a separate memory. The focused frontend suite passes, and Yosys-Slang
AST elaboration of the transformed RC passes with zero errors and warnings.

The bounded synthesis replay still reaches `MEMORY_LIBMAP` and times out, so
this is a validated representation improvement but not yet a complete mapping
fix. Its transformation receipt reports `packed_done_buf_repairs: 6` and
output SHA-256
`6d095664c791bf2797b86c6d0f062a4087bc7fc7670404b5b130e3bfd44670b8`.

The packed pre-map replay quantified the effect: memories fell from 1,241 to
160, memory bits from 20,284 to 18,122, and cells from 313,593 to 308,188.
The remaining 160 memories correspond to the external RC memory ABI
(`$memrd_v2`/`$memwr_v2`: 160 each). The normalization therefore removed the
internal pipeline-state memories; the remaining implementation cost is now
concentrated in the intended external memories and their control logic.

## Global block-RAM mapping experiment (rejected)

As a bounded tool experiment, the packed normalized source was copied to a
temporary workspace and every generated `seq_mem_d1` declaration was given
`(* ram_style = "block" *)`. The production source and compiler contract were
not changed. The replay used the same Xilinx synthesis script, with the
post-techmap `alumacc` and `opt` omissions used by the preceding diagnostic
replays.

Yosys entered `MEMORY_LIBMAP` and honored the attribute, but then failed on
the generated memory `main.mem_128.mem` with:

```text
ERROR: no valid mapping found for memory main.mem_128.mem
```

This is evidence that a global block-RAM directive is not a valid legalization
strategy: at least one generated width/depth shape is incompatible with the
available Kintex-7 block-RAM templates. The experiment produced no mapped JSON,
so it did not reach nextpnr and changed no repository RTL. The next tool-level
direction is selective legalization (choose BRAM only for compatible shapes,
LUTRAM or reshaping for the rest) or compiler-side memory-shape consolidation.

## Selective memory-style pass (compiler-side candidate)

The new `annotate_compiler_memory_styles.py` pass implements that policy as an
auditable transformation rather than a global pragma. It annotates only
`seq_mem_d1` instances whose width is compatible with a 7-series BRAM mode,
whose depth is at least eight, and whose total storage is at least 256 bits.
Tiny or irregular memories remain unconstrained so Yosys can choose LUTRAM or
registers. On the packed decode-8 source this selects 31 of 165 instances and
leaves 134 unconstrained. The pass emits a SHA-256 receipt and has focused
unit coverage. Yosys-Slang elaboration of the transformed source completed with
zero errors and warnings. It is not yet wired into the production Nix gate;
that integration remains contingent on a bounded synthesis replay showing a
real mapping improvement.

The candidate was replayed with the redundant full `opt` immediately before
`map_dsp:coarse` removed (the required `opt -nodffe -nosdff` cleanup was kept).
That bounded 420-second run reached `SYNTH_XILINX`'s `MEMORY_LIBMAP` stage;
the previous run spent the whole bound in the optimizer. It still timed out
inside memory legalization and emitted no mapped JSON, so the change is
diagnostic rather than an accepted production-flow modification. The evidence
supports separating the optimizer and memory-library timeboxes and evaluating
the selective annotations with a longer, independently bounded mapping stage.

The selective pass was then extended to scalarize all 32 one-entry
`seq_mem_d1` instances (including the previously failing `8x1` shape) into a
same-ABI `seq_mem_d1_scalar` register implementation. Yosys-Slang elaboration
still passes with zero errors and warnings. The 420-second replay reached
`MEMORY_LIBMAP` but timed out at the same frontier, so one-entry memories are
not the dominant remaining cost. The scalarization remains a valid
representation cleanup; the unresolved blocker is the legalization of the
remaining multi-entry memories and the mapper's search over their shapes.

Finally, Yosys's `memory_libmap -no-auto-block` option was tested with the
correct pinned Series-7 library files and the same scalarized candidate. The
run still reached `MEMORY_LIBMAP` and timed out after 420 seconds, without a
mapped JSON. Disabling automatic block selection is therefore not a sufficient
tool fix; the production synthesis script remains unchanged.

### Replay-order correction and persistent checkpoint

The first selective replays above were run from the pre-packed temporary
source, so their mapping-frontier comparisons are not authoritative for the
production candidate. They are retained only as diagnostic tool experiments.
The corrected order is: frontend normalization (including packed `done_buf`),
then selective style/scalar legalization. That source elaborates cleanly and
its pre-memory-map flow completed in 417 seconds, writing a 594 MiB RTLIL
checkpoint. Mapping that checkpoint independently still timed out in
`MEMORY_LIBMAP` after 420 seconds while enumerating LUTRAM candidates.

An explicit-only diagnostic (`-no-auto-block -no-auto-distributed`) completed
memory lowering quickly, but produced 522,890 generic cells and no usable
implementation result; it is a resource-explosion fallback, not an accepted
flow. The checkpoint establishes the next fast-iteration boundary: future
Yosys mapping/tool patches can be evaluated without repeating the 417-second
front half.

The persisted-checkpoint inspection adds an important Yosys detail: with
`-no-auto-block -no-auto-distributed`, `memory_libmap` completes in about
nine seconds, but leaves 90 `$mem_v2` memories and emits no BRAM/LUTRAM cells.
The earlier Verilog `ram_style` annotations are not preserved as actionable
placement metadata after `memory -nomap`/memory collection. Therefore a
production fix must reattach placement intent at the RTLIL `$mem_v2` stage (or
teach Yosys to classify those memories by width/depth); adding more source
attributes alone will not constrain the mapper.

Lowering the remaining memories immediately with `memory_map` is only a
diagnostic fallback: it completes quickly but produces 522,890 generic cells,
far beyond a useful Kintex-7 implementation. No bitstream or P&R claim is
made from that fallback.
