# Stateful Serving RC Reference and Direct-Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add an independent TinyStories stateful-serving representative core whose native Hugging Face prefill and cached-decode trace is reproducible, directly exportable, and truthfully gated on cache-aware PT2E W8A8 feasibility.

**Architecture:** The new model key owns one fixed three-transaction trace: eight-token prefill, then two one-token cached decodes. The ordinary Hugging Face model remains the only model implementation: a Python call helper supplies fixed source-API arguments, while PyTorch's official DynamicCache export registration preserves the native cache container across direct export. A dedicated multi-program bundle represents the three static phases; it deliberately does not enter the generic one-program pipeline registry. A separate PT2E probe writes a durable pass-or-blocked receipt before any Torch-MLIR, SV, or RTL work is permitted.

**Tech Stack:** Python 3.11, PyTorch 2.9.1, Transformers 4.57.3, TorchAO 0.15.0, PyTorch Export, PT2E XNNPACK quantization, Nix flakes, and Python unittest.

## Global Constraints

- Keep the existing stateless RC, key, adapter, artifacts, reference image, aliases, and acceptance criteria unchanged: tinystories-w8a8-rc-study-mask9-vocab6-width2 remains the static context-eight PT2E W8A8 compiler fixture.
- The new independent key is exactly tinystories-w8a8-rc-serving-mask10-vocab6-width2. It is a protocol-representative serving RC, not a TinyStories-quality, resource-scaling, throughput, power, or full-tokenizer proxy.
- The profile has vocabulary 6, two layers, hidden width 2, one head, window size 256, seed 0, and max_position_embeddings = 10. The source model has use_cache = True.
- The immutable workload is exactly: prefill-8 with prompt IDs [0, 1, 2, 3, 4, 5, 0, 1]; decode-8 with the greedy token from prefill; and decode-9 with the greedy token from decode-8. Their cache lengths are 0 to 8, 8 to 9, and 9 to 10 respectively.
- Every source-model call uses the normal Hugging Face model object. Do not add an nn.Module wrapper, custom forward, hand-written attention, causal mask, cache append, cache reshape, cache conversion, position-ID computation, sampling model, or tokenizer model.
- The fixed cache_position tensors [0, 1, 2, 3, 4, 5, 6, 7], [8], and [9] are trace inputs passed through the documented source-model API. Each call also receives an all-valid attention_mask of length 8, 9, or 10, matching the fixed valid cache length. Do not infer a causal mask or provide position_ids; the source model retains its normal handling of both.
- Use only transformers.integrations.executorch.register_dynamic_cache_export_support() to make the current DynamicCache a PyTorch-export PyTree. Do not call register_pytree_node directly and do not introduce a cache ABI shim in this phase.
- Treat every DynamicCache object as mutable. Snapshot cache leaves immediately after each call, and regenerate a fresh native cache for every eager/export comparison. A reference to C8 must never be used after decode-8 as evidence for C8.
- Before the PT2E probe passes all three phases, every bundle manifest must say numeric_format: native-fp32-source and quantization_status: unproven. The W8A8 substring in the requested model key is an intended line of investigation, not evidence that a quantized artifact exists.
- Do not modify TinyStories/model_adapter_quantized_representative_core_pt2e_w8a8.py, TinyStories/pt2e_w8a8_study.py, TinyStories/rc_working_contract.py, scripts/materialize-pytorch-exported.py, scripts/compile-pytorch.py, nix/models.nix, nix/pipeline.nix, or nix/rc-working-system.nix.
- The generic materializer remains a single-program tool. Do not add a stage flag, a phase flag, or a multi-export mode to it. The serving bundle has its own materializer and its own Nix derivations.
- Do not create a root tinystories-w8a8-rc-serving-mask10-vocab6-width2-torch package, pipeline alias, generated-SV package, or claimed FPGA cache store in this plan.
- Generated SV chaining with a host/testbench cache service is a follow-on plan after this plan's direct export and frontend feasibility evidence. A persistent RTL cache store is a later, separate follow-on plan.
- Use the existing Nix development environment for tests that import PyTorch or Transformers: nix develop -c python -m unittest. Stage and commit only files named in each task.

---

## Scope boundary and subsequent plans

This plan covers the first independently testable subsystem: source-model
construction, fixed native trace, native-cache evidence, direct torch.export
artifacts, and the cache-aware PT2E W8A8 feasibility result.

It intentionally ends before the following independent subsystems:

1. Torch-MLIR frontend admission and a generated-SV prefill-to-decode harness
   that retains cache bytes in a host/testbench service.
2. A persistent RTL cache-store component with reset, invalidation,
   read-after-write, schema, bounds, and byte-image tests.

If direct export fails, publish its exact receipt and stop. If direct export
passes but the PT2E probe is blocked, publish that as a W8A8 frontier and stop.
Neither condition authorizes a rewritten source model or an unlabelled
floating-point or quantized substitution.

## File structure

| File | Responsibility |
| --- | --- |
| TinyStories/rc_serving_contract.py | Frozen profile constants, trace parsing, phase metadata, token validation, and deterministic lowest-index argmax. |
| TinyStories/rc_serving_trace_input.json | The one immutable prompt and three fixed phase descriptors. |
| TinyStories/rc_serving_source.py | Build the unwrapped native model, form its documented call arguments, execute a native call, and regenerate a fresh phase invocation. |
| TinyStories/rc_serving_evidence.py | Official DynamicCache PyTree registration, byte-exact tensor/cache snapshots, cache-prefix checks, and native trace execution. |
| scripts/pipeline/build_rc_serving_reference.py | Materialize the repeated deterministic native-reference receipt. |
| TinyStories/rc_serving_direct_export.py | Export and execute one direct native-cache phase without a model wrapper, then compare it to an eager phase. |
| scripts/pipeline/materialize_rc_serving_direct_exports.py | Write the three-program bundle and its manifests, cache schema, source copies, and direct-export conformance receipts. |
| nix/rc-serving-system.nix | Dedicated serving-RC profile metadata and Nix derivations; it is deliberately outside the generic model registry. |
| scripts/pipeline/probe_rc_serving_pt2e_w8a8.py | Record cache-aware PT2E XNNPACK progress or the first blocking exception without manufacturing a quantized export. |
| scripts/pipeline/assess_rc_serving_phase1.py | Join the three receipts into the explicit stop/go decision for the next planning phase. |
| flake.nix | Import the dedicated system and expose only accurately named source, direct-export, probe, and evidence packages. |
| docs/glossary.md | Distinguish the static compiler RC from the stateful serving RC. |
| tests/test_rc_serving_*.py | Unit, integration-contract, artifact-layout, Nix-wiring, probe, and stop/go regressions. |

