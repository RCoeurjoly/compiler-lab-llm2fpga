# TinyStories-1M compiler-input alignment

## Result

The compiler registry now pins the frozen package's Hugging Face revision,
`ac533fb8b4f69c71894bf96badfe11e6294d9fcf`.  This is a provenance alignment,
not a claim of quantized compiler equivalence.  The current full-model compiler
export remains FP32 and cannot consume the authenticated package described
below, so the slice comparison remains blocked on a package-to-export adapter.

## Evidence

The old registry pin was `77f1b168e219585646439073245fe87e56b3023e`.  Both
that registry and the reference package's independently pinned source manifest
fetch the following identical content-addressed checkpoint files:

| file | SHA-256 |
| --- | --- |
| `config.json` | `ff74c30d5ebb5ab1da0f2ea479adf7197c504b42b5522a858c334ab91ed4958c` |
| `pytorch_model.bin` | `07f9609ea882b8163ff3b23d40e2b82cb715d409631beb15c84b164f3877dae7` |

Thus the revision difference did not change the FP32 model bytes.  It did,
however, leave the compiler provenance inconsistent with the frozen contract;
the single registry-pin change corrects that inconsistency.

The validated package is present at git commit
`df1fc45b2ffcb26fddc19cfd57621e7eedf6153f` of the GNU AGPL v3
`RCoeurjoly/kev-gpt` fork.  The package is an authenticated **input**, not
copied source or RTL.  Its relevant immutable identity is:

| item | value |
| --- | --- |
| package manifest | `374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35` |
| `weights.bin` | `caa140a70f824334d626e20819effabb3a56c28f35cc5c84e6f5f174b3f6bf4e` |
| `scales.bin` | `a81faadf9ab21a525a8a20870f2fa97572c66bbf6b88c5cbe2a29cd253355155` |
| `calibration_ids.bin` | `2537125a6edea656c5f6b8fe537b4cec7f2a3b2f633f5ee36297135e705bb075` |
| package receipt | `aa546aa3956fd5de207af647ed4cf280d26c8477e9f308f9f0b39c1a2b90cca2` |
| frozen contract | `a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf` |

The package manifest proves the exact model configuration: GPT-Neo, eight
layers, 64 hidden channels, 16 heads of width 4, vocabulary 50,257, context
32, tied embeddings, and `gelu_new`.  It has 108 stored tensors: 50 signed
INT8 `symmetric_int8_per_output` weight tensors with little-endian float32
scales, plus FP32 tensors where recorded.  Its 202 calibration token IDs hash
to `253712…b075`; the manifest contains 97 activation scale vectors of widths
64 or 256.

This last point is deliberately recorded rather than hidden: the frozen
contract's high-level phrase “symmetric per-tensor INT8” is insufficient to
recreate the package.  The immutable package manifest is the authoritative
detail for the 97 per-channel activation scales.  The frozen contract was not
rewritten.

## What changed

`flake.nix` now pins `tinyStories1m` to `ac533…9fcf`, while retaining the
content hashes for the same HF model bytes.  The new
`verify_tinystories_1m_reference_input.py` validates the frozen contract,
package receipt, all required binary hashes, GPT-Neo semantic fields, tensor
formats, and the calibrated scale structure.  It fails closed before any
compiler adapter can consume a tampered package.

## Remaining adapter boundary

The current `TinyStories/model_adapter.py` calls
`AutoModelForCausalLM.from_pretrained()` on the FP32 checkpoint and exports an
FP32 program.  It neither deserializes `weights.bin`/`scales.bin` nor represents
the package's per-output weight dequantization and 97 activation Q/DQ
boundaries.  Consequently, changing only the HF revision cannot make the
compiler-generated RTL match the reference package.

The next bounded implementation must be a new, independently implemented
package adapter/export derivation.  It must accept a Nix-pinned checkout of
the GPL-licensed package at `df1fc45…6153f`, run the fail-closed verifier,
map canonical package tensor names to GPT-Neo state keys, reconstruct each
INT8 weight using its authenticated per-output scale, and explicitly model the
97 calibrated activation boundaries before `torch.export`.  It must emit an
input receipt carrying the frozen contract and all package hashes.  No kev-gpt
source or RTL should be copied into compiler output, and equivalence must not
be claimed until that adapter has an independent numerical trace test.
