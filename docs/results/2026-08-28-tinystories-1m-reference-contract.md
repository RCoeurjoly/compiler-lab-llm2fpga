# TinyStories-1M reference contract (2026-08-28)

This contract records the inspected kev-gpt TinyStories-1M package before any
compiler comparison. The package manifest, tokenizer assets, quantized memory
images, command framing, prompt fixture, and 16-token integer-reference output
are recorded in `artifacts/reference/tinystories-1m-kev-gpt-contract.json`.

The inspected package is GPT-Neo with eight layers, hidden width 64, sixteen
heads (head dimension 4), vocabulary 50,257, and a 32-token hardware context.
The package uses symmetric per-output INT8 weights, symmetric INT8 activations,
INT32 accumulation, and little-endian float32 scale images. The exact package
and tokenizer file digests are retained in the JSON artifact.

The fixed software fixture is `Once upon a time`, token IDs
`[7454, 2402, 257, 640]`, followed by greedy IDs
`[11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375, 6151, 284, 711, 2354, 287, 262]`.

## Wire ABI

`command_abi` is an executable data definition, rather than a prose-only
description. It assigns `infer` the unsigned-8-bit command value `1` and `ok`
the unsigned-8-bit reply-status value `0`. Every scalar is byte-aligned,
unsigned, and little-endian; no bit-packed fields are permitted (`bit_order` is
`lsb0`). Request magic is the little-endian `u16` value `19271` (`0x4b47`), and
reply magic is `19282` (`0x4b52`).

The request header is six bytes followed by `prompt_count` little-endian `u16`
tokens and then the CRC trailer: its total byte length is
`10 + 2 * prompt_count`. `prompt_count` and `generation_count` are each in
`[1, 32]`, and their sum may not exceed 32. The reply header is thirteen bytes
followed by `token_count` little-endian `u16` tokens and the same trailer: its
total byte length is `17 + 2 * token_count`. A successful reply has exactly the
requested generation count.

The trailer is an unsigned little-endian `u32` immediately after the variable
token payload. It is CRC-32/IEEE (reflected polynomial `0xedb88320`, initial
and final XOR `0xffffffff`); coverage starts at byte zero and ends immediately
before that trailer. The JSON records offsets, widths, count bounds, and length
formula operands as structured fields so a consumer can construct and validate
both frame types without interpreting narrative text.

## Deliberate blocker

The contract is marked `incomplete`. No reproducible TinyStories-1M reference
trace artifact was found, so its digest remains explicitly unavailable. No
reproducible one-stream hardware timing/resource receipt was found either.
Existing kev-gpt README figures describe multi-stream fabric configurations and
are not silently relabeled as the required one-stream baseline. A later task
must add these receipts before trace-based equivalence, efficiency, or waste-map
conclusions are drawn.

The package directory is an external inspected checkout, not copied into this
repository. Its receipt contains an exact hash for every package file; the
contract preserves those identities without fabricating a repository-local
artifact or measurement.