## Receipt contracts

All receipts in this plan use schema_version 1 and the exact model key.
The native-reference receipt has this stable shape:

~~~json
{
  "schema_version": 1,
  "artifact_kind": "native-serving-reference",
  "model_key": "tinystories-w8a8-rc-serving-mask10-vocab6-width2",
  "numeric_format": "native-fp32-source",
  "quantization_status": "unproven",
  "trace": {
    "prompt_token_ids": [0, 1, 2, 3, 4, 5, 0, 1],
    "phases": ["prefill-8", "decode-8", "decode-9"]
  },
  "native_cache_schema": {
    "native_type": "transformers.cache_utils.DynamicCache",
    "tree_spec": "recorded PyTree representation",
    "leaf_count": 4,
    "leaves": []
  },
  "phases": [],
  "generate_conformance": {}
}
~~~

Each phase record contains name, input_token_ids, cache_length_before,
cache_length_after, cache_position, last_logits, greedy_token_id, and
cache_snapshot. A tensor record has dtype, shape, byte_count, sha256, and
little_endian_hex. A cache leaf record additionally has ordinal and path. The
actual receipts contain real values for every digest and hex string.

The direct-export bundle layout is fixed:

~~~text
bundle/
  manifest.json
  native-cache-schema.json
  reference.json
  source/
    rc_serving_contract.py
    rc_serving_source.py
    rc_serving_evidence.py
    rc_serving_direct_export.py
  prefill-8/
    exported.pt2
    exported-program.txt
    graph.txt
    graph-module.py
    graph-signature.txt
    manifest.json
    conformance.json
  decode-8/
    exported.pt2
    exported-program.txt
    graph.txt
    graph-module.py
    graph-signature.txt
    manifest.json
    conformance.json
  decode-9/
    exported.pt2
    exported-program.txt
    graph.txt
    graph-module.py
    graph-signature.txt
    manifest.json
    conformance.json
~~~

The PT2E probe always writes probe.json. Its status is one of blocked,
ready-for-manual-review, or invalid-direct-export. A blocked receipt records
phase, step, exception_type, and message; it is a successful diagnostic
derivation, not a successful quantized export.

### Task 1: Freeze the new profile and trace contract

**Files:**

- Create: TinyStories/rc_serving_contract.py
- Create: TinyStories/rc_serving_trace_input.json
- Create: tests/test_rc_serving_contract.py

**Interfaces:**

- Produces: SERVING_RC_MODEL_KEY, VOCAB_SIZE, NUM_LAYERS,
  MAX_POSITION_EMBEDDINGS, WINDOW_SIZE, HIDDEN_SIZE, NUM_HEADS,
  PREFILL_LENGTH, DECODE_STEPS, ServingPhase, load_trace(path),
  phase_by_name(name), validate_token_ids(values, expected_length), and
  argmax_lowest(values).
- ServingPhase is an immutable dataclass with name, input_length,
  cache_length_before, cache_length_after, and cache_positions.
- Consumed later by rc_serving_source.py, the native reference builder, the
  direct-export materializer, and the PT2E probe.

- [ ] **Step 1: Write the failing contract tests**

  Create tests/test_rc_serving_contract.py with exact profile, phase, token,
  tie-break, and isolation assertions:

  ~~~python
  import unittest
  from pathlib import Path

  from TinyStories import rc_serving_contract as contract


  ROOT = Path(__file__).resolve().parents[1]
  TRACE = ROOT / "TinyStories" / "rc_serving_trace_input.json"


  class RcServingContractTest(unittest.TestCase):
      def test_profile_and_trace_are_fixed(self) -> None:
          trace = contract.load_trace(TRACE)
          self.assertEqual(
              contract.SERVING_RC_MODEL_KEY,
              "tinystories-w8a8-rc-serving-mask10-vocab6-width2",
          )
          self.assertEqual(
              (contract.VOCAB_SIZE, contract.NUM_LAYERS, contract.HIDDEN_SIZE,
               contract.NUM_HEADS, contract.MAX_POSITION_EMBEDDINGS,
               contract.WINDOW_SIZE),
              (6, 2, 2, 1, 10, 256),
          )
          self.assertEqual(trace.prompt_token_ids, (0, 1, 2, 3, 4, 5, 0, 1))
          self.assertEqual(
              [(phase.name, phase.input_length, phase.cache_length_before,
                phase.cache_length_after, phase.cache_positions)
               for phase in trace.phases],
              [
                  ("prefill-8", 8, 0, 8, (0, 1, 2, 3, 4, 5, 6, 7)),
                  ("decode-8", 1, 8, 9, (8,)),
                  ("decode-9", 1, 9, 10, (9,)),
              ],
          )

      def test_token_validation_and_ties_are_deterministic(self) -> None:
          self.assertEqual(
              contract.argmax_lowest([-2.0, 1.0, 1.0, 0.0, -3.0, 0.5]), 1
          )
          self.assertEqual(contract.validate_token_ids([0, 5], 2), (0, 5))
          with self.assertRaisesRegex(ValueError, "expected exactly 8"):
              contract.validate_token_ids([0] * 7, 8)
          with self.assertRaisesRegex(ValueError, "range"):
              contract.validate_token_ids([0, 1, 2, 3, 4, 5, 0, 6], 8)

      def test_old_stateless_rc_is_not_retargeted(self) -> None:
          old_adapter = (
              ROOT / "TinyStories"
              / "model_adapter_quantized_representative_core_pt2e_w8a8.py"
          ).read_text(encoding="utf-8")
          old_contract = (ROOT / "TinyStories" / "rc_working_contract.py").read_text(
              encoding="utf-8"
          )
          self.assertIn("config.use_cache = False", old_adapter)
          self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", old_contract)
          self.assertNotIn(contract.SERVING_RC_MODEL_KEY, old_adapter)
          self.assertNotIn(contract.SERVING_RC_MODEL_KEY, old_contract)


  if __name__ == "__main__":
      unittest.main()
  ~~~

