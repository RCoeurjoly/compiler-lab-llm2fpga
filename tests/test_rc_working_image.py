import hashlib
import importlib.util
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKER_PATH = REPO_ROOT / "scripts" / "pipeline" / "pack_rc_working_image.py"
VERIFIER_PATH = REPO_ROOT / "scripts" / "pipeline" / "verify_rc_working_image.py"
REFERENCE_BUILDER_PATH = (
    REPO_ROOT / "scripts" / "pipeline" / "build_rc_working_reference.py"
)


def _load_module(path: Path, module_name: str):
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packer = _load_module(PACKER_PATH, "pack_rc_working_image")
verifier = _load_module(VERIFIER_PATH, "verify_rc_working_image")
reference_builder = _load_module(REFERENCE_BUILDER_PATH, "build_rc_working_reference")


class _FakeNumpyArray:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self, order: str = "C") -> bytes:
        if order != "C":
            raise ValueError("only C order is supported by this test double")
        return self._payload


class _FakeTensor:
    def __init__(self, dtype: str, shape: tuple[int, ...], payload: bytes) -> None:
        self.dtype = dtype
        self.shape = shape
        self._payload = payload

    def detach(self):
        return self

    def cpu(self):
        return self

    def contiguous(self):
        return self

    def numpy(self) -> _FakeNumpyArray:
        return _FakeNumpyArray(self._payload)


class _FakeExported:
    def __init__(self, state_dict: dict[str, _FakeTensor]) -> None:
        self.state_dict = state_dict
        self.constants: dict[str, _FakeTensor] = {}


class RcWorkingImageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(
            packer,
            "scripts/pipeline/pack_rc_working_image.py must define the image packer",
        )
        self.assertIsNotNone(
            verifier,
            "scripts/pipeline/verify_rc_working_image.py must define image replay",
        )

    def _named_tensors(self) -> dict[str, _FakeTensor]:
        return {
            "state/weights": _FakeTensor("torch.int8", (4,), bytes([1, 2, 3, 4])),
            "constants/output_scale": _FakeTensor(
                "torch.float32", (), struct.pack("<f", 0.25)
            ),
        }

    def test_packer_aligns_and_hashes_segments(self) -> None:
        manifest, payload = packer.pack_named_tensors(self._named_tensors())

        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["alignment_bytes"], 64)
        self.assertEqual(manifest["segments"][0]["name"], "constants/output_scale")
        self.assertEqual(manifest["segments"][1]["name"], "state/weights")
        self.assertEqual(manifest["segments"][1]["offset"] % 64, 0)
        self.assertEqual(manifest["segments"][0]["dtype"], "float32")
        self.assertEqual(manifest["segments"][0]["shape"], [])
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(), manifest["image_sha256"]
        )
        self.assertEqual(
            hashlib.sha256(payload[64:68]).hexdigest(),
            manifest["segments"][1]["sha256"],
        )

    def test_packer_is_deterministic_and_detects_a_modified_image_byte(self) -> None:
        first_manifest, first_payload = packer.pack_named_tensors(self._named_tensors())
        second_manifest, second_payload = packer.pack_named_tensors(self._named_tensors())

        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_payload, second_payload)
        packer.verify_image_bytes(first_manifest, first_payload)

        modified = bytearray(first_payload)
        modified[64] ^= 0x01
        with self.assertRaises(ValueError):
            packer.verify_image_bytes(first_manifest, bytes(modified))

    def test_replay_rejects_a_missing_exported_state_item(self) -> None:
        state = {
            "first": _FakeTensor("torch.int8", (1,), b"\x11"),
            "second": _FakeTensor("torch.int8", (1,), b"\x22"),
        }
        manifest, payload = packer.pack_named_tensors({"state/first": state["first"]})

        with self.assertRaisesRegex(ValueError, "state/second"):
            verifier.reconstruct_state(_FakeExported(state), manifest, payload)

    def test_replay_comparator_requires_exact_codes_and_token_id(self) -> None:
        self.assertTrue(
            hasattr(verifier, "compare_reference_results"),
            "image replay must compare every raw code and the chosen token ID",
        )
        expected = {
            "results": [
                {
                    "case_id": "ascending",
                    "output_codes_i8": [-4, 5, 5, 1, 0, -2],
                    "token_id": 1,
                }
            ]
        }
        observed = [
            {
                "case_id": "ascending",
                "output_codes_i8": [-4, 5, 5, 1, 0, -2],
                "token_id": 1,
            }
        ]

        self.assertEqual(
            verifier.compare_reference_results(expected, observed)["status"], "pass"
        )
        observed[0]["output_codes_i8"][0] = -3
        mismatch = verifier.compare_reference_results(expected, observed)
        self.assertEqual(mismatch["status"], "mismatch")
        self.assertEqual(mismatch["cases"][0]["status"], "mismatch")


class RcWorkingReferenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(
            reference_builder,
            "scripts/pipeline/build_rc_working_reference.py must build the PT2E oracle",
        )

    def test_extracts_terminal_output_quantization_parameters_from_the_graph(self) -> None:
        terminal_quantize = SimpleNamespace(
            op="call_function",
            target="quantized_decomposed.quantize_per_tensor.default",
            args=("logits", 0.125, -4, -128, 127, "torch.int8"),
        )
        exported = SimpleNamespace(
            graph=SimpleNamespace(
                nodes=[
                    terminal_quantize,
                    SimpleNamespace(op="output", target=None, args=((terminal_quantize,),)),
                ]
            )
        )

        self.assertEqual(
            reference_builder.extract_terminal_output_qparams(exported),
            {"scale": 0.125, "zero_point": -4},
        )


if __name__ == "__main__":
    unittest.main()
