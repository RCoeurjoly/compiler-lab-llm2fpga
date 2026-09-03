#!/usr/bin/env python3
"""Bounded, fail-closed composition runner for exact serial-GEMV lowering.

This deliberately records the *first* unavailable handoff.  A descriptor SV
is not silently promoted to a full TinyStories SV artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


STAGE_ORDER = ("export", "legalize", "calyx", "sv", "synthesis")
MAX_STAGE_TIMEOUT_SECONDS = 1800
TASK2_COMMIT = "bac0e5abb52fe2d235a0bcf80508ca2111101058"
TASK2_TREE = "d7ec887194b9bee8f0aa59f55f8422c6ab4d66f4"
TASK3_COMMIT = "d20351e9298989a67d1956838e062c8bfa8862dd"
TASK3_TREE = "dd5626f90c0920736731dc58c3a8c24a2ba6c2e7"


class FrontierError(ValueError):
    """A bounded stage reached the first causal compiler frontier."""


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: Path, root: Path) -> dict[str, object]:
    path = path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise FrontierError(f"missing output: {path}")
    try:
        rendered = str(path.relative_to(root.resolve()))
    except ValueError:
        rendered = str(path)
    return {"path": rendered, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def load_module(root: Path, relative: str, name: str):
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FrontierError(f"unloadable compiler verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def predecessor_identity(*, role: str, root: Path, commit: str, tree: str) -> dict[str, object]:
    """Bind only the immutable source snapshot that a predecessor receipt used."""
    expected = {
        "task2": (TASK2_COMMIT, TASK2_TREE, (
            "nix/models.nix", "nix/pipeline.nix", "flake.nix",
            "scripts/compile-pytorch.py", "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py",
            "tools/torch-mlir-passes/LegalizeExactSerialGemv.cpp",
        )),
        "task3": (TASK3_COMMIT, TASK3_TREE, (
            "nix/pipeline.nix", "flake.nix",
            "scripts/pipeline/lower_exact_serial_gemv_to_calyx.py",
            "scripts/pipeline/verify_exact_serial_gemv_calyx_gate.py",
        )),
    }
    if role not in expected:
        raise FrontierError(f"unknown predecessor role: {role}")
    expected_commit, expected_tree, files = expected[role]
    if commit != expected_commit or tree != expected_tree:
        raise FrontierError(f"{role} predecessor commit/tree mismatch")
    root = root.resolve()
    return {
        "commit": commit,
        "tree": tree,
        # These are immutable predecessor snapshots, not paths relative to
        # the evolving Task 4 checkout.  Keep their absolute store bindings.
        "source_files": {relative: binding(root / relative, Path("/")) for relative in files},
    }


@dataclass(frozen=True)
class Stage:
    name: str
    artifact: Path | None
    action: Callable[[], None]
    command: tuple[str, ...] | None = None
    timeout_seconds: int = MAX_STAGE_TIMEOUT_SECONDS


def _stage_record(stage: Stage, root: Path) -> dict[str, object]:
    if stage.name not in STAGE_ORDER:
        raise FrontierError(f"unknown composition stage: {stage.name}")
    if stage.timeout_seconds <= 0 or stage.timeout_seconds > MAX_STAGE_TIMEOUT_SECONDS:
        raise FrontierError(f"invalid timeout for {stage.name}: {stage.timeout_seconds}")
    command = list(stage.command or ("internal", stage.name))
    before = time.monotonic()
    try:
        stage.action()
    except Exception as error:
        elapsed = time.monotonic() - before
        return {
            "status": "failure",
            "timeout_seconds": stage.timeout_seconds,
            "elapsed_seconds": elapsed,
            "command": command,
            "command_sha256": canonical_sha256(command),
            "diagnostic": str(error),
        }
    elapsed = time.monotonic() - before
    record: dict[str, object] = {
        "status": "success",
        "timeout_seconds": stage.timeout_seconds,
        "elapsed_seconds": elapsed,
        "command": command,
        "command_sha256": canonical_sha256(command),
    }
    if stage.artifact is not None:
        record["artifact"] = binding(stage.artifact, root)
    return record


def run_stages(*, root: Path, stages: Iterable[Stage], compiler_closure: Iterable[Path] = ()) -> dict:
    stages = tuple(stages)
    if tuple(stage.name for stage in stages) != STAGE_ORDER:
        raise FrontierError(f"composition stages must be exactly {STAGE_ORDER}")
    records: dict[str, dict] = {name: {} for name in STAGE_ORDER}
    result: dict[str, object] = {"status": "success", "stage": "synthesis"}
    for index, stage in enumerate(stages):
        record = _stage_record(stage, root)
        records[stage.name] = record
        if record["status"] != "success":
            result = {"status": "failure", "stage": stage.name, "frontier": f"{stage.name}_frontier"}
            for later in stages[index + 1:]:
                records[later.name] = {}
            break
    closure = [binding(path, root) for path in compiler_closure]
    payload = {
        "schema": "llm2fpga-exact-serial-gemv-frontier-v1",
        "stage_order": list(STAGE_ORDER),
        "sources": {
            "runner": binding(root / "scripts/pipeline/run_exact_serial_gemv_frontier.py", root)
            if (root / "scripts/pipeline/run_exact_serial_gemv_frontier.py").is_file() else {},
            "verifier": binding(root / "scripts/pipeline/verify_exact_serial_gemv_frontier.py", root)
            if (root / "scripts/pipeline/verify_exact_serial_gemv_frontier.py").is_file() else {},
        },
        "stages": records,
        "compiler_closure": closure,
        "result": result,
    }
    payload["receipt_sha256"] = canonical_sha256(payload)
    return payload


def _verify_export(root: Path) -> None:
    module = load_module(root, "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py", "exact_frontier_export")
    module.verify_successor_authority(root)


def _verify_torch(root: Path, receipt: Path) -> None:
    module = load_module(root, "scripts/pipeline/verify_exact_serial_gemv_successor_torch.py", "exact_frontier_torch")
    value = json.loads(receipt.read_text(encoding="utf-8"))
    module.validate_artifact(value, root)


def _verify_portable_torch(root: Path, receipt: Path, exported_dir: Path, torch_output: Path) -> None:
    module = load_module(root, "scripts/pipeline/verify_exact_serial_gemv_portable_torch.py", "exact_frontier_portable_torch")
    module.verify(json.loads(receipt.read_text(encoding="utf-8")), root, exported_dir, torch_output)


def _verify_calyx_gate(receipt: Path) -> dict:
    value = json.loads(receipt.read_text(encoding="utf-8"))
    claimed = value.get("receipt_sha256")
    without = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if claimed != canonical_sha256(without):
        raise FrontierError("Calyx gate receipt self-hash mismatch")
    gates = value.get("gates")
    if not isinstance(gates, dict) or set(gates) != {"1x64x64", "1x256x64", "1x64x256", "4x50257x64"}:
        raise FrontierError("Calyx gate receipt is incomplete")
    for gate in gates.values():
        files = gate.get("files", {})
        for item in files.values():
            path = Path(str(item.get("path", "")))
            if not path.is_file() or path.stat().st_size != item.get("bytes") or sha256_file(path) != item.get("sha256"):
                raise FrontierError("Calyx gate output binding mismatch")
    return value


def run_composition(*, root: Path, export_receipt: Path, portable_torch_receipt: Path,
                    portable_exported_dir: Path, portable_torch_output: Path, calyx_receipt: Path,
                    task3_root: Path | None = None) -> dict:
    # Keep the prior receipts as stage artifacts.  Their own verifiers establish
    # their transitive authority; this runner establishes ordering and closure.
    task3_root = (task3_root or root).resolve()
    task3_identity = predecessor_identity(role="task3", root=task3_root,
        commit=TASK3_COMMIT, tree=TASK3_TREE)

    def calyx() -> None:
        gate = _verify_calyx_gate(calyx_receipt)
        torch = json.loads(portable_torch_receipt.read_text(encoding="utf-8"))
        count = torch.get("legalizer", {}).get("legalized_serial_gemv_operator_count")
        if count != 49:
            raise FrontierError("Torch receipt does not bind 49 legalized serial-GEMV boundaries")
        # Task 3 has only descriptor-shape gates.  No callsite-to-component map
        # exists, therefore there is no full-model Calyx program that could
        # honestly become an SV source at this point.
        raise FrontierError(
            f"full-model Calyx composition absent: Torch has {count} boundaries; "
            f"Calyx receipt has {len(gate['gates'])} descriptor gates"
        )

    receipt = run_stages(
        root=root,
        stages=(
            Stage("export", export_receipt, lambda: _verify_export(root), ("verify-successor-authority",)),
            Stage("legalize", portable_torch_receipt,
                lambda: _verify_portable_torch(root, portable_torch_receipt, portable_exported_dir, portable_torch_output),
                ("verify-portable-successor-torch", str(portable_torch_receipt))),
            Stage("calyx", calyx_receipt, calyx, ("verify-calyx-composition", str(calyx_receipt))),
            Stage("sv", None, lambda: None, ("emit-systemverilog",)),
            Stage("synthesis", None, lambda: None, ("yosys-stat",)),
        ),
    )
    receipt["predecessors"] = {"task3": task3_identity}
    receipt["sources"]["portable_torch_verifier"] = binding(
        root / "scripts/pipeline/verify_exact_serial_gemv_portable_torch.py", root)
    receipt["receipt_sha256"] = canonical_sha256({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--export-receipt", type=Path, required=True)
    parser.add_argument("--portable-torch-receipt", type=Path, required=True)
    parser.add_argument("--portable-exported-dir", type=Path, required=True)
    parser.add_argument("--portable-torch-output", type=Path, required=True)
    parser.add_argument("--calyx-receipt", type=Path, required=True)
    parser.add_argument("--task3-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_composition(
        root=args.root.resolve(), export_receipt=args.export_receipt,
        portable_torch_receipt=args.portable_torch_receipt,
        portable_exported_dir=args.portable_exported_dir, portable_torch_output=args.portable_torch_output,
        calyx_receipt=args.calyx_receipt, task3_root=args.task3_root,
    )
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["result"], sort_keys=True))


if __name__ == "__main__":
    main()
