# Task 1 report: exact signed left-shift semantics

## Status

Verified semantics fixture and verifier complete. Compiler code was not
modified. The fixture has six live pinned-PyTorch `si64` cases and four
non-executed compiler-contract rejections.

## Commits

- `2a837dc9eddb10b5a67b37938c793c787def78f6` — `test: freeze exact signed left shift semantics`
- The report commit follows this content update.

## Files

- `artifacts/comparison/tinystories-1m-exact-left-shift-semantics.json`
- `scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py`
- `tests/test_tinystories_1m_exact_left_shift_semantics.py`
- `docs/results/2026-08-30-tinystories-1m-exact-left-shift-semantics.md`

## Red/green evidence

The required initial red command was run after only the fixture/verifier test
was added. It failed with `FileNotFoundError` for the absent fixture and
verifier, as expected. After materialization, the focused verifier accepted the
fixture and the focused unit suite passed all 3 tests.

## Exact semantic cases and results

Valid live-PyTorch cases, all `si64` with preserved output dtype and shape:

| Case | Count | Result |
| --- | ---: | --- |
| `shift_zero` | 0 | `[-5, -1, 0, 1, 5]` |
| `model_observed_shift_sixteen` | 16 | `[4,64]` result; repeated lane is `[-327680, -65536, 0, 65536, 327680, 2147418112, -2147483648, -9223372036854775808]` |
| `negative_operand` | 3 | `[-40, -8, 0]` |
| `positive_high_bit_wrap` | 1 | `[-9223372036854775808, -2]` |
| `negative_high_bit_discard` | 2 | `[0, 0]` |
| `shift_sixty_two` | 62 | `[-9223372036854775808, -4611686018427387904, 0, 4611686018427387904, -9223372036854775808]` |

The invalid cases are all explicitly `compiler_contract` and have no output:
`negative_count` (`rejected_negative_shift`), `count_sixty_three`
(`rejected_shift_greater_than_sixty_two`), `dynamic_count`
(`rejected_dynamic_shift`), and `si32_rejection`
(`rejected_unsupported_dtype`). Count 63 is deliberately rejected by the
compiler contract, not attributed to PyTorch.

## Provenance bindings

The artifact self-hash is
`672d34819f93db399e7e8faac4747f9bb88b690491c2683912fee9490ffca19c`.
The live executor was PyTorch 2.9.1 with resolved
`torch/__init__.py` SHA-256
`3caf7f40140ede2465bde40b9003af10cbbc8f7bcf436fa1de026471daa1b288`.
The artifact binds adapter hash
`d7259ccd5545a1826101fbb06b3199f2b5973fb739e1aed13828acc0b2607e5e`,
reproducer hash
`c3fe1f68a1da10ad690b1b2ff6272ec6131aa70a1cd62d79a111ebb619631132`,
and accepted successor receipt self-hash
`638ed427537be14fe53a0d5d694eb2c13bf09f56f8b0679fadd30dbb746b6822`,
plus the current Task 1--3 identity fields from that receipt.

## Test commands and outcomes

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_left_shift_semantics.py -v
RED: 3 errors because the required fixture and verifier did not yet exist.

nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_left_shift_semantics.py
GREEN: accepted; 6 valid cases and 4 invalid cases.

nix develop -c python -m unittest tests/test_tinystories_1m_exact_left_shift_semantics.py -v
GREEN: 3 tests passed.
```

## Self-review

Reviewed the artifact schema, strict case-ID order, no-output rejection rule,
self-hash, expected-output hashes, live PyTorch binding, independent masked
64-bit arithmetic, adapter/reproducer/receipt bindings, and Task 1--3
identity checks. The verifier rejects mutated fixture self-hash and mutated
adapter provenance in the focused test suite.

## Concerns

The pinned PyTorch module is a Nix-environment symlink; the fixture records
its resolved store path and hashes the resolved file, avoiding an environment
wrapper-path ambiguity. The semantic domain intentionally excludes count 63
despite PyTorch behavior.