- [ ] **Step 2: Run the contract test to prove it is red**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_contract.py -v
  ~~~

  Expected: import failure because TinyStories.rc_serving_contract does not
  exist.

- [ ] **Step 3: Add the immutable JSON fixture**

  Create TinyStories/rc_serving_trace_input.json with this complete content:

  ~~~json
  {
    "schema_version": 1,
    "model_key": "tinystories-w8a8-rc-serving-mask10-vocab6-width2",
    "purpose": "stateful-serving-native-cache-trace",
    "prompt_token_ids": [0, 1, 2, 3, 4, 5, 0, 1],
    "phases": [
      {
        "name": "prefill-8",
        "input_length": 8,
        "cache_length_before": 0,
        "cache_length_after": 8,
        "cache_positions": [0, 1, 2, 3, 4, 5, 6, 7]
      },
      {
        "name": "decode-8",
        "input_length": 1,
        "cache_length_before": 8,
        "cache_length_after": 9,
        "cache_positions": [8]
      },
      {
        "name": "decode-9",
        "input_length": 1,
        "cache_length_before": 9,
        "cache_length_after": 10,
        "cache_positions": [9]
      }
    ]
  }
  ~~~

- [ ] **Step 4: Implement the contract module**

  Use immutable dataclasses and reject any fixture that does not exactly match
  the fixed profile. The core public definitions are:

  ~~~python
  SERVING_RC_MODEL_KEY = "tinystories-w8a8-rc-serving-mask10-vocab6-width2"
  VOCAB_SIZE = 6
  NUM_LAYERS = 2
  MAX_POSITION_EMBEDDINGS = 10
  WINDOW_SIZE = 256
  HIDDEN_SIZE = 2
  NUM_HEADS = 1
  PREFILL_LENGTH = 8
  DECODE_STEPS = 2


  @dataclass(frozen=True)
  class ServingPhase:
      name: str
      input_length: int
      cache_length_before: int
      cache_length_after: int
      cache_positions: tuple[int, ...]


  @dataclass(frozen=True)
  class ServingTrace:
      prompt_token_ids: tuple[int, ...]
      phases: tuple[ServingPhase, ...]


  def argmax_lowest(values: Sequence[float]) -> int:
      if len(values) != VOCAB_SIZE:
          raise ValueError("expected exactly 6 logits")
      normalized = tuple(float(value) for value in values)
      if not all(math.isfinite(value) for value in normalized):
          raise ValueError("logits must be finite")
      return max(range(VOCAB_SIZE), key=lambda index: (normalized[index], -index))
  ~~~

  load_trace must reject a wrong schema version, model key, purpose, prompt
  length, token ID, phase order, input length, cache length, or position list.
  phase_by_name must accept only the three names above and reject every other
  value.

- [ ] **Step 5: Re-run the focused contract test**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_contract.py -v
  ~~~

  Expected: PASS.

- [ ] **Step 6: Commit the frozen profile contract**

  Run:

  ~~~bash
  git add TinyStories/rc_serving_contract.py TinyStories/rc_serving_trace_input.json tests/test_rc_serving_contract.py
  git commit -m "feat: freeze stateful serving RC contract"
  ~~~

### Task 2: Build the native source trace and immutable cache evidence

**Files:**

- Create: TinyStories/rc_serving_source.py
- Create: TinyStories/rc_serving_evidence.py
- Create: scripts/pipeline/build_rc_serving_reference.py
- Create: tests/test_rc_serving_reference.py

**Interfaces:**

- Consumes: ServingTrace and a pinned TinyStories config snapshot.
- Produces: build_source_model(model_path), native_call_kwargs(phase,
  past_key_values), run_native_call(model, phase, input_ids,
  past_key_values), fresh_phase_invocation(model, trace, phase_name),
  enable_hf_dynamic_cache_export_support(), snapshot_native_cache(cache),
  run_native_trace(model, trace), and build_reference(model_path,
  trace_path).
- fresh_phase_invocation returns a dataclass with phase, input_ids, and the
  actual source-returned past_key_values; it never rebuilds cache values from
  serialised leaves.
- build_reference returns the receipt schema described above and does not
  quantize, export, or lower the model.

