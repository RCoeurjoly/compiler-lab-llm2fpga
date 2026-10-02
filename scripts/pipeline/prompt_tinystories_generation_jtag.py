#!/usr/bin/env python3
"""Run a 16-token TinyStories continuation on an already programmed YPCB."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline.infer_tinystories_generation_jtag import infer_generation


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
VOCAB_SIZE = 50257


def load_tokenizer(tokenizer_dir: Path):
    tokenizer_file = tokenizer_dir / "tokenizer.json"
    actual = hashlib.sha256(tokenizer_file.read_bytes()).hexdigest()
    expected = json.loads(CONTRACT.read_text(encoding="utf-8"))["tokenizer"]["sha256"]
    if actual != expected:
        raise ValueError(f"tokenizer SHA-256 mismatch: expected {expected}, got {actual}")
    from transformers import PreTrainedTokenizerFast

    return PreTrainedTokenizerFast(tokenizer_file=str(tokenizer_file))


def encode_prompt(text: str, tokenizer) -> list[int]:
    ids = tokenizer.encode(text, add_special_tokens=False)
    if len(ids) != 4 or any(type(token) is not int or not 0 <= token < VOCAB_SIZE for token in ids):
        raise ValueError(f"prompt must encode to exactly four IDs in [0, {VOCAB_SIZE}); got {len(ids)}")
    return ids


def open_transport(transport_dir: Path, serial: str):
    sys.path.insert(0, str(transport_dir.resolve()))
    ftdi = importlib.import_module("read_jtag_debug_ftdi_bitbang")
    jtag = importlib.import_module("read_jtag_debug_xvc")
    client = ftdi.FtdiMpsseJtag(serial=serial, vid=0x0403, pid=0x6014,
                                freq_hz=1_000_000, tdo_bit=7)
    return client, jtag


def _sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _write_receipt(receipt: dict[str, object], path: Path | None) -> None:
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def run_prompt(text: str, tokenizer_dir: Path, transport_dir: Path, serial: str,
               timeout: float, receipt_path: Path | None = None) -> dict[str, object]:
    """Execute one fresh prompt; `passed` means transport completion only."""
    receipt: dict[str, object] = {
        "schema": "tinystories-short-prompt-jtag-v1",
        "status": "failed",
        "prompt_text": text,
        "prompt_ids": [],
        "tokens": [],
        "transactions": [],
        "token_check": "none",
        "inference_started": False,
        "transport_serial": serial,
        "tokenizer_sha256": None,
        "checker_sha256": {
            "prompt_cli": _sha256_file(Path(__file__)),
            "generation_jtag": _sha256_file(ROOT / "scripts/pipeline/infer_tinystories_generation_jtag.py"),
        },
    }
    client = None
    try:
        if not 0 < timeout <= 300:
            raise ValueError("timeout must be in (0, 300]")
        tokenizer = load_tokenizer(tokenizer_dir)
        receipt["tokenizer_sha256"] = _sha256_file(tokenizer_dir / "tokenizer.json")
        prompt_ids = encode_prompt(text, tokenizer)
        receipt["prompt_ids"] = prompt_ids
        client, jtag = open_transport(transport_dir, serial)
        receipt["transport_sha256"] = {
            name: _sha256_file(transport_dir / name)
            for name in ("read_jtag_debug_ftdi_bitbang.py", "read_jtag_debug_xvc.py")
        }
        run = infer_generation(
            client, clock_tms=jtag.clock_tms, reset_tap=jtag.reset_tap,
            shift_ir=jtag.shift_ir, prompt=prompt_ids, expected_tokens=None,
            generation_steps=16, timeout=timeout,
        )
        receipt["jtag_schema"] = run["schema"]
        receipt.update({key: value for key, value in run.items() if key != "schema"})
        if run["status"] != "passed":
            raise RuntimeError(str(run["error"]))
        tokens = run["tokens"]
        if len(tokens) != 16:
            raise RuntimeError(f"expected 16 generated IDs, got {len(tokens)}")
        for token in tokens:
            if type(token) is not int or not 0 <= token < VOCAB_SIZE:
                raise ValueError(f"generated token ID {token} outside [0, {VOCAB_SIZE})")
        receipt["continuation_text"] = tokenizer.decode(
            tokens, clean_up_tokenization_spaces=False, skip_special_tokens=False
        )
        receipt["status"] = "passed"
    except Exception as error:
        receipt["status"] = "failed"
        receipt["error"] = str(error)
    finally:
        if client is not None:
            client.close()
        _write_receipt(receipt, receipt_path)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="text encoding to exactly four token IDs")
    parser.add_argument("--tokenizer-dir", type=Path, required=True)
    parser.add_argument("--transport-dir", type=Path, required=True)
    parser.add_argument("--serial", default="210299BF3824")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    result = run_prompt(args.prompt, args.tokenizer_dir, args.transport_dir,
                        args.serial, args.timeout, args.receipt)
    if result["status"] == "passed":
        print("Prompt IDs:", " ".join(str(token) for token in result["prompt_ids"]))
        print("Continuation:")
        sys.stdout.write(str(result["continuation_text"]) + "\n")
        return 0
    print(f"short-prompt inference failed: {result['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
