# Task 3 report: exact frozen-generation equivalence

## Status

Implemented and verified. Three fresh `ExactModelBundle`/model instances each
generate exactly the frozen sixteen-token sequence from prompt IDs
`[7454, 2402, 257, 640]`:

```text
[11, 612, 373, 257, 1310, 2576, 3706, 20037,
 13, 1375, 6151, 284, 711, 2354, 287, 262]
```

No model, arithmetic profile, backend, DDR3, PCIe, or board integration was
changed. The compiler model is not registered by this task; the artifact opens
the later lowering gate only after complete equality and leaves registration
`performed: false`.

## Authenticated inputs and fail-closed boundary

The verifier consumes the authenticated Task 2 bundle and rejects drift before
export or candidate generation. It binds:

- Task 1 commit `c8eb2011ee09c368accdf8efd67c50dfc5564679`, contract file SHA-256
  `859fe3095a4842e413ee99466f5dc63d5420d0e890a3dce0cf7a52e3bd2d1d3c`,
  and audit file/payload hashes;
- Task 2 commit `a2eda783819bbfb35a833d1a45d3dd125a176973`, exact-model artifact file/self
  hashes, model receipt, and independent fixed-logits oracle identity;
- the complete current Task 2 source closure already authenticated by its
  artifact;
- the live model state SHA-256
  `0c55aba9769d1cf836cb9fae7d39e9ea1ce8cef2e2e617acbe1cd465e2b16c66`,
  compared against Task 2's authenticated exported-state digest;
- this verifier source SHA-256
  `ceac99c378108ca7589ff38f99d671c8254b25654e3235940d3897d95ba0e562`
  and test source SHA-256
  `13b7a5564ea558c745ed99a93010309960a8039d8de48c1dfad4afaf9c959fb9`.

The external fixed reference remains the Task 2 authority only. It is not
called as the Task 3 candidate. A regression test mutates a live model buffer
while preserving the receipt and confirms rejection as
`task_2_model_state_mismatch` before any export.

## Complete eager/exported execution

Task 2's export is correctly treated as static to its input shape. Task 3
creates exactly one deterministic trace export for each context length 4
through 19, replays that export once for each of the three fresh bundles, then
releases the active program before exporting the next length. The artifact
records 16 exports and 48 actual replays; it never compares only the first
step.

For every run and every step, eager and exported execution compare:

- the complete current 50,257-element fixed-point logits vector and the full
  context logits tensor, with canonical and little-endian signed-int64 hashes;
- all 12 block-0 checkpoint hashes;
- all 97 Q/DQ boundary groups (codes, scales, and dequantized values);
- all 49 serial GEMV accumulator hashes;
- all 33 nonlinear observation hashes.

This is 191 named checkpoint/observation groups and 385 observation tensor
hashes per execution mode per step. A mismatch records its run, step, context
length, exact nested field/checkpoint path, and eager/exported values, stops
generation, and closes the registration gate.

Greedy selection explicitly finds every ID equal to the maximum and selects
the smallest ID. A focused tie test verifies IDs 1 and 2 tied at the maximum
select ID 1.

## Determinism and artifact

All three fresh runs have identical authenticated transcript SHA-256:

```text
9ab20b2b61ab58e7b1d6a1c89e4ccb070d0fe93b9bcd8d14f74bfe321ee9c6d7
```

Their run hashes (which additionally bind each deterministic run index) are:

```text
cfd1ac8116ccd6baedc710a6df7bf26e7fbc7f3463cddfdc91760d537f207006
07b85cab82bab9225ac5b45e9cc08f7df4b91695d82d59ed0412c3b3cce8410d
ec8f8d622ade2dc11a8fb15c3b4f5afb3d6a33913f73150510596ba6eac732f3
```

The combined three-run SHA-256 is
`f621ed3d9133554d840adcdf5db2d7158dd8d5abe0d310a98c10556591321fce`.
The per-length export cache identity is
`024bb8a6356f556f6b0a820cfebaa79287a17e7e483fc6bfba9558efe38da613`.