- [ ] **Step 1: Write the failing source/reference tests**

  Create tests/test_rc_serving_reference.py. Use a recording native-call
  double for the call ABI and a tensor-mutation check for immutable evidence:

  ~~~python
  import hashlib
  import unittest

  import torch

  from TinyStories import rc_serving_contract as contract
  from TinyStories import rc_serving_evidence as evidence
  from TinyStories import rc_serving_source as source


  class RecordingModel:
      def __init__(self) -> None:
          self.calls = []

      def __call__(self, input_ids, **kwargs):
          self.calls.append((input_ids.clone(), kwargs))
          next_cache = [torch.tensor([len(self.calls)], dtype=torch.int64)]
          return (torch.zeros((1, input_ids.shape[1], 6)), next_cache)


  class RcServingReferenceTest(unittest.TestCase):
      def test_native_call_uses_only_the_source_api_boundary(self) -> None:
          model = RecordingModel()
          phase = contract.phase_by_name("prefill-8")
          logits, returned_cache = source.run_native_call(
              model, phase, torch.zeros((1, 8), dtype=torch.long), None
          )

          self.assertEqual(tuple(logits.shape), (1, 8, 6))
          self.assertEqual(returned_cache[0].item(), 1)
          _, kwargs = model.calls[0]
          self.assertIsNone(kwargs["past_key_values"])
          self.assertTrue(kwargs["use_cache"])
          self.assertFalse(kwargs["return_dict"])
          self.assertTrue(torch.equal(kwargs["cache_position"], torch.arange(8)))
          self.assertTrue(
              torch.equal(
                  kwargs["attention_mask"], torch.ones((1, 8), dtype=torch.long)
              )
          )
          self.assertNotIn("position_ids", kwargs)

      def test_tensor_record_survives_later_in_place_mutation(self) -> None:
          value = torch.tensor([1, 2, 3], dtype=torch.int8)
          record = evidence.tensor_record(value)
          value[0] = 9
          self.assertEqual(record["little_endian_hex"], "010203")
          self.assertEqual(
              record["sha256"], hashlib.sha256(bytes([1, 2, 3])).hexdigest()
          )

      def test_reference_schema_requires_all_three_cache_lengths(self) -> None:
          trace = contract.ServingTrace(
              prompt_token_ids=(0, 1, 2, 3, 4, 5, 0, 1),
              phases=tuple(
                  contract.phase_by_name(name)
                  for name in ("prefill-8", "decode-8", "decode-9")
              ),
          )
          self.assertEqual(
              [phase.cache_length_after for phase in trace.phases], [8, 9, 10]
          )


  if __name__ == "__main__":
      unittest.main()
  ~~~

- [ ] **Step 2: Run the source/reference test to prove it is red**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_reference.py -v
  ~~~

  Expected: import failure because the source and evidence modules do not
  exist.

- [ ] **Step 3: Implement native model construction and native calls**

  In TinyStories/rc_serving_source.py, duplicate only the configuration
  assignment needed to create this new profile. Do not import the old
  stateless adapter. The source model implementation must look like this:

  ~~~python
  def build_source_model(model_path: str | Path) -> torch.nn.Module:
      config = AutoConfig.from_pretrained(model_path, local_files_only=True)
      config.vocab_size = VOCAB_SIZE
      config.num_layers = NUM_LAYERS
      config.max_position_embeddings = MAX_POSITION_EMBEDDINGS
      config.window_size = WINDOW_SIZE
      config.hidden_size = HIDDEN_SIZE
      config.num_heads = NUM_HEADS
      config.attention_types = attention_types_for_layers(config.num_layers)
      config.attention_layers = config.expand_attention_types_params(
          config.attention_types
      )
      config.use_cache = True
      config.bos_token_id = VOCAB_SIZE - 1
      config.eos_token_id = VOCAB_SIZE - 1
      torch.manual_seed(0)
      return AutoModelForCausalLM.from_config(config).eval()


  def native_call_kwargs(
      phase: ServingPhase, past_key_values: object | None
  ) -> dict[str, object]:
      return {
          "past_key_values": past_key_values,
          "use_cache": True,
          "return_dict": False,
          "cache_position": torch.tensor(
              phase.cache_positions, dtype=torch.long
          ),
      }


  def run_native_call(
      model: object,
      phase: ServingPhase,
      input_ids: torch.Tensor,
      past_key_values: object | None,
  ) -> tuple[torch.Tensor, object]:
      output = model(
          input_ids, **native_call_kwargs(phase, past_key_values)
      )
      if not isinstance(output, tuple) or len(output) < 2:
          raise RuntimeError("native source model did not return logits and cache")
      logits, returned_cache = output[0], output[1]
      if not isinstance(logits, torch.Tensor):
          raise RuntimeError("native source model logits are not a tensor")
      return logits, returned_cache
  ~~~

  Add PhaseInvocation and fresh_phase_invocation. For decode-8, it must execute
  a new prefill from an empty cache. For decode-9, it must execute a new
  prefill and a new decode-8. It must compute feedback only with
  argmax_lowest(last_logits.tolist()) and use the exact next-token tensor shape
  [1, 1].

- [ ] **Step 4: Implement evidence capture and the reference builder**

  enable_hf_dynamic_cache_export_support must use the official Transformers
  integration exactly:

  ~~~python
  def enable_hf_dynamic_cache_export_support() -> None:
      from transformers.integrations.executorch import (
          register_dynamic_cache_export_support,
      )

      register_dynamic_cache_export_support()
  ~~~

  tensor_record must detach, copy to CPU, make contiguous, view as unsigned
  bytes, and record the bytes before the caller can mutate its source tensor:

  ~~~python
  def tensor_record(tensor: torch.Tensor) -> dict[str, object]:
      detached = tensor.detach().cpu().contiguous()
      raw = bytes(detached.view(torch.uint8).reshape(-1).tolist())
      return {
          "dtype": str(detached.dtype),
          "shape": [int(dimension) for dimension in detached.shape],
          "byte_count": len(raw),
          "sha256": hashlib.sha256(raw).hexdigest(),
          "little_endian_hex": raw.hex(),
      }
  ~~~

  snapshot_native_cache must call tree_flatten_with_path(cache) after the
  official registration. It records the native type, stringified tree spec,
  leaf count, and each leaf's ordinal, path, and tensor_record. It must reject
  a non-tensor leaf and an empty leaf list. Preserve detached tensor clones
  internally so assert_cache_prefix_unchanged can compare C8 to C9 and C9 to
  C10 without rereading a mutated DynamicCache object.

  run_native_trace executes the three calls in order. It snapshots C8 before
  decode-8, snapshots C9 before decode-9, then snapshots C10. It discovers the
  one growing sequence dimension by comparing each C8/C9 leaf shape and
  requires exactly one dimension to grow from 8 to 9 and then from 9 to 10.
  It compares the valid prefix of every leaf along that observed dimension
  byte-for-byte. It records only final-position logits and the deterministic
  greedy token for each phase.

  build_rc_serving_reference.py accepts --model-path, --trace, and --out;
  builds the ordinary source model; invokes run_native_trace; runs
  model.generate with do_sample=False, max_new_tokens=2, use_cache=True, and
  eos_token_id=None so a greedy EOS-valued token cannot shorten the frozen
  two-step trace; and rejects a mismatch with the two manually chained greedy
  tokens. It writes sorted, newline-terminated JSON.

