# Task 1 report: TinyStories-1M reference contract

## Result

Committed the machine-readable contract, strict loader test, and public result
note. The contract freezes the inspected kev-gpt TinyStories-1M package identity,
GPT-Neo dimensions, tokenizer and quantization representation, wire command ABI,
fixed prompt, and exactly 16 greedy output IDs.

## Evidence used

The package was inspected at
`/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m`.
Its `receipt.json` verified the recorded manifest, weight, scale,
calibration-image, and tokenizer asset hashes. The 16 output IDs were produced
by the package's `tinystories.int_reference.IntegerGPTNeo` for prompt IDs
`[7454, 2402, 257, 640]`; no values were inferred from unrelated compiler
fixtures.

## Validation

`nix develop -c python -m unittest -v tests.test_tinystories_1m_reference_contract`
passes (2 tests). JSON parsing and `git diff --check` pass. The brief's exact
pytest command was also attempted, but the pinned environment does not provide
the `pytest` module (`No module named pytest`); unittest is used by the focused
test and is the available pinned-environment runner.

## Explicit blocker

The contract status is `incomplete` because no reproducible one-stream
TinyStories-1M timing/resource receipt was found. Existing kev-gpt README
figures describe other multi-stream configurations and are intentionally not
relabelled as the required baseline. Baseline fields therefore remain null and
must be measured before compiler efficiency or waste-map conclusions.

## Commit note

The worktree had a pre-existing staged modification to
`docs/superpowers/specs/2026-08-28-reference-guided-tinystories-1m-compiler-design.md`;
Git included it in the commit when the scoped files were staged. Other dirty
changes remain untouched.
