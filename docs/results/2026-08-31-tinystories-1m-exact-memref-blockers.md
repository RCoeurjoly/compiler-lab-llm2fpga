# Exact TinyStories-1M flat-SCF memref blocker contract

## Result

The authenticated retained c22 flat-SCF output contains exactly the four
registered memref blocker classes. The extractor parsed balanced MLIR
operations and recomputed every count, location, type/layout signature, and
multiplicity from `flat.scf.mlir`; the counts below were not taken from the
older blocker report.

| Operation | Count | Unique canonical signatures |
| --- | ---: | ---: |
| `memref.reinterpret_cast` | 11,449 | 408 |
| `memref.collapse_shape` | 4,682 | 450 |
| `memref.copy` | 3,228 | 27 |
| `memref.expand_shape` | 921 | 10 |
| **Total** | **20,280** | **895** |

The canonical contract is
`artifacts/comparison/tinystories-1m-exact-memref-blocker-contract.json`.
It is 4,276,980 bytes and has self-hash
`e66d005b99c04420fe2ed7639f50ed8cc59feb3668beb172e93a522efda77eda`.
It retains all 20,280 exact source locations and every unique signature with
its multiplicity.

## Evidence and Nix ancestry

The payload is the retained authenticated c22 Nix output, not a realization of
the post-Task-1 alias derivation:

- retained c22 deriver:
  `/nix/store/k8s58qyhywj26hcqpikw8lbalkqb9as5-tiny-stories-1m-kev-gpt-exact-flat-scf.drv`;
- retained c22 output:
  `/nix/store/qskklvplhvrdjz7x097r369n2gjyrr1l-tiny-stories-1m-kev-gpt-exact-flat-scf`;
- current protected alias derivation:
  `/nix/store/zvkcy64sxxahpgj8ay0fcvgdk27bpc7q-tiny-stories-1m-kev-gpt-exact-flat-scf.drv`;
- current protected alias output:
  `/nix/store/gj31d9b3ry4h3k4hwk4b9fd8s9bpj38f-tiny-stories-1m-kev-gpt-exact-flat-scf`, explicitly unrealized;
- filtered runtime source:
  `/nix/store/amahjznxmsx37q7x7lazjkf5253syc56-llm2fpga-pipeline-runtime-scripts`, NAR hash
  `sha256-v5VXxWwTVtwgGT1BTZ4nE02jtK+hW623ptAOA+0Wdsg=`.

The extractor and independent verifier each require all 29 derivation-visible
runtime files to be byte-identical in the workspace, Task-1 commit `99f0b6c`,
and c22 commit `c22c5f8`. They also require the retained store output to match
the captured manifest, MLIR, and blocker bytes. A Nix dry-run said that
realizing the current alias would build Linalg, SCF, and flat-SCF, so no rebuild
was started. This residual derivation-boundary provenance is recorded in the
contract and is not represented as a current-output realization.

| Payload | Bytes | SHA-256 |
| --- | ---: | --- |
| manifest | 118 | `8b15b5aeffa19ed20975926fab100d28398863482eccb3fcd6840a65ed2df7cb` |
| `flat.scf.mlir` | 18,933,168 | `66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6` |
| `blockers.json` | 19,257,118 | `2be1745e4a588c533b03d792439d5698c90b7ecd2bb9dba2c5294791d94576f9` |
| c22 receipt | 61,835 | `6af348b82f2e263980f0515f46b0a08c14898118d7e868cacfec3764ceae6acf` |

The receipt self-hash is
`961b81662493f1241eea58061433779314019e6c46a249022362d77fc61808c8`.
The pinned `mlir-opt` binary is
`/nix/store/qfhb8ajk2kw32lrmk8xqaa1g6h7w95p8-mlir-21.1.2/bin/mlir-opt`,
496,904 bytes, SHA-256
`3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912`.

## Representatives

One deterministic standalone module per class is under
`reproducers/tinystories-1m-exact-flat-scf-memref/`. Selection is the
lexicographically smallest canonical `(operation, type signature, source
location)` tuple. Each directory includes the module, its exact signature and
selection metadata, and an interestingness test. The public verifier requires
the module to parse with the pinned MLIR tool and to contain exactly the bound
class and signature.

| Operation | Selected source line | Signature SHA-256 |
| --- | ---: | --- |
| `memref.collapse_shape` | 29,032 | `59747eb1bf4ea9208a3d0ec4c6f9bf0da0ea5fe4a8555798793a6f767bc00d8e` |
| `memref.copy` | 10,149 | `818a3039b607d474c6c351cab464d1e6f7860f872b1ab1cf8e0646d5fde1fe9c` |
| `memref.expand_shape` | 10,163 | `b0856b3b36b0366cddf0a2f2c315458a50b8b30abffc2ad2895c74f1531ead31` |
| `memref.reinterpret_cast` | 10,166 | `856681b7550898c32f7a10acd8c08f4d976ea54cc3b243996f3b46f7b9cbb8f8` |

## Frozen identities and scope

The contract binds the c22 receipt's exact Task 1--3 identity map: input-audit
file/payload, exact model artifact/file/receipt, generation
artifact/file/result, model contract, adapter, and package manifest hashes.
The independent verifier rejects stale payload hashes, altered counts or
locations, unknown classes, malformed static/affine metadata, incomplete Nix
ancestry, runtime-byte drift, broken representative bytes, parse failures, or
an altered exact signature.

No compiler behavior, runtime pipeline script, model, quantization, Calyx,
later pipeline stage, or external system changed. Calyx was not invoked.

```text
nix develop -c python scripts/pipeline/verify_tinystories_1m_exact_memref_blockers.py
nix develop -c python -m unittest tests/test_tinystories_1m_exact_memref_blockers.py -v
```