- [ ] **Step 5: Re-run source/reference tests**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_reference.py -v
  ~~~

  Expected: PASS.

- [ ] **Step 6: Commit the native reference subsystem**

  Run:

  ~~~bash
  git add TinyStories/rc_serving_source.py TinyStories/rc_serving_evidence.py scripts/pipeline/build_rc_serving_reference.py tests/test_rc_serving_reference.py
  git commit -m "feat: add native serving RC reference trace"
  ~~~

### Task 3: Materialize and verify the three direct native-cache exports

**Files:**

- Create: TinyStories/rc_serving_direct_export.py
- Create: scripts/pipeline/materialize_rc_serving_direct_exports.py
- Create: tests/test_rc_serving_direct_export.py

**Interfaces:**

- Consumes: the native source helpers, the frozen trace, and a native reference
  receipt.
- Produces: export_direct_phase(model, invocation),
  compare_eager_and_exported_phase(model, exported, invocation), and
  materialize_direct_export_bundle(model_path, trace_path, reference_path,
  out_dir).
- The exported object is the unwrapped AutoModelForCausalLM object. Its public
  input/output cache container remains DynamicCache after loading and calling
  ExportedProgram.module().

- [ ] **Step 1: Write the failing direct-export tests**

  Create tests/test_rc_serving_direct_export.py with the following
  artifact-contract assertions:

  ~~~python
  import tempfile
  import unittest
  from pathlib import Path

  from TinyStories import rc_serving_direct_export as direct


  class RcServingDirectExportTest(unittest.TestCase):
      def test_bundle_manifest_requires_three_named_phase_directories(self) -> None:
          with tempfile.TemporaryDirectory() as directory:
              root = Path(directory)
              for name in ("prefill-8", "decode-8", "decode-9"):
                  (root / name).mkdir()
              manifest = direct.bundle_manifest(
                  root,
                  {
                      "prefill-8": "a" * 64,
                      "decode-8": "b" * 64,
                      "decode-9": "c" * 64,
                  },
              )
              self.assertEqual(
                  [phase["name"] for phase in manifest["phases"]],
                  ["prefill-8", "decode-8", "decode-9"],
              )
              self.assertEqual(
                  manifest["artifact_kind"], "direct-native-cache-export-bundle"
              )
              self.assertEqual(manifest["numeric_format"], "native-fp32-source")
              self.assertEqual(manifest["quantization_status"], "unproven")

      def test_materializer_is_not_the_generic_single_program_materializer(self) -> None:
          root = Path(__file__).resolve().parents[1]
          source = (
              root / "scripts" / "pipeline"
              / "materialize_rc_serving_direct_exports.py"
          ).read_text(encoding="utf-8")
          self.assertNotIn("materialize-pytorch-exported.py", source)
          self.assertIn("prefill-8", source)
          self.assertIn("decode-8", source)
          self.assertIn("decode-9", source)


  if __name__ == "__main__":
      unittest.main()
  ~~~

- [ ] **Step 2: Run the direct-export test to prove it is red**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_direct_export.py -v
  ~~~

  Expected: import failure because rc_serving_direct_export does not exist.

- [ ] **Step 3: Implement direct export and exact per-phase conformance**

  The direct exporter must register only the official DynamicCache support and
  export the original model object:

  ~~~python
  def export_direct_phase(
      model: torch.nn.Module, invocation: PhaseInvocation
  ) -> torch.export.ExportedProgram:
      enable_hf_dynamic_cache_export_support()
      return torch.export.export(
          model,
          (invocation.input_ids,),
          kwargs=native_call_kwargs(
              invocation.phase, invocation.past_key_values
          ),
          strict=False,
      )
  ~~~

  Do not define a wrapper class or a replacement forward. For every phase,
  compare_eager_and_exported_phase must:

  1. call fresh_phase_invocation for the eager run;
  2. snapshot the eager logits/cache before the next source call can mutate it,
     then require that complete record to equal the corresponding native
     reference phase;
  3. call fresh_phase_invocation again for the exported run;
  4. call exported.module() with the same documented arguments;
  5. require the exported result to be a tuple of logits and the same native
     cache type;
  6. compare final logits and every cache leaf using exact sha256 and
     little_endian_hex equality; and
  7. require cache leaf count, leaf paths, dtypes, and shapes to match the
     native reference schema.

  An output that exposes only flattened leaves, changes cache type, changes a
  leaf schema, or differs by one byte is a failure of direct conformance. It is
  not an invitation to add a shim.

- [ ] **Step 4: Implement the dedicated bundle materializer**

  materialize_rc_serving_direct_exports.py accepts exactly:

  ~~~text
  --model-path PATH
  --trace PATH
  --reference PATH
  --out-dir PATH
  ~~~

  It first loads and validates the native reference receipt. It then builds a
  fresh source model, independently exports the three named phases, saves each
  program as PHASE/exported.pt2, writes text graph artifacts, and writes
  PHASE/conformance.json. Copy the four named serving source files into the
  bundle's source directory. Write a root native-cache-schema.json from the
  native reference and a root manifest whose phase digest values are computed
  from the three actual exported.pt2 files.

  The root manifest must calculate each phase digest from the actual file:

  ~~~python
  def phase_manifest(name: str, phase_dir: Path) -> dict[str, str]:
      return {
          "name": name,
          "path": name,
          "exported_program_sha256": sha256_file(phase_dir / "exported.pt2"),
      }


  {
      "schema_version": 1,
      "artifact_kind": "direct-native-cache-export-bundle",
      "model_key": SERVING_RC_MODEL_KEY,
      "numeric_format": "native-fp32-source",
      "quantization_status": "unproven",
      "phases": [
          phase_manifest("prefill-8", out_dir / "prefill-8"),
          phase_manifest("decode-8", out_dir / "decode-8"),
          phase_manifest("decode-9", out_dir / "decode-9"),
      ],
  }
  ~~~

