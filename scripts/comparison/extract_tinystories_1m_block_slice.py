#!/usr/bin/env python3
"""Fail-closed extraction of a TinyStories-1M transformer-block RTL slice.

This utility deliberately does not infer a full-model artifact from historical
resource reports or from Representative Core outputs.  A caller must supply
the compiler artifact and a sidecar metadata JSON explicitly.  The sidecar
binds the artifact to the frozen reference contract before any source is
copied into an extracted comparison slice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "artifacts/reference/tinystories-1m-kev-gpt-contract.json"
SLICE_KIND = "one_transformer_block_token_step"
SCHEMA = "tinystories-1m-compiler-slice-manifest-v1"
MODULE_RE = re.compile(r"(?ms)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b(.*?)\bendmodule\b")
INSTANCE_RE = re.compile(
    r"(?m)(?:^|;)\s*([A-Za-z_][A-Za-z0-9_$]*)\s*(?:#\s*\([^;]*?\))?\s+"
    r"[A-Za-z_][A-Za-z0-9_$]*\s*\("
)
ANCHOR_RE = re.compile(r"(?:transformer.*block|block.*transformer).*(?:token|step)|(?:token|step).*(?:transformer.*block|block.*transformer)", re.I)
ANNOTATION = "llm2fpga.slice_kind=one_transformer_block_token_step"
VERILOG_KEYWORDS = {"module", "if", "for", "while", "case", "assign", "always", "always_ff", "always_comb", "generate", "function", "task"}


class ExtractionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtractionError("invalid_input", f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ExtractionError("invalid_input", f"JSON object required: {path}")
    return value


def required_identity(contract: dict[str, Any]) -> dict[str, Any]:
    model = contract.get("model")
    package = contract.get("package")
    if not isinstance(model, dict) or not isinstance(package, dict):
        raise ExtractionError("invalid_contract", "contract lacks model/package identity")
    keys = ("name", "source_model_id", "source_revision")
    if any(not isinstance(model.get(key), str) for key in keys):
        raise ExtractionError("invalid_contract", "contract model identity is malformed")
    if not isinstance(package.get("sha256"), str) or not isinstance(package.get("manifest_sha256"), str):
        raise ExtractionError("invalid_contract", "contract package identity is malformed")
    return {
        "model": {key: model[key] for key in keys},
        "package": {key: package[key] for key in ("sha256", "manifest_sha256")},
    }


def validate_identity(metadata: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    expected = required_identity(contract)
    actual = metadata.get("contract_identity")
    if actual != expected:
        raise ExtractionError(
            "contract_mismatch",
            "artifact metadata contract_identity does not exactly match the frozen TinyStories-1M contract",
        )
    return expected


def parse_modules(inputs: list[Path]) -> dict[str, tuple[Path, str, set[str]]]:
    modules: dict[str, tuple[Path, str, set[str]]] = {}
    for source in inputs:
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ExtractionError("invalid_input", f"source is not UTF-8 text: {source}") from error
        for match in MODULE_RE.finditer(text):
            name, body = match.group(1), match.group(0)
            if name in modules:
                raise ExtractionError("ambiguous_module", f"module {name!r} is declared more than once")
            dependencies = {
                candidate
                for candidate in INSTANCE_RE.findall(body)
                if candidate not in VERILOG_KEYWORDS
            }
            modules[name] = (source, body, dependencies)
    if not modules:
        raise ExtractionError("boundary_not_found", "no Verilog/SystemVerilog modules found in explicit inputs")
    return modules


def select_anchor(modules: dict[str, tuple[Path, str, set[str]]]) -> str:
    matches = [
        name for name, (_, body, _) in modules.items()
        if ANCHOR_RE.search(name) or ANNOTATION in body
    ]
    if len(matches) != 1:
        detail = "none" if not matches else ", ".join(sorted(matches))
        raise ExtractionError("boundary_not_found", f"expected exactly one block/token-step anchor, found {detail}")
    return matches[0]


def dependency_closure(anchor: str, modules: dict[str, tuple[Path, str, set[str]]]) -> list[str]:
    closure: set[str] = set()
    todo = [anchor]
    while todo:
        name = todo.pop()
        if name in closure:
            continue
        closure.add(name)
        unresolved = modules[name][2] - set(modules)
        if unresolved:
            raise ExtractionError(
                "unbounded_dependency_closure",
                f"{name} instantiates modules not supplied as explicit inputs: {', '.join(sorted(unresolved))}",
            )
        todo.extend(sorted(modules[name][2] - closure))
    return sorted(closure)


def unavailable_manifest(contract_path: Path, contract: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "source_artifact_unavailable",
        "model": contract["model"]["name"],
        "contract": {"path": str(contract_path), "sha256": sha256(contract_path)},
        "slice": {"kind": SLICE_KIND, "dependency_closure": [], "status": "unavailable"},
        "failure": {"code": "source_artifact_unavailable", "reason": reason},
    }


def extract(inputs: list[Path], metadata_path: Path, contract_path: Path, slice_dir: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    metadata = load_json(metadata_path)
    identity = validate_identity(metadata, contract)
    if not inputs:
        raise ExtractionError("source_artifact_unavailable", "at least one explicit compiler source/IR input is required")
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise ExtractionError("source_artifact_unavailable", f"compiler source artifact is absent: {', '.join(missing)}")
    modules = parse_modules(inputs)
    anchor = select_anchor(modules)
    closure = dependency_closure(anchor, modules)
    slice_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []
    # Inputs may carry unrelated modules (for example, a full generated SV
    # bundle).  Write each selected module independently so the materialized
    # comparison artifact is exactly the reachable dependency closure.
    for index, name in enumerate(closure):
        source, body, _ = modules[name]
        destination = slice_dir / f"{index:03d}-{name}.sv"
        extracted = body.rstrip() + "\n"
        destination.write_text(extracted, encoding="utf-8")
        copied.append({
            "module": name,
            "source": str(source),
            "source_sha256": sha256(source),
            "extracted": str(destination),
            "sha256": hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
        })
    return {
        "schema": SCHEMA,
        "status": "ready",
        "model": contract["model"]["name"],
        "contract": {"path": str(contract_path), "sha256": sha256(contract_path), "identity": identity},
        "source_metadata": {"path": str(metadata_path), "sha256": sha256(metadata_path)},
        "slice": {
            "kind": SLICE_KIND,
            "anchor_module": anchor,
            "dependency_closure": closure,
            "artifacts": copied,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", default=[], type=Path, help="explicit SV/Verilog source input (repeatable)")
    parser.add_argument("--metadata", type=Path, help="JSON sidecar containing exact contract_identity")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--slice-dir", type=Path, help="directory for copied source closure")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    contract = load_json(args.contract)
    try:
        if args.metadata is None or args.slice_dir is None:
            raise ExtractionError("source_artifact_unavailable", "--metadata and --slice-dir are required for extraction")
        manifest = extract(args.input, args.metadata, args.contract, args.slice_dir)
        exit_code = 0
    except ExtractionError as error:
        manifest = unavailable_manifest(args.contract, contract, str(error))
        manifest["status"] = error.code
        manifest["failure"]["code"] = error.code
        exit_code = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
