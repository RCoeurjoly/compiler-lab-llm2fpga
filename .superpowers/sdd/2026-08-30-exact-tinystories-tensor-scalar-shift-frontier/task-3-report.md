# Task 3 Report: Authenticated Registered Pipeline Rerun

Status: implemented and verified with a new SCF availability frontier.

## Outcome

The live Task 2 semantic verifier accepted the current registered Torch bytes
before any classifier derivation lookup or stage build. Two subsequent
classifier runs executed the registered stages in this exact order:

1. `pytorch-exported`: valid
2. `torch`: valid
3. `linalg`: valid
4. `scf`: invalid control manifest

Both runs stopped at SCF. Neither run invoked `flat-scf`, `calyx`, or
`calyx-native-sv`.

The first invalid diagnostic is:

```text
error: registered scf stage status is 'unavailable': baseline hardware pipeline lowers through CF and Handshake
```

This is a registered-stage availability frontier, not an operation
legalization frontier. The SCF derivation exits 0 but its only artifact is a
109-byte manifest with `status: unavailable`; the classifier rejects that
artifact and does not accept exit code 0 as validity.

## Precheck and TDD

The initial `scripts/agent/pre_final_check.sh` completed without a dirty-state
diagnostic. `scripts/agent/install_git_hooks.sh` could not update the linked
worktree's shared `.git/config` because it is read-only in the sandbox; manual
pre-final checks were retained.

The first focused red run was:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier.py -v
Ran 27 tests
FAILED (failures=4, errors=11)
```

The new semantic-order test observed the old first action
`nix build ...-torch-mlir` rather than the Task 2 verifier. The sequencing and
bundle-identity tests failed because the required runner interfaces did not
exist. The registered stage-name tests also exposed the required transition
from logical `torch-mlir` to the actual registered `torch` name.

After the minimal semantic gate, ordered runner, stop condition, and bundle
comparison were implemented, the focused suite was green. Two later red/green
cycles caught integration defects:

- export provenance `manifest.json` was incorrectly interpreted as a control
  stage manifest; the red test rejected a valid export, and the fix scopes
  control-status validation to SCF/backend stages;
- fresh versus cached Nix build-progress text changed the Linalg log; the red
  test proved the mismatch, and the fix removes only Nix cache/build progress
  while retaining commands, exits, store results, and substantive diagnostics.

The final focused frontier suite contains 29 passing tests. The determinism
suite gained a current-SCF bundle test while retaining the historical Torch,
successor, and registered-Torch-success bundle tests.

The final combined semantic/frontier/determinism gate reported:

```text
Ran 49 tests in 39.566s
OK
```

## Semantic prerequisite

The hard prerequisite command was run before the registered pipeline:

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py \
  --probe-report artifacts/comparison/tinystories-1m-exact-shift-semantic-probe.json
```

It returned `accepted` for both the compiler-backed semantic probe and the
registered Torch stage. Bound identities include:

- registered Torch artifact SHA-256:
  `e2e0fe83d874714847cdacc4918fc41220637569c8ac7ca225f0139ab82ea674`
- semantic probe file SHA-256:
  `645a87cdc4292ea584a04d4268187c612dd070b068036f9fa13b71865b36cbe6`
- decision self-hash:
  `429da5a367755d35bc38308589beaf25d291a8272ebf4d8944bfa4b8919ef8fe`

The receipt also copies the complete frozen Task 1--3 identity map from the
decision receipt and binds the live verifier bytes.

## Registered commands and stage evidence

Each canonical run invoked:

```text
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-pytorch-exported
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-torch
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-linalg
nix build --no-link --print-out-paths -L .#tiny-stories-1m-kev-gpt-exact-scf
```

The receipt binds each artifact, command, derivation file, canonical derivation
JSON, build command, log, upstream artifact, exit code, source commit, and
accepted/rejected state. The executed prefix is exactly
`pytorch-exported, torch, linalg, scf`; the `not_run` list is exactly
`flat-scf, calyx, calyx-native-sv`.

## Full input and minimal frontier

The complete Linalg input to the SCF stage is preserved as deterministic gzip:

- uncompressed bytes: `13,274,515`
- uncompressed SHA-256:
  `f4792aef4a0054386bf4e9e6399cc107e6d947b4d608e97e6041ccdf2ffb59c8`
- gzip bytes: `532,330`
- gzip SHA-256:
  `1e6d47462458fed298353e97bfbc030af8c6b9e8f8a870e53fbd4d35ffe88594`

