#!/usr/bin/env python3
"""Fail-closed extraction of a TinyStories-1M transformer-block RTL slice.

This utility deliberately does not infer a full-model artifact from historical
resource reports or from Representative Core outputs.  It first inventories
fixed repository/build-manifest locations (and explicitly supplied existing Nix
outputs); a caller may instead supply source paths directly.  A sidecar metadata
JSON binds any discovered source to the frozen reference contract before source
is copied into an extracted comparison slice.
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
KNOWN_REPOSITORY_ARTIFACTS = (
    "artifacts/tinystories-1m/compiler/main.sv",
    "artifacts/tinystories-1m/compiler/main.il",
    "artifacts/tinystories-1m/compiler/main.rtlil",
    "artifacts/tinystories-1m/compiler-build/main.sv",
)
KNOWN_MANIFESTS = (
    "artifacts/tinystories-1m/compiler-build-manifest.json",
    "artifacts/tinystories-1m/compiler/manifest.json",
)
KNOWN_NIX_OUTPUTS = (
    {
        "flake_attribute": "tiny-stories-1m-baseline-float-sv",
        "relative_artifacts": ("sv/main.sv", "main.sv"),
    },
    {
        "flake_attribute": "tiny-stories-1m-baseline-float-il",
        "relative_artifacts": ("main.il", "main.rtlil"),
    },
)
MODULE_RE = re.compile(r"(?ms)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b(.*?)\bendmodule\b")
RTLIL_CELL_RE = re.compile(r"(?m)^\s*cell\s+\\?([^\s]+)\s+\\?[^\s]+")
RTLIL_MODULE_START_RE = re.compile(r"^\s*module\s+\\?([^\s]+)(?:\s.*)?$")
RTLIL_NESTED_BLOCK_RE = re.compile(r"^\s*(?:cell|process|switch)\s+")
RTLIL_END_RE = re.compile(r"^\s*end\s*(?:#.*)?$")
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


def manifest_source_paths(manifest: Path) -> list[Path]:
    """Return explicit artifact paths declared by a known build manifest only."""
    try:
        value = load_json(manifest)
    except ExtractionError:
        return []
    found: list[Path] = []
    for key in ("sv", "rtl", "rtlil", "artifact", "artifact_path", "source_path"):
        candidate = value.get(key)
        if isinstance(candidate, str):
            path = Path(candidate)
            if not path.is_absolute():
                path = manifest.parent / path
            if path.is_file():
                found.append(path)
    return found


def discover_sources(repo_root: Path, nix_outputs: list[Path] | None = None) -> tuple[list[Path], dict[str, Any]]:
    """Inspect fixed repository, build-manifest, and existing Nix-output paths.

    It never invokes Nix or builds an output.  Nix outputs are inspected only
    when their concrete paths are supplied through ``--nix-output``.
    """
    searched = [str(repo_root / relative) for relative in KNOWN_REPOSITORY_ARTIFACTS]
    found = [repo_root / relative for relative in KNOWN_REPOSITORY_ARTIFACTS if (repo_root / relative).is_file()]
    manifests = [repo_root / relative for relative in KNOWN_MANIFESTS]
    for manifest in manifests:
        found.extend(manifest_source_paths(manifest) if manifest.is_file() else [])
    supplied_nix_outputs = [] if nix_outputs is None else list(nix_outputs)
    for output in supplied_nix_outputs:
        if output.is_file():
            searched.append(str(output))
            if output.suffix.lower() in {".sv", ".v", ".il", ".rtlil"}:
                found.append(output)
            continue
        for entry in KNOWN_NIX_OUTPUTS:
            for relative in entry["relative_artifacts"]:
                candidate = output / relative
                searched.append(str(candidate))
                if candidate.is_file():
                    found.append(candidate)
    unique = sorted({path.resolve() for path in found}, key=str)
    return unique, {
        "repository_root": str(repo_root),
        "repository_candidates": searched[:len(KNOWN_REPOSITORY_ARTIFACTS)],
        "manifest_paths": [str(path) for path in manifests],
        "nix_output_policy": [
            {"flake_attribute": entry["flake_attribute"], "relative_artifacts": list(entry["relative_artifacts"])}
            for entry in KNOWN_NIX_OUTPUTS
        ],
        "supplied_nix_outputs": [str(path) for path in supplied_nix_outputs],
        "searched_paths": searched,
        "found_paths": [str(path) for path in unique],
    }


def immediately_preceding_annotation(text: str, module_start: int) -> bool:
    """Recognize the slice annotation only in comments adjoining a module."""
    prefix = text[:module_start]
    trailing = re.search(r"(?s)(?:(?:\s+)|(?://[^\n]*(?:\n|$))|(?:#[^\n]*(?:\n|$))|(?:/\*.*?\*/))*$", prefix)
    return trailing is not None and ANNOTATION in trailing.group(0)


def parse_sv_modules(text: str) -> list[tuple[str, str, set[str], int]]:
    parsed: list[tuple[str, str, set[str], int]] = []
    for match in MODULE_RE.finditer(text):
        name, body = match.group(1), match.group(0)
        dependencies = {
            candidate for candidate in INSTANCE_RE.findall(body)
            if candidate not in VERILOG_KEYWORDS
        }
        parsed.append((name, body, dependencies, match.start()))
    return parsed


def parse_rtlil_modules(text: str) -> list[tuple[str, str, set[str], int]]:
    """Parse complete RTLIL modules without confusing nested ``end`` tokens.

    RTLIL uses ``end`` for modules and for nested cell/process/switch blocks.
    A non-greedy regular expression therefore truncates ordinary synthesized
    modules at their first cell or process.  Track the grammar's block depth so
    the emitted text is a complete, reparsable module.
    """
    parsed: list[tuple[str, str, set[str], int]] = []
    offset = 0
    module_name: str | None = None
    module_start = 0
    module_lines: list[str] = []
    depth = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if module_name is None:
            match = RTLIL_MODULE_START_RE.match(bare)
            if match is not None:
                module_name = match.group(1)
                module_start = offset
                module_lines = [line]
                depth = 1
        else:
            module_lines.append(line)
            if RTLIL_NESTED_BLOCK_RE.match(bare):
                depth += 1
            elif RTLIL_END_RE.match(bare):
                depth -= 1
                if depth == 0:
                    body = "".join(module_lines)
                    parsed.append((
                        module_name,
                        body,
                        set(RTLIL_CELL_RE.findall(body)),
                        module_start,
                    ))
                    module_name = None
                    module_lines = []
        offset += len(line)
    if module_name is not None:
        raise ExtractionError("invalid_input", f"unterminated RTLIL module {module_name!r}")
    return parsed


def parse_modules(inputs: list[Path]) -> dict[str, tuple[Path, str, set[str], bool]]:
    modules: dict[str, tuple[Path, str, set[str], bool]] = {}
    for source in inputs:
        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ExtractionError("invalid_input", f"source is not UTF-8 text: {source}") from error
        parser = parse_rtlil_modules if source.suffix.lower() in {".il", ".rtlil"} else parse_sv_modules
        for name, body, dependencies, start in parser(text):
            if name in modules:
                raise ExtractionError("ambiguous_module", f"module {name!r} is declared more than once")
            modules[name] = (source, body, dependencies, immediately_preceding_annotation(text, start))
    if not modules:
        raise ExtractionError("boundary_not_found", "no Verilog/SystemVerilog or RTLIL modules found in explicit inputs")
    return modules


def select_anchor(modules: dict[str, tuple[Path, str, set[str], bool]]) -> str:
    matches = [
        name for name, (_, _, _, annotated) in modules.items()
        if ANCHOR_RE.search(name) or annotated
    ]
    if len(matches) != 1:
        detail = "none" if not matches else ", ".join(sorted(matches))
        raise ExtractionError("boundary_not_found", f"expected exactly one block/token-step anchor, found {detail}")
    return matches[0]


def dependency_closure(anchor: str, modules: dict[str, tuple[Path, str, set[str], bool]]) -> list[str]:
    closure: set[str] = set()
    todo = [anchor]
    while todo:
        name = todo.pop()
        if name in closure:
            continue
        closure.add(name)
        dependencies = modules[name][2]
        # A declared module is always a dependency, including generated names
        # such as ``$paramod\\foo...``.  Undeclared ordinary/$paramod cells are
        # unbounded dependencies; only undeclared Yosys internal ``$`` cells
        # are primitives supplied by Yosys itself.
        unresolved = {
            dependency
            for dependency in dependencies - set(modules)
            if not (dependency.startswith("$") and not dependency.startswith("$paramod"))
        }
        if unresolved:
            raise ExtractionError(
                "unbounded_dependency_closure",
                f"{name} instantiates modules not supplied as explicit inputs: {', '.join(sorted(unresolved))}",
            )
        todo.extend(sorted((dependencies & set(modules)) - closure))
    return sorted(closure)


def unavailable_manifest(contract_path: Path, contract: dict[str, Any], reason: str, discovery: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "source_artifact_unavailable",
        "model": contract["model"]["name"],
        "contract": {"path": str(contract_path), "sha256": sha256(contract_path)},
        "slice": {"kind": SLICE_KIND, "dependency_closure": [], "status": "unavailable"},
        "failure": {"code": "source_artifact_unavailable", "reason": reason},
        "discovery": discovery,
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
        source, body, _, _ = modules[name]
        suffix = source.suffix if source.suffix.lower() in {".sv", ".v", ".il", ".rtlil"} else ".sv"
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name).strip("._-") or "module"
        name_digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        destination = slice_dir / f"{index:03d}-{safe_name}-{name_digest}{suffix}"
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
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="repository root for deterministic discovery")
    parser.add_argument("--nix-output", action="append", default=[], type=Path, help="existing Nix output path to inspect; never builds")
    parser.add_argument("--slice-dir", type=Path, help="directory for copied source closure")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    contract = load_json(args.contract)
    discovery: dict[str, Any] | None = None
    try:
        inputs = args.input
        if not inputs:
            inputs, discovery = discover_sources(args.repo_root, args.nix_output)
        if not inputs:
            raise ExtractionError("source_artifact_unavailable", "no full TinyStories-1M compiler artifact found by deterministic discovery")
        if args.metadata is None or args.slice_dir is None:
            raise ExtractionError("source_artifact_unavailable", "--metadata and --slice-dir are required for extraction")
        manifest = extract(inputs, args.metadata, args.contract, args.slice_dir)
        manifest["discovery"] = discovery
        exit_code = 0
    except ExtractionError as error:
        manifest = unavailable_manifest(args.contract, contract, str(error), discovery)
        manifest["status"] = error.code
        manifest["failure"]["code"] = error.code
        exit_code = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
