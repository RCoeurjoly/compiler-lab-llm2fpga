"""Strict loader for the frozen TinyStories-1M reference contract."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "artifacts" / "reference" / "tinystories-1m-kev-gpt-contract.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_REQUEST_FIELDS = [
    {"name": "magic", "kind": "fixed", "byte_offset": 0, "byte_width": 2, "encoding": "u16"},
    {"name": "version", "kind": "fixed", "byte_offset": 2, "byte_width": 1, "encoding": "u8"},
    {"name": "command", "kind": "fixed", "byte_offset": 3, "byte_width": 1, "encoding": "u8"},
    {"name": "prompt_count", "kind": "fixed", "byte_offset": 4, "byte_width": 1, "encoding": "u8"},
    {"name": "generation_count", "kind": "fixed", "byte_offset": 5, "byte_width": 1, "encoding": "u8"},
    {"name": "prompt_tokens", "kind": "variable_array", "byte_offset": 6, "byte_width": 2, "encoding": "u16", "count_field": "prompt_count"},
]
EXPECTED_REPLY_FIELDS = [
    {"name": "magic", "kind": "fixed", "byte_offset": 0, "byte_width": 2, "encoding": "u16"},
    {"name": "version", "kind": "fixed", "byte_offset": 2, "byte_width": 1, "encoding": "u8"},
    {"name": "status", "kind": "fixed", "byte_offset": 3, "byte_width": 1, "encoding": "u8"},
    {"name": "token_count", "kind": "fixed", "byte_offset": 4, "byte_width": 1, "encoding": "u8"},
    {"name": "cycles", "kind": "fixed", "byte_offset": 5, "byte_width": 8, "encoding": "u64"},
    {"name": "output_tokens", "kind": "variable_array", "byte_offset": 13, "byte_width": 2, "encoding": "u16", "count_field": "token_count"},
]
EXPECTED_TOKENS = [11, 612, 373, 257, 1310, 2576, 3706, 20037, 13, 1375, 6151, 284, 711, 2354, 287, 262]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_exact_object(value: object, keys: set[str], path: str) -> dict:
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must be an object")
    missing = keys - value.keys()
    extra = value.keys() - keys
    if missing or extra:
        raise AssertionError(f"{path} has invalid fields: missing={sorted(missing)}, extra={sorted(extra)}")
    return value


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError(f"duplicate JSON object field: {key}")
        result[key] = value
    return result


def _validate_fields(fields: object, expected: list[dict], path: str) -> None:
    if not isinstance(fields, list) or len(fields) != len(expected):
        raise AssertionError(f"{path} has an invalid field count")
    for index, (field, expected_field) in enumerate(zip(fields, expected, strict=True)):
        keys = set(expected_field)
        actual = _require_exact_object(field, keys, f"{path}[{index}]")
        for key in ("byte_offset", "byte_width"):
            if not _is_int(actual[key]) or actual[key] < 0:
                raise AssertionError(f"{path}[{index}].{key} is malformed")
        if actual != expected_field:
            raise AssertionError(f"{path} must have the frozen ordered, non-overlapping layout")


def _validate_frame(frame: object, expected: dict, path: str) -> None:
    actual = _require_exact_object(frame, set(expected), path)
    total_length = _require_exact_object(actual["total_length"], set(expected["total_length"]), f"{path}.total_length")
    for key in ("header_bytes", "token_payload_offset", "token_count_min", "token_count_max", "token_element_bytes"):
        if not _is_int(actual[key]) or actual[key] < 0:
            raise AssertionError(f"{path}.{key} is malformed")
    for key in ("base_bytes", "element_bytes"):
        if not _is_int(total_length[key]) or total_length[key] < 0:
            raise AssertionError(f"{path}.total_length.{key} is malformed")
    if "generation_count_min" in actual:
        for key in ("generation_count_min", "generation_count_max", "prompt_plus_generation_max"):
            if not _is_int(actual[key]) or actual[key] < 0:
                raise AssertionError(f"{path}.{key} is malformed")
    if actual != expected:
        raise AssertionError(f"{path} is inconsistent with the frozen ABI")


def load_contract(path: Path | None = None) -> dict:
    path = CONTRACT_PATH if path is None else path
    if not path.is_file():
        raise AssertionError(f"missing reference contract: {path}")
    contract = json.loads(path.read_text(), object_pairs_hook=_reject_duplicate_json_keys)
    _require_exact_object(contract, {"schema_version", "status", "model", "package", "tokenizer", "quantization", "memory_image", "command_abi", "reference", "baseline", "incomplete_reasons"}, "contract")
    if contract["schema_version"] != 1 or contract["status"] != "incomplete":
        raise AssertionError("invalid contract header")

    model = _require_exact_object(contract["model"], {"name", "architecture", "source_model_id", "source_revision", "n_layer", "hidden_size", "n_head", "head_dim", "vocab_size", "max_context", "tie_word_embeddings", "activation_function"}, "model")
    expected_model = {"name": "TinyStories-1M", "n_layer": 8, "hidden_size": 64, "n_head": 16, "head_dim": 4, "vocab_size": 50257, "max_context": 32}
    if any(model[key] != value for key, value in expected_model.items()):
        raise AssertionError("model identity changed")
    if any(not _is_int(model[key]) for key in ("n_layer", "hidden_size", "n_head", "head_dim", "vocab_size", "max_context")):
        raise AssertionError("model dimensions must be integers")
    if not isinstance(model["tie_word_embeddings"], bool) or any(not isinstance(model[key], str) or not model[key] for key in ("name", "architecture", "source_model_id", "source_revision", "activation_function")) or not re.fullmatch(r"[0-9a-f]{40}", model["source_revision"]):
        raise AssertionError("model metadata is malformed")

    package = _require_exact_object(contract["package"], {"origin", "manifest_sha256", "sha256", "files"}, "package")
    if not isinstance(package["origin"], str) or not package["origin"] or any(not isinstance(package[key], str) or not SHA256.fullmatch(package[key]) for key in ("manifest_sha256", "sha256")):
        raise AssertionError("package identity is malformed")
    package_files = _require_exact_object(package["files"], {"manifest.json", "weights.bin", "scales.bin", "calibration_ids.bin", "receipt.json"}, "package.files")
    if any(not isinstance(digest, str) or not SHA256.fullmatch(digest) for digest in package_files.values()):
        raise AssertionError("package file digest is malformed")

    tokenizer = _require_exact_object(contract["tokenizer"], {"type", "sha256", "vocab_sha256", "merges_sha256", "add_bos_token", "add_prefix_space"}, "tokenizer")
    if not isinstance(tokenizer["type"], str) or not tokenizer["type"] or any(not isinstance(tokenizer[key], str) or not SHA256.fullmatch(tokenizer[key]) for key in ("sha256", "vocab_sha256", "merges_sha256")) or not isinstance(tokenizer["add_bos_token"], bool) or not isinstance(tokenizer["add_prefix_space"], bool):
        raise AssertionError("tokenizer is malformed")

    quantization = _require_exact_object(contract["quantization"], {"weights", "activations", "accumulator", "scale_format", "scale_image_sha256"}, "quantization")
    if any(not isinstance(quantization[key], str) or not quantization[key] for key in ("weights", "activations", "accumulator", "scale_format")) or not isinstance(quantization["scale_image_sha256"], str) or not SHA256.fullmatch(quantization["scale_image_sha256"]):
        raise AssertionError("quantization is malformed")
    memory_image = _require_exact_object(contract["memory_image"], {"format", "sha256", "bytes"}, "memory_image")
    if not isinstance(memory_image["format"], str) or not memory_image["format"] or not isinstance(memory_image["sha256"], str) or not SHA256.fullmatch(memory_image["sha256"]) or not _is_int(memory_image["bytes"]) or memory_image["bytes"] <= 0:
        raise AssertionError("memory image is malformed")

    abi = _require_exact_object(contract["command_abi"], {"request_magic_u16", "reply_magic_u16", "version", "command_encodings", "status_encodings", "max_context", "token_id_bits", "generation_count_bits", "cycle_count_bits", "byte_order", "bit_order", "bit_packing", "request_fields", "reply_fields", "request_frame", "reply_frame", "crc32"}, "command_abi")
    if any(not _is_int(abi[key]) for key in ("request_magic_u16", "reply_magic_u16", "version", "max_context", "token_id_bits", "generation_count_bits", "cycle_count_bits")) or (abi["request_magic_u16"], abi["reply_magic_u16"], abi["version"], abi["max_context"], abi["token_id_bits"], abi["generation_count_bits"], abi["cycle_count_bits"]) != (19271, 19282, 1, 32, 16, 8, 64):
        raise AssertionError("ABI scalar values changed")
    if _require_exact_object(abi["command_encodings"], {"infer"}, "command_abi.command_encodings") != {"infer": 1} or _require_exact_object(abi["status_encodings"], {"ok"}, "command_abi.status_encodings") != {"ok": 0}:
        raise AssertionError("ABI command/status encodings changed")
    if abi["byte_order"] != "little" or abi["bit_order"] != "lsb0" or abi["bit_packing"] != "none":
        raise AssertionError("ABI integer packing changed")
    _validate_fields(abi["request_fields"], EXPECTED_REQUEST_FIELDS, "command_abi.request_fields")
    _validate_fields(abi["reply_fields"], EXPECTED_REPLY_FIELDS, "command_abi.reply_fields")
    _validate_frame(abi["request_frame"], {"header_bytes": 6, "token_payload_offset": 6, "token_count_field": "prompt_count", "token_count_min": 1, "token_count_max": 32, "token_element_bytes": 2, "token_element_encoding": "u16", "generation_count_min": 1, "generation_count_max": 32, "prompt_plus_generation_max": 32, "total_length": {"operator": "base_plus_count_times_element_bytes", "base_bytes": 10, "count_field": "prompt_count", "element_bytes": 2}}, "command_abi.request_frame")
    _validate_frame(abi["reply_frame"], {"header_bytes": 13, "token_payload_offset": 13, "token_count_field": "token_count", "token_count_min": 0, "token_count_max": 32, "token_element_bytes": 2, "token_element_encoding": "u16", "ok_token_count_rule": "equals_request_generation_count", "total_length": {"operator": "base_plus_count_times_element_bytes", "base_bytes": 17, "count_field": "token_count", "element_bytes": 2}}, "command_abi.reply_frame")
    crc = _require_exact_object(abi["crc32"], {"algorithm", "polynomial_reflected_u32", "initial_value_u32", "final_xor_u32", "reflected_input", "reflected_output", "coverage", "trailer_placement", "trailer_offset", "trailer_byte_width", "trailer_integer_encoding", "trailer_byte_order"}, "command_abi.crc32")
    coverage = _require_exact_object(crc["coverage"], {"start_offset", "end_offset"}, "command_abi.crc32.coverage")
    trailer_offset = _require_exact_object(crc["trailer_offset"], {"operator", "constant_bytes"}, "command_abi.crc32.trailer_offset")
    if any(not _is_int(crc[key]) for key in ("polynomial_reflected_u32", "initial_value_u32", "final_xor_u32", "trailer_byte_width")) or not _is_int(coverage["start_offset"]) or not _is_int(trailer_offset["constant_bytes"]) or crc != {"algorithm": "CRC-32/IEEE", "polynomial_reflected_u32": 3988292384, "initial_value_u32": 4294967295, "final_xor_u32": 4294967295, "reflected_input": True, "reflected_output": True, "coverage": {"start_offset": 0, "end_offset": "crc_trailer_start_exclusive"}, "trailer_placement": "immediately_after_payload", "trailer_offset": {"operator": "total_bytes_minus_constant", "constant_bytes": 4}, "trailer_byte_width": 4, "trailer_integer_encoding": "u32", "trailer_byte_order": "little"}:
        raise AssertionError("ABI CRC-32/IEEE definition changed")

    reference = _require_exact_object(contract["reference"], {"prompt_text", "prompt_tokens", "tokens", "generation", "reference_impl", "reference_trace"}, "reference")
    if reference["prompt_text"] != "Once upon a time" or reference["prompt_tokens"] != [7454, 2402, 257, 640] or reference["tokens"] != EXPECTED_TOKENS or any(not _is_int(token) for token in reference["tokens"]) or not isinstance(reference["generation"], str) or not isinstance(reference["reference_impl"], str):
        raise AssertionError("reference fixture changed or is malformed")
    trace = _require_exact_object(reference["reference_trace"], {"status", "sha256", "reason"}, "reference.reference_trace")
    if trace["status"] != "unavailable" or trace["sha256"] is not None or not isinstance(trace["reason"], str) or not trace["reason"]:
        raise AssertionError("reference trace evidence is not honestly unavailable")

    baseline = _require_exact_object(contract["baseline"], {"status", "cycles_per_token", "clock_mhz", "throughput_tokens_per_second", "resources", "source", "reason"}, "baseline")
    if baseline["status"] != "unavailable" or any(baseline[key] is not None for key in ("cycles_per_token", "clock_mhz", "throughput_tokens_per_second", "resources", "source")) or not isinstance(baseline["reason"], str) or not baseline["reason"]:
        raise AssertionError("baseline evidence is not honestly unavailable")
    reasons = contract["incomplete_reasons"]
    if not isinstance(reasons, list) or len(reasons) != 2 or any(not isinstance(reason, str) or not reason for reason in reasons) or not any("trace" in reason for reason in reasons) or not any("timing/resource" in reason for reason in reasons):
        raise AssertionError("incomplete contract must identify trace and timing/resource blockers")
    return contract


class TinyStoriesReferenceContractTest(unittest.TestCase):
    def test_abi_is_a_complete_machine_readable_wire_definition(self) -> None:
        abi = load_contract()["command_abi"]
        self.assertEqual(
            set(abi),
            {
                "request_magic_u16",
                "reply_magic_u16",
                "version",
                "command_encodings",
                "status_encodings",
                "max_context",
                "token_id_bits",
                "generation_count_bits",
                "cycle_count_bits",
                "byte_order",
                "bit_order",
                "bit_packing",
                "request_fields",
                "reply_fields",
                "request_frame",
                "reply_frame",
                "crc32",
            },
        )
        self.assertEqual(abi["command_encodings"], {"infer": 1})
        self.assertEqual(abi["byte_order"], "little")
        self.assertEqual(abi["bit_order"], "lsb0")
        self.assertEqual(abi["bit_packing"], "none")
        self.assertEqual(abi["request_frame"]["total_length"], {
            "operator": "base_plus_count_times_element_bytes",
            "base_bytes": 10,
            "count_field": "prompt_count",
            "element_bytes": 2,
        })
        self.assertEqual(abi["reply_frame"]["total_length"], {
            "operator": "base_plus_count_times_element_bytes",
            "base_bytes": 17,
            "count_field": "token_count",
            "element_bytes": 2,
        })
        self.assertEqual(abi["crc32"]["trailer_placement"], "immediately_after_payload")
        self.assertEqual(abi["crc32"]["trailer_byte_order"], "little")

    def test_contract_contains_frozen_1m_identity(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["model"]["name"], "TinyStories-1M")
        self.assertEqual(contract["model"]["n_layer"], 8)
        self.assertEqual(contract["model"]["hidden_size"], 64)
        self.assertEqual(len(contract["reference"]["tokens"]), 16)

    def test_contract_is_explicitly_incomplete_without_unmeasured_baseline(self) -> None:
        contract = load_contract()
        self.assertEqual(contract["status"], "incomplete")
        self.assertTrue(any("baseline" in reason for reason in contract["incomplete_reasons"]))

    def test_loader_rejects_nested_hash_and_abi_corruption(self) -> None:
        original = CONTRACT_PATH.read_text()
        value = json.loads(original)
        for path, replacement in [
            (("package", "files", "weights.bin"), "not-a-hash"),
            (("package", "files", "extra.bin"), "f" * 64),
            (("tokenizer", "vocab_sha256"), "f" * 63),
            (("tokenizer", "type"), 7),
            (("quantization", "scale_image_sha256"), "f" * 65),
            (("command_abi", "request_magic"), "4b47"),
            (("command_abi", "command"), 1),
            (("command_abi", "crc32"), "zlib"),
            (("command_abi", "byte_order"), 1),
            (("command_abi", "request_fields", 0), "magic"),
            (("command_abi", "framing"), None),
            (("command_abi", "crc_algorithm"), None),
            (("memory_image", "format"), None),
            (("model", "source_revision"), "deadbeef"),
            (("reference", "tokens", 0), True),
        ]:
            candidate = deepcopy(value)
            cursor = candidate
            for key in path[:-1]:
                cursor = cursor[key]
            cursor[path[-1]] = replacement
            with tempfile.TemporaryDirectory() as temp:
                temp_path = Path(temp) / "contract.json"
                temp_path.write_text(json.dumps(candidate))
                with self.assertRaises(AssertionError):
                    load_contract(temp_path)

    def test_loader_rejects_every_abi_layout_and_framing_failure_class(self) -> None:
        original = json.loads(CONTRACT_PATH.read_text())

        def reject(mutator) -> None:
            candidate = deepcopy(original)
            mutator(candidate)
            with tempfile.TemporaryDirectory() as temp:
                temp_path = Path(temp) / "contract.json"
                temp_path.write_text(json.dumps(candidate))
                with self.assertRaises(AssertionError):
                    load_contract(temp_path)

        mutations = [
            lambda c: c["command_abi"].update({"extra": 1}),
            lambda c: c["command_abi"]["command_encodings"].update({"reset": 2}),
            lambda c: c["command_abi"]["command_encodings"].update({"infer": 0}),
            lambda c: c["command_abi"].update({"byte_order": "big"}),
            lambda c: c["command_abi"].update({"bit_packing": "packed"}),
            lambda c: c["command_abi"]["request_fields"].append(deepcopy(c["command_abi"]["request_fields"][0])),
            lambda c: c["command_abi"]["request_fields"][1].update({"byte_offset": 0}),
            lambda c: c["command_abi"]["request_fields"].__setitem__(slice(0, 2), list(reversed(c["command_abi"]["request_fields"][:2]))),
            lambda c: c["command_abi"]["request_fields"][1].update({"byte_width": True}),
            lambda c: c["command_abi"]["request_fields"][5].update({"byte_offset": 7}),
            lambda c: c["command_abi"]["request_frame"].update({"token_count_max": 31}),
            lambda c: c["command_abi"]["request_frame"]["total_length"].update({"base_bytes": 11}),
            lambda c: c["command_abi"]["reply_frame"].update({"token_payload_offset": 12}),
            lambda c: c["command_abi"]["reply_frame"]["total_length"].update({"element_bytes": 1}),
            lambda c: c["command_abi"]["crc32"].update({"trailer_placement": "before_payload"}),
            lambda c: c["command_abi"]["crc32"].update({"trailer_byte_order": "big"}),
            lambda c: c["command_abi"]["crc32"]["coverage"].update({"end_offset": "frame_end"}),
            lambda c: c["command_abi"]["crc32"]["trailer_offset"].update({"constant_bytes": 3}),
            lambda c: c["command_abi"]["crc32"].update({"extra": 1}),
            lambda c: c["reference"]["reference_trace"].update({"status": "available"}),
            lambda c: c["baseline"].update({"resources": {}}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                reject(mutation)

    def test_loader_rejects_duplicate_json_object_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp) / "contract.json"
            temp_path.write_text('{"schema_version": 1, "schema_version": 1}')
            with self.assertRaises(AssertionError):
                load_contract(temp_path)


if __name__ == "__main__":
    unittest.main()