The exact 109-byte SCF control manifest is the minimal reproducer, SHA-256
`afc3d62b34d2eda0ec241556e04ce2c36642ca6520609df7a2a2ef87b8ce7c7c`.
Operation and type reduction is explicitly marked not applicable because no
MLIR operation diagnostic is involved.

## Independent deterministic captures

Two independent post-fix classifier runs were captured under separate
temporary roots and compared before preservation. All seven canonical files
were byte-identical. The preserved bundle is
`artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf`.

- receipt file SHA-256:
  `1d1fd8eeea5ad5114ec36a5aea13c5b84cec4a60cc25fa2aa5793ed9e46bf8ce`
- receipt self-hash:
  `7451d19a9dd7d10ae61e7759422625de300e3a5e4ae5b1b44dbc56d8f3173425`
- canonical file count: `7`

The default determinism verifier now verifies the current v2 bundle and still
dispatches to the historical v1 verifier for the preserved original Torch
frontier. Historical successor verification resolves old receipt bytes from
their immutable determinism bundles when the mutable current receipt path has
advanced; no historical receipt or bundle bytes were changed.

The Task 2 verifier applies the same immutable-receipt lookup before replaying
current compiler semantics. This removed the mutable-path coupling without
changing the decision, fixture, probe report, expected outputs, registered
Torch artifact, or any historical receipt.

## Files

- Modified `scripts/pipeline/classify_tinystories_1m_exact_frontier.py`
- Modified `scripts/pipeline/verify_tinystories_1m_exact_frontier_semantics.py`
- Modified `scripts/pipeline/verify_tinystories_1m_exact_frontier_determinism.py`
- Modified `scripts/pipeline/verify_tinystories_1m_exact_successor_frontier_determinism.py`
- Modified `tests/test_tinystories_1m_exact_frontier.py`
- Modified `tests/test_tinystories_1m_exact_frontier_determinism.py`
- Updated `artifacts/comparison/tinystories-1m-exact-current-pipeline-frontier.json`
- Added `artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf/`
- Added `reproducers/scf/`
- Updated `docs/results/2026-08-29-tinystories-1m-exact-current-pipeline-frontier.md`

## Scope and claims

No compiler, adapter, model, quantization, runtime, scheduler, memory, RTL, or
board change was made. No SystemVerilog was produced, so syntax and synthesis
validation are not applicable. The receipt makes no board-inference,
functional-equivalence, resource, or timing claim.

## Self-review

- Confirmed the semantic verifier is the first external action in the current
  runner.
- Confirmed a zero-exit control manifest with non-`ok` status is rejected.
- Confirmed successful prefixes cannot establish completion.
- Confirmed both canonical receipts list only the four-stage executed prefix.
- Confirmed later-stage logs do not exist in either canonical bundle.
- Confirmed the full compressed input round-trips to the recorded size/hash.
- Confirmed the minimal reproducer bytes match the rejected SCF manifest.
- Confirmed both bundles are byte-identical and receipt self-hashes recompute.
- Confirmed historical bundle bytes remain unchanged and independently
  verifiable after the current receipt advanced.

## Concern

Before control-manifest validation was implemented, an exploratory manual
probe treated SCF's exit code 0 as success and invoked cached `flat-scf` and
`calyx` attributes. Those outputs were immediately recognized as unavailable,
were not accepted, are not included in canonical evidence, and no
`calyx-native-sv` invocation occurred. The two final authenticated classifier
runs enforce the required stop at SCF. This process defect is recorded here
rather than hidden.

The technical successor concern is the registered SCF availability frontier.
A new bounded plan is required before changing compiler or pipeline wiring.

## Review fix round 1: complete provenance bindings

The review findings were addressed without registering SCF and without any
compiler or lowering change. Provenance code, adversarial tests, and the
bounded successor plan were committed first as
`b6f54a4edec9d90a02c94ec79f8a9913f0a4cbdf`. Only then were both classifier
captures rerun. Each v4 receipt names that code commit and binds the exact
classifier and determinism-verifier bytes:

- classifier SHA-256:
  `966541ca4d548a9f1f6820819c87add91aa401d025d3946ab5db69c39f3bf9e7`
- determinism-verifier SHA-256:
  `b875ea3bab84bcefe2ca52c887205623b3169abc61183ddb843eb3021f4e4c46`

The independent verifier now replays the live compiler-backed semantic gate,
compares the exact semantic evidence and probe/verifier hashes, enforces the
frozen Task 1--3 and predecessor constants, resolves the live Linalg and SCF
derivations, and checks result/artifact paths, exits, statuses, acceptance,
logs, diagnostics, and exact stop semantics. It also decompresses the Linalg
archive and compares its bytes to the live derivation output, then validates
the SCF manifest as exactly:

