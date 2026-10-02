#!/usr/bin/env python3
"""Generate the FPGA's 16-token continuation with the exact PyTorch model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pipeline.compare_tinystories_short_prompts import generate_software_reference
from scripts.pipeline.prompt_tinystories_generation_jtag import (
    CONTRACT, DEFAULT_TOKENIZER_DIR, encode_prompt, load_tokenizer,
)

TOKENIZER_SHA256 = json.loads(CONTRACT.read_text(encoding="utf-8"))["tokenizer"]["sha256"]


def _write_receipt(receipt: dict, path: Path | None) -> None:
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def run_prompt(text: str, package: Path, model_snapshot: Path,
               tokenizer_dir: Path = DEFAULT_TOKENIZER_DIR,
               receipt_path: Path | None = None) -> dict:
    """Run one greedy continuation with the authenticated fixed-point model."""
    result = {
        "schema": "tinystories-short-prompt-software-v1",
        "status": "failed",
        "prompt_text": text,
        "prompt_ids": [],
        "tokens": [],
        "token_check": "exact_software_model",
        "tokenizer_sha256": TOKENIZER_SHA256,
    }
    try:
        tokenizer = load_tokenizer(tokenizer_dir)
        prompt_ids = encode_prompt(text, tokenizer)
        result["prompt_ids"] = prompt_ids
        reference = generate_software_reference(prompt_ids, package, model_snapshot)
        tokens = reference["tokens"]
        if reference["prompt_ids"] != prompt_ids or len(tokens) != 16:
            raise RuntimeError("exact model returned an invalid 16-token reference")
        result.update({key: value for key, value in reference.items()
                       if key != "prompt_ids"})
        result["continuation_text"] = tokenizer.decode(
            tokens, clean_up_tokenization_spaces=False, skip_special_tokens=False
        )
        result["status"] = "passed"
    except Exception as error:
        result["status"] = "failed"
        result["error"] = str(error)
    finally:
        _write_receipt(result, receipt_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="text encoding to exactly four token IDs")
    parser.add_argument("--package", type=Path,
                        help="authenticated fixed-point package (default: pinned Nix shell package)")
    parser.add_argument("--model-snapshot", type=Path,
                        help="GPT-Neo config snapshot (default: pinned Nix shell snapshot)")
    parser.add_argument("--tokenizer-dir", type=Path, default=DEFAULT_TOKENIZER_DIR)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    package = args.package or os.environ.get("TINYSTORIES_1M_EXACT_PACKAGE")
    snapshot = args.model_snapshot or os.environ.get("TINYSTORIES_1M_SNAPSHOT")
    if not package or not snapshot:
        print("software prompt needs the pinned model package and snapshot; run inside `nix develop`",
              file=sys.stderr)
        return 1
    result = run_prompt(args.prompt, Path(package), Path(snapshot),
                        args.tokenizer_dir, args.receipt)
    if result["status"] != "passed":
        print(f"software prompt failed: {result['error']}", file=sys.stderr)
        return 1
    print("Prompt IDs:", " ".join(str(token) for token in result["prompt_ids"]))
    print("Generated IDs:", " ".join(str(token) for token in result["tokens"]))
    print("Continuation:")
    sys.stdout.write(str(result["continuation_text"]) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
