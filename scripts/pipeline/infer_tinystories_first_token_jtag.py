#!/usr/bin/env python3
"""Check one inference on an already programmed one-step compiler image.

This does not program the FPGA or establish independent reconfiguration.
Use only with the non-overlapping prompt ABI and a one-step compiler image.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

STATUS = 0x3000000000000000


def infer(client, *, clock_tms, reset_tap, shift_ir, prompt, expected_token,
          timeout=300, delay=time.sleep, monotonic=time.monotonic):
    result = {"schema": "tinystories-first-token-jtag-v1", "status": "failed",
              "transactions": [], "inference_started": False,
              "independent_reconfiguration_verified": False}
    begun = monotonic()

    def exchange(command):
        clock_tms(client, [1, 0, 0])
        bits = client.shift([0] * 63 + [1], [(command >> i) & 1 for i in range(64)])
        clock_tms(client, [1, 0])
        if len(bits) != 64:
            raise RuntimeError(f"short JTAG response: {len(bits)} bits")
        value = sum((bit & 1) << i for i, bit in enumerate(bits))
        result["transactions"].append({"command": f"{command:016x}", "captured": f"{value:016x}"})
        delay(0.01)
        return value

    def read(command):
        exchange(command)
        return exchange(STATUS)

    def expect(command, expected):
        actual = read(command)
        if actual != expected:
            raise RuntimeError(f"command {command:016x}: expected {expected:016x}, got {actual:016x}")

    try:
        if len(prompt) != 4 or any(type(x) is not int or not 0 <= x <= 65535 for x in prompt):
            raise ValueError("four unsigned 16-bit prompt words required")
        if not 0 < timeout <= 300:
            raise ValueError("timeout must be in (0, 300]")
        reset_tap(client)
        shift_ir(client, 2, 6)
        delay(0.01)
        expect(0x5000000000000000, 0)
        expect(STATUS, 0x2800000000000000)
        for index, word in enumerate(prompt):
            expect(0x1000000000000000 | (index << 16) | word, word)
        for index, word in enumerate(prompt):
            expect(0x6000000000000000 | (index << 16), word)
        expect(STATUS, 0x2800000000000000 | prompt[0])
        begun = monotonic()
        result["inference_started"] = True
        exchange(0x2000000000000000)
        while monotonic() - begun < timeout:
            status = read(STATUS)
            result["last_status"] = f"{status:016x}"
            if status == (0x2c00000000000000 | prompt[0]):
                break
            if status != (0x2a00000000000000 | prompt[0]):
                raise RuntimeError(f"unexpected inference status {status:016x}")
            delay(0.01)
        else:
            raise RuntimeError("inference timeout")
        token = read(0x4000000000000000)
        result["token"] = token
        if token != expected_token:
            raise RuntimeError(f"token mismatch: expected {expected_token}, got {token}")
        if monotonic() - begun > timeout:
            raise RuntimeError("inference timeout during token readback")
        result["status"] = "passed"
    except Exception as error:
        result["error"] = str(error)
    result["elapsed_seconds"] = monotonic() - begun
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport-dir", type=Path, required=True)
    parser.add_argument("--serial", default="210299BF3824")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from TinyStories.capture_fixed_point_model_token_step_oracle import verify_oracle_fixture
    oracle = json.loads((root / "artifacts/reference/tinystories-1m-fixed-point-model-token-step-oracle.json").read_text())
    verify_oracle_fixture(oracle)
    sys.path.insert(0, str(args.transport_dir.resolve()))
    ftdi = importlib.import_module("read_jtag_debug_ftdi_bitbang")
    jtag = importlib.import_module("read_jtag_debug_xvc")
    client = None
    result = {"schema": "tinystories-first-token-jtag-v1", "status": "failed"}
    try:
        client = ftdi.FtdiMpsseJtag(serial=args.serial, vid=0x0403, pid=0x6014,
                                   freq_hz=1_000_000, tdo_bit=7)
        result = infer(client, clock_tms=jtag.clock_tms, reset_tap=jtag.reset_tap,
                       shift_ir=jtag.shift_ir, prompt=oracle["token_contract"]["initial_context"],
                       expected_token=oracle["steps"][0]["selected_token"]["value"], timeout=args.timeout)
    except Exception as error:
        result["error"] = str(error)
    finally:
        if client is not None:
            client.close()
    result["oracle_sha256"] = oracle["artifact_sha256"]
    result["transport_serial"] = args.serial
    result["transport_sha256"] = {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (ftdi, jtag)}
    result["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["receipt_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "transactions"}, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
