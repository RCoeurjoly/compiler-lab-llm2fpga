#!/usr/bin/env python3
"""Run a 16-token TinyStories continuation on an already programmed YPCB."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline.infer_tinystories_generation_jtag import infer_generation


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "artifacts/reference/tinystories-1m-exact-input-contract.json"
VOCAB_SIZE = 50257
DEFAULT_TOKENIZER_DIR = ROOT / "artifacts/runtime/tinystories-1m-full16/tokenizer"
DEFAULT_TRANSPORT_DIR = ROOT / "third_party/llm2fpga-jtag"
DEFAULT_IMAGE = ROOT / "artifacts/runtime/tinystories-1m-full16/bitstream/model.bit"
ACCEPTED_IMAGE_SHA256 = "bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f"
TRANSPORT_SHA256 = {
    "read_jtag_debug_ftdi_bitbang.py": "dec0f56290324fa3f178a5d86b6afca3432e68f043f1ec1c9f0b51aaf244184c",
    "read_jtag_debug_xvc.py": "14b9a6737f05741399969e24b841859de025197ffde2b6f559a4f6e7c9746b40",
}


def verify_bundled_runtime() -> None:
    """Fail closed if the committed board inputs differ from accepted bytes."""
    expected_tokenizer = json.loads(CONTRACT.read_text(encoding="utf-8"))["tokenizer"]["sha256"]
    inputs = {
        DEFAULT_TOKENIZER_DIR / "tokenizer.json": expected_tokenizer,
        DEFAULT_IMAGE: ACCEPTED_IMAGE_SHA256,
        **{DEFAULT_TRANSPORT_DIR / name: digest for name, digest in TRANSPORT_SHA256.items()},
    }
    for path, expected in inputs.items():
        actual = _sha256_file(path)
        if actual != expected:
            raise ValueError(f"bundled input SHA-256 mismatch: {path} (expected {expected}, got {actual})")


def _run_dir() -> Path:
    return ROOT / ".local/tinystories-short-prompt"


@contextmanager
def board_lock(serial: str):
    """Serialize CLI use across worktrees of the same user without /tmp."""
    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    lock_path = cache / "llm2fpga" / f"ypcb-hs3-{serial}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"board is in use (lock: {lock_path})") from error
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def program_board(image: Path, serial: str, log_path: Path) -> dict[str, object]:
    log_path = log_path.resolve()
    actual = _sha256_file(image)
    if actual != ACCEPTED_IMAGE_SHA256:
        raise ValueError(f"accepted bitstream SHA-256 mismatch: expected {ACCEPTED_IMAGE_SHA256}, got {actual}")
    programmer = shutil.which("openFPGALoader")
    if programmer is None:
        raise RuntimeError("openFPGALoader is unavailable; use the pinned Nix development shell")
    command = [programmer, "-c", "digilent_hs3", "--ftdi-serial", serial,
               "--freq", "1000000", "-m", str(image)]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=360, check=False)
    receipt = {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "image_sha256": actual,
        "serial": serial,
        "returncode": completed.returncode,
        "log_path": str(log_path),
        "log_sha256": _sha256_file(log_path),
        "elapsed_seconds": time.monotonic() - started,
    }
    if completed.returncode != 0:
        raise RuntimeError(f"FPGA programming failed (exit {completed.returncode}); log: {log_path}")
    return receipt


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
               timeout: float, receipt_path: Path | None = None, *,
               program: bool = False) -> dict[str, object]:
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
        if tokenizer_dir == DEFAULT_TOKENIZER_DIR and transport_dir == DEFAULT_TRANSPORT_DIR:
            verify_bundled_runtime()
        tokenizer = load_tokenizer(tokenizer_dir)
        receipt["tokenizer_sha256"] = _sha256_file(tokenizer_dir / "tokenizer.json")
        prompt_ids = encode_prompt(text, tokenizer)
        receipt["prompt_ids"] = prompt_ids
        if program:
            log_path = (receipt_path.with_suffix(".program.log") if receipt_path else
                        _run_dir() / f"program-{int(time.time())}-{os.getpid()}.log")
            receipt["programming"] = program_board(DEFAULT_IMAGE, serial, log_path)
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
    parser.add_argument("--tokenizer-dir", type=Path, default=DEFAULT_TOKENIZER_DIR)
    parser.add_argument("--transport-dir", type=Path, default=DEFAULT_TRANSPORT_DIR)
    parser.add_argument("--program", action="store_true", help="load the accepted full16 SRAM image before inference")
    parser.add_argument("--serial", default="210299BF3824")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        with board_lock(args.serial):
            result = run_prompt(args.prompt, args.tokenizer_dir, args.transport_dir,
                                args.serial, args.timeout, args.receipt,
                                program=args.program)
    except (OSError, RuntimeError) as error:
        print(f"short-prompt inference failed: {error}", file=sys.stderr)
        return 1
    if result["status"] == "passed":
        print("Prompt IDs:", " ".join(str(token) for token in result["prompt_ids"]))
        print("Continuation:")
        sys.stdout.write(str(result["continuation_text"]) + "\n")
        return 0
    print(f"short-prompt inference failed: {result['error']}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