```json
{"reason":"baseline hardware pipeline lowers through CF and Handshake","stage":"scf","status":"unavailable"}
```

Both Linalg and SCF derivations are preserved as exact `.drv` bytes and
canonical `nix derivation show` JSON. The receipt preserves the full build
commands rather than only their hashes. Linalg's build command is:

```text
/nix/store/1jzhbwq5rjjaqa75z88ws2b424vh7m53-bash-5.2p32/bin/bash /nix/store/4zp4prlbv19xvzzf80f5cf2hxh7zzd38-pipeline/torch_to_linalg.sh \
  /nix/store/k8smi8mni8mjmyf37dav2lf4f11is7ha-torch-mlir-0-unstable-2026-02-12/bin/torch-mlir-opt /nix/store/k2q1qg1xn0yvxx3bprvfq3dxphw8vz8m-tiny-stories-1m-kev-gpt-exact-torch.mlir "$out"
```

SCF's unavailable-stage build command is:

```text
mkdir -p "$out"
cat >"$out/manifest.json" <<'JSON'
{"reason":"baseline hardware pipeline lowers through CF and Handshake","stage":"scf","status":"unavailable"}
JSON
```

The two new runs are byte-identical across eleven canonical files:

- receipt file SHA-256:
  `e1ccda9f6042671660ab753d99fe8af9b77dd362b9afc0bedae1fc17f055ae60`
- receipt self-hash:
  `d43c5adaf995c432ad31001cc86654025f5976e780d25951246aa5f4e5e14bf3`
- Linalg `.drv` SHA-256:
  `57c76eca7dbea3dc1058595f0524ac6fa0172b35c6266a9d989ebf29169700f7`
- Linalg derivation JSON SHA-256:
  `9b1fc76bbe17c1a871c1b5f9e1c8012a46339291ffff33726e5368fb650e6f40`
- SCF `.drv` SHA-256:
  `103aaba38b6df8b4b28fe93781c095efa75e26c06ea586530f573b9f31127b7c`
- SCF derivation JSON SHA-256:
  `feaf6061090a89f85cf030bb86dc163342c11370cc023dc322a7f50e3e7c5da3`

Adversarial tests mutate semantic gate/probe evidence, frozen/predecessor
identity, classifier/verifier bindings, derivation/tool/build-command facts,
stage exit/status/log/diagnostic semantics, decompressed Linalg content, and
each SCF manifest field. Each mutation recomputes the receipt self-hash and is
still rejected against independent trust.

The superseded seven-file capture is preserved byte-for-byte at
`artifacts/comparison/tinystories-1m-exact-frontier-determinism-scf-v1` rather
than overwritten as causal history. The current eleven-file capture remains at
the canonical `...-determinism-scf` path.

The required bounded follow-up plan is
`docs/superpowers/plans/2026-08-30-exact-tinystories-scf-registration-frontier.md`.
Its smallest evidenced next experiment registers the repository's existing
direct `pipelineStagePackagesNoHandshake` Linalg-to-SCF route for this exact
model, proves the authenticated prefix is unchanged, and captures the next
frontier. The plan does not authorize or implement a compiler fix.

### Review-fix verification evidence

The focused combined classifier/determinism command completed 45 tests with
`OK`:

```text
nix develop -c python -m unittest tests/test_tinystories_1m_exact_frontier.py tests/test_tinystories_1m_exact_frontier_determinism.py -v
```

The historical v1 verifier returned byte identity with receipt file SHA-256
`b69fb780157362d30a1c5ee05a4ac67a71e9172b0700e820c52c08f6af70df55`.
The preserved superseded seven-file SCF verifier returned byte identity with
receipt file SHA-256
`1d1fd8eeea5ad5114ec36a5aea13c5b84cec4a60cc25fa2aa5793ed9e46bf8ce`.
The new default v4-backed verifier independently replayed the semantic gate and
returned byte identity, canonical file count 11, and first invalid stage SCF.

Explicit `cmp` checks passed for both receipts and all four Linalg/SCF
derivation evidence files. `git diff --check` passed. A scoped diff from the
frozen code commit showed no post-capture modification under `scripts/pipeline`,
`flake.nix`, `nix`, `patches`, or `TinyStories`; therefore the receipt-bound
classifier/verifier bytes and compiler/pipeline implementation remain exactly
those from `b6f54a4`.
