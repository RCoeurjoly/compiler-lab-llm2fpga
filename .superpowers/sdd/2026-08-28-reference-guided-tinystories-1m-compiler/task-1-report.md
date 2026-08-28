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

## Fix round

The loader now validates required nested fields and types for model identity,
all package file hashes, tokenizer vocab/merges hashes and boolean settings,
quantization scale-image hash, memory-image size, every ABI field, reference
fixture types, and baseline metadata. Regression coverage mutates representative
nested hashes and ABI values and confirms fail-closed behavior.

No reproducible trace artifact was available in the inspected package or this
repository. The contract therefore retains `reference_trace_sha256: null` as an
explicit unavailable-evidence field; the report does not invent a digest.

Fix-round validation command (pinned environment):
`nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_reference_contract.py' -v`
passes all 3 tests. Pytest remains unavailable in the pinned environment and no
dependency was added.

The fix-round loader checks all required nested fields and value types, including
model dimensions/metadata, package origin and every package-file digest,
tokenizer settings plus vocab/merges digests, quantization and scale-image
digest, memory-image size, complete ABI framing, reference metadata and
null-or-digest trace field, and baseline status/value types. Three regression
tests pass, including fail-closed mutations of nested hashes and ABI values.

The final strict-schema fix additionally validates tokenizer type, memory-image
format, string command name, boolean CRC declaration, exact package-file key
set, 40-hex model source revision, and rejects boolean token IDs. Focused
mutation coverage exercises each of these cases. The ABI's `crc32` field is a
boolean capability declaration; its endian/framing description remains in the
contract prose and command documentation.

The ABI is now explicit: little-endian byte order; ordered request/reply field
lists with byte offsets and widths; header, token-payload, and CRC framing
boundaries; and the CRC-32/IEEE algorithm with its covered-byte rule. The
loader requires and type-checks each of these fields, with focused corruption
tests.
