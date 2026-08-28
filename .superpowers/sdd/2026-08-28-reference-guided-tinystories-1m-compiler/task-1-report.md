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

## Fix round 4: machine-semantic ABI and fail-closed layout validation

The wire ABI is now represented by numeric and structural JSON values, not
descriptive strings. `infer` is command `u8` value 1 and `ok` is status `u8`
value 0. Magic values are numeric `u16` values, all scalar and token integers
are explicitly unsigned little-endian and byte-aligned, and `bit_packing` is
explicitly `none` with `lsb0` bit ordering.

Request and reply layouts now include frozen ordered field definitions, the
variable token-count bounds, payload offsets, and structured total-length
formula operands. The formulas are request `10 + 2 * prompt_count` and reply
`17 + 2 * token_count`; a successful reply's token count equals the requested
generation count. CRC-32/IEEE records its reflected polynomial, initial/final
XOR values, coverage interval, immediate-post-payload trailer placement, and
little-endian `u32` trailer representation.

The loader rejects duplicate JSON object keys and rejects any missing or extra
field in every contract object. It also rejects ABI extra fields, invalid command
encodings, non-little-endian packing, duplicate/overlapping/out-of-order field
lists, offset or width changes, count and length-formula inconsistencies, and
CRC placement, coverage, or byte-order changes. The regression suite exercises
each failure class.

Reference trace evidence remains unavailable and is recorded as a null digest
with an explicit reason. Timing and resource evidence also remain unavailable:
all baseline measurements, resources, and source are still null with an
explicit reason. No trace, timing, or resource value has been fabricated.

Fix-round-4 validation used the pinned command
`nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_reference_contract.py' -v`;
all 6 tests passed. `git diff --check` also passed.

## Fix round 5: pinned host/RTL semantics and frozen identities

A direct audit of the pinned
`host/kevin_jtag_cli.py` and `fpga/rtl/tinystories_packet_controller.sv`
confirmed that `generation_count = 0` is valid. The contract now freezes its
range as `[0, 32]`; request length remains `10 + 2 * prompt_count`, while the
corresponding successful zero-token reply has length
`17 + 2 * token_count = 17` bytes.

The reply status ABI now records every controller status class with exact
unsigned-8-bit values: `ok = 0`, `bad_header = 1`, `bad_crc = 2`,
`context = 3`, and accelerator-class status base/range `16`/`[16, 255]`.
Loader validation requires the exact field set and values and rejects booleans
for all numeric ABI fields, including command and status encodings.

The loader now compares every recorded package, tokenizer, scale-image, and
memory-image digest against checked-in constants obtained from the inspected
package receipt and manifest. It also compares the full fixed model,
tokenizer, quantization, memory-image, and reference identities rather than
accepting merely well-formed alternatives. Regression tests replace every
recorded digest with a different valid 64-hex value, mutate each fixed identity,
and substitute booleans at every numeric ABI location.

Trace, timing, throughput, resource, and source evidence remains explicitly
unavailable and null; no measurement or digest was inferred. The approved
compiler design spec was pre-existing project documentation before Task 1 and
is intentionally preserved on the branch. It is not part of this focused fix.

Fix-round-5 validation uses the required pinned command
`nix develop -c python -m unittest discover -s tests -p 'test_tinystories_1m_reference_contract.py' -v`;
all 11 tests pass.