- [ ] **Step 5: Re-run the direct-export test and the native reference test**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_direct_export.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_reference.py -v
  ~~~

  Expected: PASS.

- [ ] **Step 6: Commit the direct-export subsystem**

  Run:

  ~~~bash
  git add TinyStories/rc_serving_direct_export.py scripts/pipeline/materialize_rc_serving_direct_exports.py tests/test_rc_serving_direct_export.py
  git commit -m "feat: materialize direct serving cache exports"
  ~~~

### Task 4: Register the serving bundle in independent Nix derivations

**Files:**

- Create: nix/rc-serving-system.nix
- Modify: flake.nix
- Modify: docs/glossary.md
- Create: tests/test_rc_serving_nix_wiring.py

**Interfaces:**

- Produces Nix attributes modelMetadata, nativeReference, directExportBundle,
  prefill8PytorchExported, decode8PytorchExported, and
  decode9PytorchExported.
- The phase attributes are symlink packages that expose the corresponding
  phase directory from directExportBundle; each contains one exported.pt2.
- directExportBundle is the only root multi-program artifact. It cannot be
  passed to the generic mkTorchStage.

- [ ] **Step 1: Write the failing Nix-wiring test**

  Create tests/test_rc_serving_nix_wiring.py:

  ~~~python
  import unittest
  from pathlib import Path


  ROOT = Path(__file__).resolve().parents[1]
  KEY = "tinystories-w8a8-rc-serving-mask10-vocab6-width2"


  class RcServingNixWiringTest(unittest.TestCase):
      def test_dedicated_system_keeps_serving_bundle_out_of_generic_registry(self) -> None:
          system = (ROOT / "nix" / "rc-serving-system.nix").read_text(
              encoding="utf-8"
          )
          models = (ROOT / "nix" / "models.nix").read_text(encoding="utf-8")
          pipeline = (ROOT / "nix" / "pipeline.nix").read_text(encoding="utf-8")
          self.assertIn(KEY, system)
          self.assertIn("directExportBundle", system)
          self.assertIn("prefill8PytorchExported", system)
          self.assertIn("decode8PytorchExported", system)
          self.assertIn("decode9PytorchExported", system)
          self.assertNotIn(KEY, models)
          self.assertNotIn(KEY, pipeline)

      def test_flake_exposes_only_named_source_and_phase_artifacts(self) -> None:
          flake = (ROOT / "flake.nix").read_text(encoding="utf-8")
          self.assertIn("rcServingSystem", flake)
          self.assertIn(KEY + "-native-reference", flake)
          self.assertIn(KEY + "-direct-export-bundle", flake)
          self.assertIn(KEY + "-prefill-8-pytorch-exported", flake)
          self.assertIn(KEY + "-decode-8-pytorch-exported", flake)
          self.assertIn(KEY + "-decode-9-pytorch-exported", flake)
          self.assertNotIn(KEY + "-torch", flake)


  if __name__ == "__main__":
      unittest.main()
  ~~~

- [ ] **Step 2: Run the Nix-wiring test to prove it is red**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_nix_wiring.py -v
  ~~~

  Expected: file-not-found failure for nix/rc-serving-system.nix.

- [ ] **Step 3: Implement the dedicated Nix system**

  Create nix/rc-serving-system.nix as a standalone attrset taking pkgs,
  pythonWithTinyStoriesTorchAO, tinyStories1m, and sourceRoot. Define the
  model metadata with the requested W8A8 intent but no false quantization
  claim:

  ~~~nix
  modelMetadata = pkgs.writeText "tinystories-w8a8-rc-serving-mask10-vocab6-width2-metadata.json" (builtins.toJSON {
    schema_version = 1;
    model_key = "tinystories-w8a8-rc-serving-mask10-vocab6-width2";
    artifact_kind = "stateful-serving-profile";
    source = {
      type = "derived";
      profile = "stateful-serving-representative-core";
      base_model_id = tinyStories1m.modelId;
      revision = tinyStories1m.revision;
      vocab_size = 6;
      num_layers = 2;
      hidden_size = 2;
      num_heads = 1;
      window_size = 256;
      max_position_embeddings = 10;
      prompt_length = 8;
      decode_steps = 2;
    };
    quantization = {
      requested = "pt2e-static-w8a8";
      status = "probe-required";
    };
  });
  ~~~

  nativeReference runs the reference builder twice, byte-compares its two
  reference.json files, and exposes one canonical reference.json.
  directExportBundle depends on nativeReference and invokes the dedicated
  materializer with the pinned model snapshot, trace fixture, and canonical
  reference. The three phase packages are read-only symlink derivations to
  directExportBundle/prefill-8, directExportBundle/decode-8, and
  directExportBundle/decode-9.

  Each derivation exports PYTHONPATH with sourceRoot, uses
  pythonWithTinyStoriesTorchAO, and writes to its Nix output only. Do not
  import nix/models.nix or nix/pipeline.nix.

- [ ] **Step 4: Wire only the named packages and glossary entry**

  In flake.nix, import the new system beside rcWorkingSystem. Add exactly these
  public package names:

  ~~~text
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-metadata
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-native-reference
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-direct-export-bundle
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-prefill-8-pytorch-exported
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-decode-8-pytorch-exported
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-decode-9-pytorch-exported
  ~~~

  Do not add an entry to modelRegistry, pipelineAliasSpecs, or a generic stage
  package map. Update docs/glossary.md with one definition:

  ~~~text
  Stateful serving RC — tinystories-w8a8-rc-serving-mask10-vocab6-width2,
  the independent V=6, two-layer, width-two source-model trace for one
  prefill and two cached greedy decodes. It proves only the stated
  native/export state protocol; it is not the static W8A8 RC oracle or an
  FPGA-serving result.
  ~~~

