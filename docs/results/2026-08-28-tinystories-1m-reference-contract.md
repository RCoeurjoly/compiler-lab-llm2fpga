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

## Deliberate blocker

The contract is marked `incomplete`: no reproducible one-stream hardware
timing/resource receipt was found. Existing kev-gpt README figures describe
multi-stream fabric configurations and are not silently relabeled as the
required one-stream TinyStories-1M baseline. A later task must add that receipt
before efficiency or waste-map conclusions are drawn.

The package directory is an external inspected checkout, not copied into this
repository. Its receipt contains an exact hash for every package file; the
contract preserves those identities without fabricating a repository-local
artifact or measurement.
