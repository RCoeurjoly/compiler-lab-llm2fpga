#!/usr/bin/env python3
"""Independent structural verifier for Task 4 composition receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

STAGE_ORDER = ("export", "legalize", "calyx", "sv", "synthesis")
MAX_STAGE_TIMEOUT_SECONDS = 1800


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _resolve(root: Path, rendered: str) -> Path:
    path = Path(rendered)
    return path if path.is_absolute() else root / path


def _verify_binding(value: object, root: Path, label: str) -> Path:
    if not isinstance(value, dict):
        raise ValueError(f"{label} binding missing")
    path = _resolve(root, str(value.get("path", "")))
    if not path.is_file() or path.stat().st_size != value.get("bytes"):
        raise ValueError(f"{label} binding missing or size mismatch")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != value.get("sha256"):
        raise ValueError(f"{label} binding hash mismatch")
    return path


def verify_receipt(value: dict, root: Path) -> None:
    if value.get("schema") != "llm2fpga-exact-serial-gemv-frontier-v1":
        raise ValueError("unexpected frontier receipt schema")
    actual = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if value.get("receipt_sha256") != canonical_sha256(actual):
        raise ValueError("frontier receipt self-hash mismatch")
    if tuple(value.get("stage_order", ())) != STAGE_ORDER:
        raise ValueError("frontier receipt stage ordering mismatch")
    sources = value.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("frontier receipt source bindings missing")
    for label, item in sources.items():
        if item:
            _verify_binding(item, root, f"source {label}")
    predecessors = value.get("predecessors")
    if predecessors is not None:
        if not isinstance(predecessors, dict):
            raise ValueError("predecessor bridge missing")
        expected = {
            "task3": ("d20351e9298989a67d1956838e062c8bfa8862dd", "dd5626f90c0920736731dc58c3a8c24a2ba6c2e7"),
        }
        for role, (commit, tree) in expected.items():
            item = predecessors.get(role)
            if not isinstance(item, dict) or item.get("commit") != commit or item.get("tree") != tree:
                raise ValueError(f"{role} predecessor commit/tree mismatch")
            files = item.get("source_files")
            if not isinstance(files, dict) or not files:
                raise ValueError(f"{role} predecessor source bindings missing")
            for label, bound in files.items():
                # Historical snapshots live outside the current source root.
                _verify_binding(bound, Path("/"), f"{role} predecessor {label}")
    stages = value.get("stages")
    result = value.get("result")
    if not isinstance(stages, dict) or not isinstance(result, dict):
        raise ValueError("frontier receipt stages/result missing")
    first_empty = False
    for name in STAGE_ORDER:
        stage = stages.get(name)
        if not stage:
            first_empty = True
            continue
        if first_empty:
            raise ValueError("later stage populated after a skipped stage")
        if stage.get("timeout_seconds", MAX_STAGE_TIMEOUT_SECONDS + 1) > MAX_STAGE_TIMEOUT_SECONDS:
            raise ValueError("stage timeout exceeds 1800 seconds")
        command = stage.get("command")
        if not isinstance(command, list) or stage.get("command_sha256") != canonical_sha256(command):
            raise ValueError("stage command binding mismatch")
        if not isinstance(stage.get("elapsed_seconds"), (int, float)) or stage["elapsed_seconds"] < 0:
            raise ValueError("stage elapsed time missing")
        if stage.get("status") == "success" and "artifact" in stage:
            _verify_binding(stage["artifact"], root, f"stage {name}")
        if stage.get("status") == "failure":
            for later in STAGE_ORDER[STAGE_ORDER.index(name) + 1:]:
                if stages.get(later) != {}:
                    raise ValueError("later stages must be empty after failure")
            if result != {"status": "failure", "stage": name, "frontier": f"{name}_frontier"}:
                raise ValueError("failure result does not name first failed stage")
            return
        if stage.get("status") != "success":
            raise ValueError("invalid stage status")
    if result.get("status") != "success":
        raise ValueError("all successful stages require a success result")
    sv = stages["sv"].get("artifact")
    sv_path = _verify_binding(sv, root, "SV")
    closure = value.get("compiler_closure")
    if not isinstance(closure, list):
        raise ValueError("compiler closure missing")
    closure_paths = {_verify_binding(item, root, "compiler closure") for item in closure}
    if sv_path not in closure_paths:
        raise ValueError("SV source is outside compiler closure")
    if not sv_path.read_text(encoding="utf-8").strip():
        raise ValueError("SV source is empty")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.receipt.read_text(encoding="utf-8"))
    verify_receipt(value, args.root.resolve())
    print(json.dumps({"status": "verified", "receipt": str(args.receipt)}, sort_keys=True))


if __name__ == "__main__":
    main()