- [ ] **Step 5: Re-run the Nix-wiring test and build source/direct artifacts**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_nix_wiring.py -v
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-native-reference -L --no-link
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-direct-export-bundle -L --no-link
  ~~~

  Expected: all tests pass; both Nix builds succeed; the direct bundle contains
  three phase directories and no root exported.pt2.

- [ ] **Step 6: Commit the independent Nix registration**

  Run:

  ~~~bash
  git add nix/rc-serving-system.nix flake.nix docs/glossary.md tests/test_rc_serving_nix_wiring.py
  git commit -m "feat: register stateful serving RC export bundle"
  ~~~

### Task 5: Probe cache-aware PT2E W8A8 without making a false export claim

**Files:**

- Create: scripts/pipeline/probe_rc_serving_pt2e_w8a8.py
- Create: tests/test_rc_serving_pt2e_probe.py
- Modify: nix/rc-serving-system.nix
- Modify: flake.nix

**Interfaces:**

- Consumes: the accepted direct-export bundle and native reference.
- Produces: probe_pt2e_w8a8(model_path, trace_path, direct_bundle,
  reference_path, out_dir) and probe.json.
- A blocked result has no exported.pt2 accepted artifact. A
  ready-for-manual-review result may preserve diagnostics and phase files, but
  still does not create a generic frontend package.

- [ ] **Step 1: Write the failing PT2E probe tests**

  Create tests/test_rc_serving_pt2e_probe.py with an injected conversion
  failure and an explicit no-promotion assertion:

  ~~~python
  import unittest

  from scripts.pipeline import probe_rc_serving_pt2e_w8a8 as probe


  class RcServingPt2eProbeTest(unittest.TestCase):
      def test_convert_failure_is_a_durable_blocker_receipt(self) -> None:
          def fail_convert(prepared):
              raise AttributeError("'object' object has no attribute 'dtype'")

          receipt = probe.run_phase_probe(
              phase_name="prefill-8",
              export_step=lambda: object(),
              prepare_step=lambda exported: object(),
              calibrate_step=lambda prepared: None,
              convert_step=fail_convert,
              reexport_step=lambda converted: object(),
              compare_step=lambda exported: None,
          )

          self.assertEqual(receipt["status"], "blocked")
          self.assertEqual(receipt["phase"], "prefill-8")
          self.assertEqual(receipt["step"], "convert_pt2e")
          self.assertEqual(receipt["exception_type"], "AttributeError")
          self.assertIn("dtype", receipt["message"])

      def test_only_all_phase_success_is_ready_for_manual_review(self) -> None:
          receipts = [
              {"status": "passed", "phase": name}
              for name in ("prefill-8", "decode-8", "decode-9")
          ]
          result = probe.summarize_probe(receipts)
          self.assertEqual(result["status"], "ready-for-manual-review")
          self.assertFalse(result["frontend_eligible"])


  if __name__ == "__main__":
      unittest.main()
  ~~~

- [ ] **Step 2: Run the PT2E probe test to prove it is red**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_pt2e_probe.py -v
  ~~~

  Expected: import failure because the probe script does not exist.

- [ ] **Step 3: Implement the explicit PT2E probe**

  Use a local phase-specific copy of the existing XNNPACK configuration, not
  export_pt2e_w8a8, because that helper requires one output and strips one
  terminal dequantize. The conversion configuration is:

  ~~~python
  quantizer = XNNPACKQuantizer().set_global(
      get_symmetric_quantization_config(
          is_dynamic=False,
          act_qmin=-128,
          act_qmax=127,
          weight_qmin=-128,
          weight_qmax=127,
      )
  )
  ~~~

  For each phase, first make a fresh native invocation and direct export. Then
  execute these named steps in order:

  ~~~python
  prepared = prepare_pt2e(exported.module(), quantizer)
  prepared(*invocation_args, **invocation_kwargs)
  converted = convert_pt2e(prepared)
  move_exported_model_to_eval(converted)
  reexported = torch.export.export(
      converted, invocation_args, kwargs=invocation_kwargs, strict=False
  )
  compare_eager_and_exported_phase(model, reexported, fresh_invocation)
  ~~~

  run_phase_probe catches every exception, returns the phase and exact step,
  and serializes exception type and message. It must not catch an exception and
  write a success status. summarize_probe returns blocked at the first blocked
  phase; otherwise it returns ready-for-manual-review with
  frontend_eligible: false.

  The root probe.json includes the direct-bundle manifest SHA-256, native
  reference SHA-256, PyTorch/Transformers/TorchAO versions, all completed phase
  receipts, and its first failure. With the currently pinned stack, a receipt
  blocked at prefill-8 / convert_pt2e with an AttributeError mentioning dtype
  is the expected frontier result. Do not normalize that exception into a
  fabricated converted program.

- [ ] **Step 4: Add the diagnostic Nix package**

  Extend nix/rc-serving-system.nix with pt2eW8a8Probe. It depends on the native
  reference and direct bundle, invokes the probe script, and always preserves
  probe.json. The derivation exits nonzero only for an invalid direct
  bundle/reference mismatch; a known quantization blocker produces an output
  derivation with status: blocked.

  Expose exactly one additional package in flake.nix:

  ~~~text
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-pt2e-w8a8-probe
  ~~~

- [ ] **Step 5: Run the focused test and actual probe**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_pt2e_probe.py -v
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-pt2e-w8a8-probe -L --no-link
  ~~~

  Expected: the unit test passes. The Nix package succeeds as a diagnostic and
  its probe.json reports blocked at convert_pt2e on the current pinned stack,
  unless the pinned tools have changed; any changed result must be reviewed
  before it is promoted.