The checked artifact is
`artifacts/reference/tinystories-1m-exact-generation.json`:

- canonical artifact self-hash:
  `77fadf7d78008e171d05671e10f861770d94f5b113f6f23b0acf6e694c877a52`;
- file SHA-256:
  `44019cb3258d58ae8b8112aec43a8bf4b3fd052c4b341f06c1ba6400b8add902`;
- generation result SHA-256:
  `fede4cd11c6f914acfab7a24e4956e55c092cbff64d0b36b9dfc42c5b6e09b72`.

The artifact contains every step hash, per-step eager/exported evidence, all
sixteen exported-program identities, three deterministic run hashes, Task 1/2
identities, and verifier/test hashes. Consistently self-rehashed mutations of
either Task identity, the test hash, a later-step logits hash, or the third-run
transcript are rejected against freshly reconstructed evidence.

## TDD record

The required initial red was observed before the verifier existed:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_generation.py -v
ERROR: FileNotFoundError: scripts/comparison/verify_tinystories_1m_exact_generation.py
FAILED (errors=1)
```

The first complete implementation run proved the full generation core: all
16 tokens in all three runs and every context 4 through 19 matched. Only the
two artifact tests remained red because the artifact had not yet been
generated:

```text
Ran 7 tests in 1975.159s
FAILED (errors=2: missing tinystories-1m-exact-generation.json)
```

Local review then added two test-first hardening cycles. A mutated in-memory
model initially entered the expensive export path instead of rejecting; the
red run was interrupted after the failure mode was demonstrated. After the
state binding was implemented, it passed in 0.255s. The first-checkpoint
reporting test initially received only `checkpoint_sha256` rather than the
exact `block.output` path; it passed after recursive mismatch reporting was
implemented. Both focused hardening tests pass together in 0.259s.

## Verification and timing

Final artifact generation:

```text
nix develop -c python scripts/comparison/verify_tinystories_1m_exact_generation.py \
  --contract artifacts/reference/tinystories-1m-exact-input-contract.json \
  --package /home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m \
  --model-path /home/roland/.cache/huggingface/hub/models--roneneldan--TinyStories-1M/snapshots/77f1b168e219585646439073245fe87e56b3023e \
  --output artifacts/reference/tinystories-1m-exact-generation.json
77fadf7d78008e171d05671e10f861770d94f5b113f6f23b0acf6e694c877a52
elapsed=1687.16s maxrss=4234476KB
```

Final focused suite on the exact commit candidate:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_generation.py -v
Ran 9 tests in 1914.363s — OK
elapsed=1920.77s maxrss=4302928KB
```

Task 2 authority regressions on the same tree:

```text
nix develop -c python -m unittest -v \
  tests.test_tinystories_1m_exact_reachable_domain \
  tests.test_tinystories_1m_exact_package_model
Ran 24 tests in 117.689s — OK
elapsed=121.98s maxrss=1318244KB
```

The static-export traversal was changed from retaining all sixteen programs
to retaining only the active length after the first complete run. Peak RSS
fell from 8,547,996KB to approximately 4.3GB without changing the required 16
exports or 48 replays.

## Concerns

- The proof is intentionally expensive: the final focused run takes about 32
  minutes and peaks near 4.3GB RSS because each static shape must capture the
  full logits and observation graph.
- The authenticated package and Hugging Face snapshot are external immutable
  inputs at the absolute paths used by Tasks 1/2; tests skip if they are not
  present.
- Fresh bundles are newly constructed bundle/model instances copied from the
  already authenticated in-memory authority. Their complete state is checked
  against Task 2 before generation; they do not re-read or call the external
  oracle as candidates.
- This task proves the exact software/export input to lowering. It makes no
  board-authentication, timing, resource, DDR3, or PCIe claim.

## Commit

The implementation/report commit is recorded in the external task handoff;
this report cannot truthfully contain the hash of the commit that contains
itself.
