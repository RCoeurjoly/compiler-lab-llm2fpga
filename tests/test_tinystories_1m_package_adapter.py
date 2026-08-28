"""Tests for the authenticated TinyStories-1M package export adapter."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "TinyStories" / "model_adapter_reference_package.py"
MATERIALIZER = ROOT / "scripts" / "comparison" / "materialize_tinystories_1m_package_export.py"
CONTRACT = ROOT / "artifacts" / "reference" / "tinystories-1m-kev-gpt-contract.json"
PACKAGE = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
MODEL = Path(
    "/home/roland/.cache/huggingface/hub/"
    "models--roneneldan--TinyStories-1M/snapshots/"
    "77f1b168e219585646439073245fe87e56b3023e"
)


def load_adapter():
    spec = importlib.util.spec_from_file_location("model_adapter_reference_package", ADAPTER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(PACKAGE.is_dir() and MODEL.is_dir(), "frozen package/model inputs unavailable")
class TinyStories1MPackageAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = load_adapter()
        cls.bundle = cls.adapter.load_authenticated_package(CONTRACT, PACKAGE, MODEL)

    def test_total_mapping_matches_gpt_neo_state_and_tied_head(self) -> None:
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        mapping = self.bundle.receipt["tensor_mapping"]

        self.assertEqual(set(mapping), set(manifest["tensors"]))
        self.assertEqual(len(mapping), 108)
        self.assertEqual(mapping["token_embedding.weight"]["target"], "transformer.wte.weight")
        self.assertEqual(mapping["blocks.0.attn.q.weight"]["target"], "transformer.h.0.attn.attention.q_proj.weight")
        self.assertEqual(mapping["blocks.7.mlp.proj.bias"]["target"], "transformer.h.7.mlp.c_proj.bias")
        self.assertEqual(self.bundle.receipt["tied_parameters"], {"lm_head.weight": "transformer.wte.weight"})
        self.assertEqual(set(self.bundle.state_dict), set(self.bundle.model.state_dict()))
        self.assertTrue(torch.equal(self.bundle.state_dict["lm_head.weight"], self.bundle.state_dict["transformer.wte.weight"]))

    def test_int8_weight_uses_little_endian_float32_per_output_scale(self) -> None:
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        entry = manifest["tensors"]["blocks.0.attn.k.weight"]
        weight_bytes = (PACKAGE / "weights.bin").read_bytes()
        scale_bytes = (PACKAGE / "scales.bin").read_bytes()
        quantized = struct.unpack_from("b", weight_bytes, entry["offset"])[0]
        scale = struct.unpack_from("<f", scale_bytes, entry["scale_offset"])[0]
        expected = struct.unpack("<f", struct.pack("<f", quantized * scale))[0]

        actual = self.bundle.state_dict["transformer.h.0.attn.attention.k_proj.weight"][0, 0].item()
        self.assertEqual(actual, expected)
        self.assertEqual(self.bundle.receipt["quantization"]["int8_weight_tensor_count"], 50)
        self.assertEqual(self.bundle.receipt["quantization"]["scale_format"], "little-endian float32")

    def test_all_activation_boundaries_are_explicit_and_content_bound(self) -> None:
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        boundaries = self.bundle.receipt["activation_qdq_boundaries"]

        self.assertEqual(set(boundaries), set(manifest["activation_scales"]))
        self.assertEqual(len(boundaries), 97)
        self.assertEqual({entry["width"] for entry in boundaries.values()}, {64, 256})
        for name, entry in boundaries.items():
            self.assertEqual(entry["scales"], manifest["activation_scales"][name])
            self.assertEqual(entry["sha256"], self.adapter.canonical_sha256(entry["scales"]))
        self.assertEqual(
            self.bundle.receipt["activation_qdq_execution"],
            {"status": "metadata_only", "reason_code": "activation_rounding_semantics_unavailable"},
        )

    def test_receipt_preserves_all_frozen_identities(self) -> None:
        contract = json.loads(CONTRACT.read_text())
        identity = self.bundle.receipt["identity"]

        self.assertEqual(identity["contract_sha256"], hashlib.sha256(CONTRACT.read_bytes()).hexdigest())
        self.assertEqual(identity["model"], contract["model"])
        self.assertEqual(identity["tokenizer"], contract["tokenizer"])
        self.assertEqual(identity["package"], contract["package"])
        self.assertEqual(self.bundle.receipt["receipt_sha256"], self.adapter.receipt_sha256(self.bundle.receipt))

    def test_frozen_verifier_rejects_tamper_before_adapter_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = Path(temp_dir) / "package"
            shutil.copytree(PACKAGE, candidate)
            manifest = json.loads((candidate / "manifest.json").read_text())
            manifest["tensors"].pop(next(iter(manifest["tensors"])))
            (candidate / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))

            with self.assertRaisesRegex(Exception, "package_hash_mismatch"):
                self.adapter.load_authenticated_package(CONTRACT, candidate, MODEL)

    def test_reconstruction_rejects_missing_extra_shape_and_scale_corruption(self) -> None:
        manifest = json.loads((PACKAGE / "manifest.json").read_text())
        weights = (PACKAGE / "weights.bin").read_bytes()
        scales = (PACKAGE / "scales.bin").read_bytes()
        target_shapes = {name: tuple(tensor.shape) for name, tensor in self.bundle.model.state_dict().items()}

        cases: list[tuple[str, dict[str, object], bytes]] = []
        missing = copy.deepcopy(manifest)
        missing["tensors"].pop("blocks.0.attn.k.weight")
        cases.append(("source_tensor_set_mismatch", missing, scales))
        extra = copy.deepcopy(manifest)
        extra["tensors"]["unexpected.weight"] = copy.deepcopy(extra["tensors"]["blocks.0.attn.k.weight"])
        cases.append(("source_tensor_set_mismatch", extra, scales))
        wrong_shape = copy.deepcopy(manifest)
        wrong_shape["tensors"]["blocks.0.attn.k.weight"]["logical_shape"] = [32, 128]
        cases.append(("tensor_shape_mismatch", wrong_shape, scales))
        malformed_scale = copy.deepcopy(manifest)
        malformed_scale["tensors"]["blocks.0.attn.k.weight"]["scale_nbytes"] -= 4
        cases.append(("malformed_scale_image", malformed_scale, scales))
        nonfinite_scale = bytearray(scales)
        scale_offset = manifest["tensors"]["blocks.0.attn.k.weight"]["scale_offset"]
        struct.pack_into("<f", nonfinite_scale, scale_offset, math.nan)
        nonfinite_manifest = copy.deepcopy(manifest)
        scale_nbytes = manifest["tensors"]["blocks.0.attn.k.weight"]["scale_nbytes"]
        nonfinite_manifest["tensors"]["blocks.0.attn.k.weight"]["scale_sha256"] = hashlib.sha256(
            nonfinite_scale[scale_offset : scale_offset + scale_nbytes]
        ).hexdigest()
        cases.append(("non_finite_tensor", nonfinite_manifest, bytes(nonfinite_scale)))

        for code, candidate, candidate_scales in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(self.adapter.PackageAdapterError, code):
                    self.adapter.reconstruct_state_dict(candidate, weights, candidate_scales, target_shapes)

    def test_numeric_trace_matches_export_at_all_required_checkpoints(self) -> None:
        gate = self.adapter.build_numeric_trace_gate(self.bundle)

        self.assertEqual(gate["status"], "matched")
        self.assertEqual(gate["schema"], "tinystories-1m-package-export-trace-v1")
        self.assertEqual(list(gate["checkpoints"]), list(self.adapter.CHECKPOINT_SHAPES))
        for name, shape in self.adapter.CHECKPOINT_SHAPES.items():
            checkpoint = gate["checkpoints"][name]
            self.assertEqual(checkpoint["shape"], list(shape))
            self.assertEqual(checkpoint["package_reconstruction_sha256"], checkpoint["exported_program_sha256"])
            self.assertEqual(checkpoint["package_reconstruction"], checkpoint["exported_program"])
        self.assertEqual(gate["trace_sha256"], self.adapter.trace_sha256(gate))

        prompt = torch.tensor([self.bundle.contract["reference"]["prompt_tokens"]], dtype=torch.long)
        with torch.no_grad():
            model_block_output = self.bundle.model(
                prompt, output_hidden_states=True
            ).hidden_states[1][0, -1].tolist()
        self.assertEqual(gate["checkpoints"]["block.output"]["package_reconstruction"], model_block_output)

    def test_frozen_prompt_first_token_is_preserved(self) -> None:
        prompt = torch.tensor([self.bundle.contract["reference"]["prompt_tokens"]], dtype=torch.long)
        with torch.no_grad():
            token = int(torch.argmax(self.bundle.model(prompt).logits[0, -1]))
        self.assertEqual(token, self.bundle.contract["reference"]["tokens"][0])

    def test_materializer_emits_loadable_export_receipt_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "export"
            completed = subprocess.run(
                [
                    "python",
                    str(MATERIALIZER),
                    "--contract",
                    str(CONTRACT),
                    "--package",
                    str(PACKAGE),
                    "--model-path",
                    str(MODEL),
                    "--out-dir",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            receipt = json.loads((output / "adapter-receipt.json").read_text())
            trace = json.loads((output / "numeric-trace.json").read_text())
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="The given buffer is not writable")
                exported = torch.export.load(output / "exported.pt2")
            prompt = torch.tensor([receipt["example_input"]["prompt_tokens"]], dtype=torch.long)

            self.assertEqual(receipt["receipt_sha256"], self.adapter.receipt_sha256(receipt))
            self.assertEqual(trace["status"], "matched")
            with torch.no_grad():
                replayed_logits = exported.module()(prompt)
                reconstructed_logits = self.bundle.model(prompt).logits
            self.assertEqual(tuple(replayed_logits.shape), (1, 4, 50257))
            self.assertTrue(torch.equal(replayed_logits, reconstructed_logits))


if __name__ == "__main__":
    unittest.main()