- [ ] **Step 6: Commit the W8A8 feasibility probe**

  Run:

  ~~~bash
  git add scripts/pipeline/probe_rc_serving_pt2e_w8a8.py tests/test_rc_serving_pt2e_probe.py nix/rc-serving-system.nix flake.nix
  git commit -m "test: record serving RC PT2E feasibility frontier"
  ~~~

### Task 6: Publish the Phase 1 stop/go evidence package

**Files:**

- Create: scripts/pipeline/assess_rc_serving_phase1.py
- Create: tests/test_rc_serving_phase1.py
- Modify: nix/rc-serving-system.nix
- Modify: flake.nix

**Interfaces:**

- Consumes: the native reference receipt, direct-export bundle manifest, and
  PT2E probe receipt.
- Produces: result.json and result.md in the
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-phase1-evidence package.
- Status values are exactly direct-export-accepted-w8a8-blocked,
  direct-export-accepted-w8a8-review-required, or invalid-direct-export. All
  have frontend_eligible: false.

- [ ] **Step 1: Write the failing Phase 1 assessment test**

  Create tests/test_rc_serving_phase1.py:

  ~~~python
  import unittest

  from scripts.pipeline import assess_rc_serving_phase1 as assess


  class RcServingPhase1Test(unittest.TestCase):
      def test_blocked_w8a8_never_becomes_frontend_eligible(self) -> None:
          result = assess.assess(
              reference={"model_key": assess.MODEL_KEY, "phases": [{}, {}, {}]},
              bundle={
                  "model_key": assess.MODEL_KEY,
                  "artifact_kind": "direct-native-cache-export-bundle",
                  "phases": [
                      {"name": "prefill-8"},
                      {"name": "decode-8"},
                      {"name": "decode-9"},
                  ],
              },
              probe={
                  "model_key": assess.MODEL_KEY,
                  "status": "blocked",
                  "first_failure": {
                      "phase": "prefill-8",
                      "step": "convert_pt2e",
                  },
              },
          )
          self.assertEqual(result["status"], "direct-export-accepted-w8a8-blocked")
          self.assertFalse(result["frontend_eligible"])
          self.assertEqual(
              result["next_action"],
              "stop; publish the PT2E blocker before frontend or SV work",
          )


  if __name__ == "__main__":
      unittest.main()
  ~~~

- [ ] **Step 2: Run the Phase 1 assessment test to prove it is red**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_phase1.py -v
  ~~~

  Expected: import failure because the assessor does not exist.

- [ ] **Step 3: Implement the exact stop/go policy**

  assess must first require the model key in all inputs, the native reference to
  have three phases, the direct bundle artifact kind to match exactly, and the
  ordered phase names to be prefill-8, decode-8, decode-9. A failed
  precondition produces invalid-direct-export and frontend_eligible: false.

  The successful direct-export cases are:

  ~~~python
  if probe["status"] == "blocked":
      status = "direct-export-accepted-w8a8-blocked"
      next_action = "stop; publish the PT2E blocker before frontend or SV work"
  elif probe["status"] == "ready-for-manual-review":
      status = "direct-export-accepted-w8a8-review-required"
      next_action = "review quantized cache outputs before creating a frontend plan"
  else:
      status = "invalid-direct-export"
      next_action = "repair receipt consistency before any frontend work"
  ~~~

  result.md must state the model key, three direct-export phase names, PT2E
  status, first failure when present, and the exact next action. It must never
  call the artifact an FPGA implementation, generated SV, a persistent cache
  store, or a successful W8A8 export while the probe is blocked.

- [ ] **Step 4: Add and expose the evidence derivation**

  Extend nix/rc-serving-system.nix with phase1Evidence, which calls the
  assessor on the three Nix inputs and writes result.json and result.md.
  Expose exactly:

  ~~~text
  tinystories-w8a8-rc-serving-mask10-vocab6-width2-phase1-evidence
  ~~~

  The derivation must remain successful for the known blocked result so the
  failure evidence is reproducible and inspectable.

- [ ] **Step 5: Run the focused, isolation, and evidence verification**

  Run:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_phase1.py -v
  nix develop -c python -m unittest discover -s tests -p test_pipeline_clarity.py -v
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-phase1-evidence -L --no-link
  git diff --check
  ~~~

  Expected: all unit tests pass; the generic pipeline clarity test remains
  unchanged; the evidence package reports direct-export-accepted-w8a8-blocked
  on the current pinned stack and keeps frontend_eligible false.

- [ ] **Step 6: Commit the Phase 1 evidence policy**

  Run:

  ~~~bash
  git add scripts/pipeline/assess_rc_serving_phase1.py tests/test_rc_serving_phase1.py nix/rc-serving-system.nix flake.nix
  git commit -m "docs: gate stateful serving RC after direct export"
  ~~~

## Final verification checklist

- [ ] Run all new focused tests:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_contract.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_reference.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_direct_export.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_nix_wiring.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_pt2e_probe.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_serving_phase1.py -v
  ~~~

- [ ] Run the existing isolation regression:

  ~~~bash
  nix develop -c python -m unittest discover -s tests -p test_rc_working_contract.py -v
  nix develop -c python -m unittest discover -s tests -p test_rc_working_nix_wiring.py -v
  nix develop -c python -m unittest discover -s tests -p test_pipeline_clarity.py -v
  ~~~

- [ ] Build the three decisive Nix artifacts:

  ~~~bash
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-native-reference -L --no-link
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-direct-export-bundle -L --no-link
  nix build .#tinystories-w8a8-rc-serving-mask10-vocab6-width2-phase1-evidence -L --no-link
  ~~~

- [ ] Inspect the emitted result.json. Do not start a frontend, SV, or RTL
  cache-store implementation unless it provides an explicit Phase 1 result and
  a separate approved plan.
