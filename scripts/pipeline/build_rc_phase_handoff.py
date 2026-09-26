"""Build the typed memory/token/cache ABI for compiler-generated RC phases."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.pipeline.run_rc_serving_w4a8_sv import (
    memory_words,
    parse_flat_scf_abi,
    parse_flat_scf_global_bindings,
    parse_sv_memory_ports,
    runtime_values,
    tensor_payload,
    validate_abi,
)


PHASES = ("prefill-8", "decode-8", "decode-9")
SCHEMA = "rc-serving-w4a8-compiler-phase-abi-v1"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _count(shape: tuple[int, ...] | list[int]) -> int:
    return math.prod(shape)


def build_handoff(abi: dict, phases: dict[str, dict]) -> dict:
    """Validate parsed phase artifacts and return a serializable RTL handoff map."""
    if abi.get("schema") != SCHEMA:
        raise ValueError("unsupported compiler phase ABI schema")
    entries = abi.get("phases")
    if not isinstance(entries, list) or tuple(entry.get("name") for entry in entries) != PHASES:
        raise ValueError("phase order disagrees with frozen ABI")
    if set(phases) != set(PHASES):
        raise ValueError("missing or extra compiler phase artifacts")

    reports = []
    readback = []
    cursor = 0
    for entry in entries:
        name = entry["name"]
        artifact = phases[name]
        semantic = artifact["semantic"]
        rtl = artifact["rtl"]
        if len(semantic) != 37:
            raise ValueError(f"{name}: expected 37 semantic memories")
        validate_abi(semantic, rtl)
        receipt = artifact["namespace_receipt"]
        if receipt.get("input_sha256") != artifact["sv_sha256"]:
            raise ValueError(f"{name}: namespaced source hash is stale")
        top = receipt.get("modules", {}).get("main_1")
        if not isinstance(top, str) or not top.endswith("__main_1"):
            raise ValueError(f"{name}: namespaced main_1 is missing")
        if "namespaced_sv_sha256" in artifact and receipt.get("output_sha256") != artifact["namespaced_sv_sha256"]:
            raise ValueError(f"{name}: namespaced output source hash is stale")
        for key, image in artifact["initial_memories"].items():
            port_number = int(key)
            if port_number < 0 or port_number >= len(rtl):
                raise ValueError(f"{name}: initial memory {key} is outside the RTL ABI")
            port = rtl[port_number]
            words = image["words"]
            if image["width"] != port.width or len(words) > port.depth:
                raise ValueError(f"{name}: initial memory {key} width/depth mismatch")
            byte_width = max(1, port.width // 8)
            payload = b"".join(int(word, 16).to_bytes(byte_width, "little") for word in words)
            if _digest(payload) != image["sha256"]:
                raise ValueError(f"{name}: initial memory {key} hash mismatch")
        token_port = artifact["token_input_port"]
        expected_token_port = 31 if name == "prefill-8" else 27
        token_shape = (1, 8) if name == "prefill-8" else (1, 1)
        if token_port != expected_token_port or semantic[token_port].shape != token_shape or semantic[token_port].width != 64:
            raise ValueError(f"{name}: token input shape or width is wrong")
        logits = semantic[32]
        expected_logits_shape = (1, 8, 6) if name == "prefill-8" else (1, 1, 6)
        if logits.shape != expected_logits_shape or logits.width != 32:
            raise ValueError(f"{name}: logits shape or width is wrong")
        vocab = logits.shape[-1]
        if entry["logits"]["word_count"] != vocab or entry["logits"]["shape"] != [vocab]:
            raise ValueError(f"{name}: readback logits width is wrong")
        if entry["token_address"] != cursor or entry["logits"]["start_address"] != cursor + 1:
            raise ValueError(f"{name}: token/logit readback addresses are not contiguous")
        logits_offset = (_count(logits.shape) // vocab - 1) * vocab
        cache_reports = []
        next_address = cursor + 1 + vocab
        leaves = entry["cache_leaves"]
        if len(leaves) != 4:
            raise ValueError(f"{name}: expected four cache leaves")
        for leaf_number, leaf in enumerate(leaves):
            if leaf.get("leaf") != leaf_number:
                raise ValueError(f"{name}: cache leaf order disagrees with ABI")
            memory = semantic[33 + leaf_number]
            if memory.width != 32 or list(memory.shape) != leaf["shape"]:
                raise ValueError(f"{name}: cache leaf {leaf_number} shape or width is wrong")
            words = _count(memory.shape)
            if leaf["word_count"] != words or leaf["start_address"] != next_address:
                raise ValueError(f"{name}: cache leaf {leaf_number} readback depth/address is wrong")
            cache_reports.append({"leaf": leaf_number, "port": 33 + leaf_number,
                                  "width": memory.width, "words": words,
                                  "shape": list(memory.shape), "readback_address": next_address})
            next_address += words
        reports.append({
            "name": name,
            "top": top,
            "token_input_port": token_port,
            "token_input_words": _count(token_shape),
            "token_address": cursor,
            "logits": {"port": 32, "offset": logits_offset, "words": vocab},
            "cache_outputs": cache_reports,
            "rtl_memories": [{"port": item.number, "width": item.width, "depth": item.depth} for item in rtl],
            "initial_memories": artifact["initial_memories"],
            "hashes": {key: artifact[key] for key in ("sv_sha256", "flat_scf_sha256", "exported_sha256")},
            "namespaced_sv_sha256": receipt["output_sha256"],
        })
        readback.append({"phase": name, "start_address": cursor, "word_count": next_address - cursor})
        cursor = next_address
    if cursor != 237:
        raise ValueError(f"readback ABI has {cursor} words instead of 237")

    handoffs = []
    for source, destination in zip(reports, reports[1:]):
        src_name, dst_name = source["name"], destination["name"]
        src_semantic, dst_semantic = phases[src_name]["semantic"], phases[dst_name]["semantic"]
        cache = []
        for leaf in range(4):
            src = src_semantic[33 + leaf]
            dst = dst_semantic[28 + leaf]
            if src.width != dst.width:
                raise ValueError(f"{src_name}->{dst_name}: cache leaf {leaf} width mismatch")
            if src.shape != dst.shape:
                raise ValueError(f"{src_name}->{dst_name}: cache leaf {leaf} depth/shape mismatch")
            cache.append({"source_port": 33 + leaf, "destination_port": 28 + leaf,
                          "width": src.width, "words": _count(src.shape)})
        handoffs.append({"source": src_name, "destination": dst_name,
                         "token_source_port": 32, "token_destination_port": destination["token_input_port"],
                         "cache": cache})
    return {"schema": "llm2fpga.rc-phase-handoff-v1", "phase_order": list(PHASES),
            "phases": reports, "handoffs": handoffs, "readback": readback,
            "readback_words": cursor}


def load_phase_artifacts(phase: str, paths: dict[str, Path]) -> dict:
    """Parse authenticated compiler files and serialize initial memory images."""
    # Registration is needed for torch.export.load of PT2E quantized operators.
    import torch
    from torch.ao.quantization.quantize_pt2e import convert_pt2e  # noqa: F401

    flat_bytes = paths["flat_scf"].read_bytes()
    sv_bytes = paths["sv"].read_bytes()
    namespaced_bytes = paths["namespaced_sv"].read_bytes()
    exported_bytes = paths["exported"].read_bytes()
    receipt = json.loads(paths["namespace_receipt"].read_text())
    semantic = parse_flat_scf_abi(flat_bytes.decode())
    rtl = parse_sv_memory_ports(sv_bytes.decode())
    validate_abi(semantic, rtl)
    if receipt["input_sha256"] != _digest(sv_bytes) or receipt["output_sha256"] != _digest(namespaced_bytes):
        raise ValueError(f"{phase}: namespaced source hash is stale")
    exported = torch.export.load(paths["exported"])
    values = runtime_values(exported)
    if len(values) != 32:
        raise ValueError(f"{phase}: expected 32 runtime memories")
    runtime_port = 0
    user_input_ports = []
    for spec in exported.graph_signature.input_specs:
        if spec.kind.name == "PARAMETER":
            continue
        if spec.kind.name == "USER_INPUT":
            user_input_ports.append(runtime_port)
        runtime_port += 1
    if len(user_input_ports) != (1 if phase == "prefill-8" else 5):
        raise ValueError(f"{phase}: unexpected token/cache user-input count")
    token_port = user_input_ports[0]
    images = {}
    for port, value in enumerate(values):
        payload, dtype, shape = tensor_payload(value)
        expected = semantic[port]
        if shape != expected.shape and not (shape == () and expected.shape == (1,)):
            raise ValueError(f"{phase}: runtime memory {port} shape mismatch")
        images[str(port)] = {"width": expected.width, "words": memory_words(payload, width=expected.width),
                             "dtype": dtype, "sha256": _digest(payload)}
    globals_ = parse_flat_scf_global_bindings(flat_bytes.decode(), first_port=len(semantic))
    for binding in globals_:
        port = rtl[binding.port]
        if port.width != binding.width or port.depth < len(binding.words):
            raise ValueError(f"{phase}: global {binding.symbol} does not fit RTL memory")
        byte_width = binding.width // 8
        payload = b"".join(word.to_bytes(byte_width, "little") for word in binding.words)
        images[str(binding.port)] = {"width": binding.width,
                                     "words": [f"{word:0{byte_width * 2}x}" for word in binding.words],
                                     "symbol": binding.symbol, "sha256": _digest(payload)}
    return {"semantic": semantic, "rtl": rtl, "sv_sha256": _digest(sv_bytes),
            "namespaced_sv_sha256": _digest(namespaced_bytes), "namespace_receipt": receipt,
            "flat_scf_sha256": _digest(flat_bytes), "exported_sha256": _digest(exported_bytes),
            "initial_memories": images, "token_input_port": token_port}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abi", required=True, type=Path)
    parser.add_argument("--artifact-map", required=True, type=Path,
                        help="JSON mapping phase names to flat_scf, sv, namespaced_sv, exported and namespace_receipt paths")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    path_map = json.loads(args.artifact_map.read_text())
    phases = {name: load_phase_artifacts(name, {key: Path(value) for key, value in path_map[name].items()})
              for name in PHASES}
    result = build_handoff(json.loads(args.abi.read_text()), phases)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
