# Generated TinyStories-1M memory-liveness diagnostic

This is a compiler-output diagnostic, not a fit or inference receipt.  It was
run against `/tmp/llm2fpga-current16/model.futil` (SHA-256
`d17e45c36e2fd7f984a904b14eaa98bc369c1caf48ca7ad48ddcbc2eb0df0366`) after
the 16-step generation geometry was emitted.

## Evidence

The generated component declares 124 external `seq_mem_d1` memories containing
39,051,904 logical bits.  The generated SV's BRAM annotations cover
38,156,288 bits, a lower bound of 1,036 RAMB36-equivalents.  The XC7K480T
reference capacity is 955 RAMB36 blocks.  This lower bound already exceeds the
device, before packing overhead and before accounting for logic or routing.

A conservative lexical liveness walk over the Calyx control schedule found a
peak of 29,868,352 simultaneously live logical bits (37 memories).  The walk
does not prove dynamic exclusivity inside loops; it is therefore evidence for
where to investigate, not permission to alias memories.

The largest non-weight live ranges are the attention buffers
`attention_score_q8`, `attention_delta_q8`, and `attention_exp_q1_20` (each
409,600 bits), and the MLP buffers `c_fc_*` (up to 327,680 bits each).  The
weight banks remain live across the model run and are not scratch candidates.

The walk also identifies shape-compatible, non-overlapping candidates that are
worth checking against explicit producer/consumer dependencies:

* `block_input_q16_16` (1,280 x 64 bits) versus `final_output_q16_16` and
  `lm_input_q16_16`;
* `ln1_output_q16_16` versus later 1,280-element activation/accumulator
  buffers;
* 512-element scale/bias buffers whose uses are confined to one projection.

Interval coloring of the lexical ranges (still not a correctness proof) gives
6,332,416 bits of theoretical reuse across all equal-shape memories, or about
172 RAMB36-equivalents.  This includes immutable weight declarations whose
contents would need an explicit packed-address layout, so it is an upper bound,
not an expected saving.  Excluding the two 131,072-deep INT8 weight memories
and the four token-scale banks leaves approximately 4,751,360 bits (about 129
RAMB36-equivalents) of scratch/intermediate reuse opportunity.  If dependency
analysis confirms most of that opportunity, the BRAM lower bound could fall
below the device capacity; this is the first evidence that a compiler memory
planner may be sufficient without changing quantization or adding DDR3.

These pairs are only lexical candidates.  A compiler memory-planning pass must
prove last-use and first-use ordering from the IR, preserve every checkpoint,
and emit a changed provenance receipt before any storage alias is accepted.

An earlier bulk-alias mismatch receipt is invalidated: its SV was generated
from a stale conversion and did not match the current Futil-to-SV preparation.
The current candidate path must always bind the Futil and SV hashes before a
semantic result is interpreted.

## Consequence

The current generated architecture cannot meet the BRAM-only objective by
placement or seed tuning alone.  The next compiler experiment should be an
IR-level lifetime/reuse transformation, followed by exact semantic simulation
and the same matching synthesis/mapping probe.  No RTL hand-edit, DDR3 change,
or transport change is justified by this diagnostic.

The out-of-tree analysis helper is
`scripts/pipeline/plan_calyx_memory_reuse.py`.  It is analysis-only by design;
its alias rewrite helper was checked on a synthetic Futil fixture and one
temporary generated-Futil alias, and the pinned Calyx compiler accepted that
temporary source.  This validates the mechanical rewrite path, not the
semantic safety of any particular alias.
