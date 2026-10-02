#!/usr/bin/env python3
"""Compare a short-prompt board receipt with the authenticated fixed-point model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
GENERATION = ROOT / "artifacts/reference/tinystories-1m-exact-generation.json"
TASK4_RECEIPT = ROOT / "artifacts/task4/full16-board-2026-09-29/hardware/receipt.json"
ACCEPTED_IMAGE_SHA256 = json.loads(TASK4_RECEIPT.read_text())["candidate_sha256"]
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _self_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def compare_receipts(board: dict, reference: dict | None, programming: dict | None,
                     image: Path, program_log: Path, *,
                     accepted_image_sha256: str = ACCEPTED_IMAGE_SHA256) -> dict:
    """Accept a match only when its identities and raw programming evidence bind."""
    if reference is None:
        raise ValueError("software reference is required for equivalence")
    if programming is None:
        raise ValueError("programming evidence is required for equivalence")
    if board.get("schema") != "tinystories-short-prompt-jtag-v1" or board.get("status") != "passed":
        raise ValueError("board receipt is not a completed short-prompt run")
    if board.get("token_check") != "none":
        raise ValueError("board receipt must be raw unverified output")
    board_body = {key: value for key, value in board.items() if key != "receipt_sha256"}
    if board.get("receipt_sha256") != _self_hash(board_body):
        raise ValueError("board receipt self-hash mismatch")
    commands = [int(row["command"], 16) for row in board.get("transactions", [])]
    if commands.count(0x2000000000000000) != 1:
        raise ValueError("board receipt must contain exactly one START")
    prompt = board.get("prompt_ids")
    board_tokens = board.get("tokens")
    software_tokens = reference.get("tokens")
    if prompt != reference.get("prompt_ids") or not isinstance(prompt, list) or len(prompt) != 4:
        raise ValueError("prompt IDs differ from software reference")
    if not isinstance(board_tokens, list) or not isinstance(software_tokens, list) or len(board_tokens) != 16 or len(software_tokens) != 16:
        raise ValueError("exactly 16 board and software tokens are required")
    tokenizer_sha = json.loads(CONTRACT.read_text())["tokenizer"]["sha256"]
    if board.get("tokenizer_sha256") != tokenizer_sha or reference.get("tokenizer_sha256") != tokenizer_sha:
        raise ValueError("tokenizer identity mismatch")
    model_sha = reference.get("model_sha256")
    if not isinstance(model_sha, str) or not SHA256.fullmatch(model_sha):
        raise ValueError("software model identity is missing")
    actual_image_sha = _hash_file(image)
    if actual_image_sha != accepted_image_sha256 or programming.get("image_sha256") != actual_image_sha:
        raise ValueError("programmed image identity mismatch")
    if programming.get("returncode") != 0:
        raise ValueError("programming did not exit successfully")
    command = programming.get("command")
    if (not isinstance(command, list) or "-m" not in command
            or command.index("-m") + 1 >= len(command)
            or command[command.index("-m") + 1] != str(image)):
        raise ValueError("programming command does not name the accepted image")
    if programming.get("serial") != board.get("transport_serial"):
        raise ValueError("programming serial differs from board serial")
    actual_log_sha = _hash_file(program_log)
    if programming.get("log_sha256") != actual_log_sha or "Done" not in program_log.read_text(errors="replace"):
        raise ValueError("program log identity or completion mismatch")
    first_mismatch = next((index for index, (actual, expected) in enumerate(zip(board_tokens, software_tokens))
                           if actual != expected), None)
    result = {
        "schema": "tinystories-short-prompt-comparison-v1",
        "status": "passed" if first_mismatch is None else "mismatch",
        "prompt_ids": prompt,
        "board_tokens": board_tokens,
        "software_tokens": software_tokens,
        "first_mismatch": first_mismatch,
        "model_sha256": model_sha,
        "tokenizer_sha256": tokenizer_sha,
        "bitstream_sha256": actual_image_sha,
        "program_log_sha256": actual_log_sha,
        "board_receipt_sha256": board["receipt_sha256"],
    }
    result["sha256"] = _self_hash(result)
    return result


def generate_software_reference(prompt_ids: list[int], package: Path, model_path: Path,
                                contract: Path = CONTRACT, historical_generation: Path = GENERATION) -> dict:
    """Run 16 greedy steps with the authenticated exact fixed-point model."""
    import torch
    from TinyStories.model_adapter_exact_package import load_successor_exact_model

    bundle = load_successor_exact_model(contract, package, model_path, historical_generation)
    context = list(prompt_ids)
    tokens = []
    with torch.no_grad():
        for _ in range(16):
            logits = bundle.model(torch.tensor([context], dtype=torch.int64))[0, -1]
            token = int(torch.argmax(logits).item())
            tokens.append(token)
            context.append(token)
    identity = {
        "contract_sha256": _hash_file(contract),
        "package_manifest_sha256": _hash_file(package / "manifest.json"),
        "model_config_sha256": _hash_file(model_path / "config.json"),
        "historical_generation_sha256": _hash_file(historical_generation),
    }
    return {
        "prompt_ids": list(prompt_ids),
        "tokens": tokens,
        "tokenizer_sha256": json.loads(contract.read_text())["tokenizer"]["sha256"],
        "model_sha256": _self_hash(identity),
        "model_identity": identity,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--board-receipt", type=Path, required=True)
    parser.add_argument("--programming-receipt", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--program-log", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        board = json.loads(args.board_receipt.read_text())
        programming = json.loads(args.programming_receipt.read_text())
        reference = generate_software_reference(board["prompt_ids"], args.package, args.model_path)
        result = compare_receipts(board, reference, programming, args.image, args.program_log)
    except Exception as error:
        print(f"short-prompt comparison failed: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("board_tokens", "software_tokens")}, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
