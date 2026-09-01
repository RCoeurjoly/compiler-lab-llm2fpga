#!/usr/bin/env python3
"""Independently authenticate the exact normalized pre-Calyx registration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
ALIAS = "tiny-stories-1m-kev-gpt-exact-normalized-flat-scf"
C22_INPUT = ROOT / "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/run-1/flat.scf.mlir"
CHECKER_SOURCE = ROOT / "scripts/pipeline/calyx_preflight_report.py"
C22_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
PLUGIN_SHA256 = "da138b78750abcdcc7f5f467d0991b1e2eb9cf04708186a6b4f0dd8e14df2c6e"
MLIR_OPT_SHA256 = "3da93261c9b6f698539bec86f3606598d8b3ed61a18095eaa03cde87f7140912"
CHECKER_SOURCE_SHA256 = "3957d6cfc6da168f9a5c1cb6f1013c172eff3c83f42be6266265009c84ad0839"
NORMALIZED_SHA256 = "e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77"
MLIR_VERSION = "21.1.2"
NORMALIZATION_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
PREPARATION_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,llm2fpga-drop-calyx-unsupported-asserts,llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,llm2fpga-lower-exact-math-for-calyx,llm2fpga-lower-negf-for-calyx,llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)"
REGISTERED = ("memref.collapse_shape", "memref.copy", "memref.expand_shape", "memref.reinterpret_cast")
FORBIDDEN = ("circt-opt", "/bin/calyx", "calyx ", "sv_mlir", "systemverilog", "yosys", "nextpnr", "vivado", "board")
AUTHORITY_KEYS = {
    "c22_input", "c22_sha256", "plugin", "plugin_sha256", "mlir_opt",
    "mlir_opt_sha256", "mlir_version", "checker_source", "checker_source_sha256",
    "checker", "python", "normalization_pipeline", "preparation_pipeline",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {label}: {error}") from error
    _require(isinstance(value, dict), f"{label} is not an object")
    return value


def _run(command: list[str], message: str, *, input_data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(command, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    _require(completed.returncode == 0, message + ": " + completed.stderr.decode("utf-8", errors="replace"))
    return completed


def _resolve_authority() -> dict[str, str]:
    completed = _run(
        ["nix", "eval", "--json", f".#${ALIAS}.registrationAuthority".replace("$", "")],
        "cannot resolve Nix registration authority",
    )
    try:
        authority = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("Nix registration authority is not JSON") from error
    _require(isinstance(authority, dict) and set(authority) == AUTHORITY_KEYS, "Nix registration authority schema mismatch")
    _require(all(isinstance(value, str) for value in authority.values()), "Nix registration authority value mismatch")
    typed = {str(key): str(value) for key, value in authority.items()}
    _require(typed["c22_sha256"] == C22_SHA256 and typed["plugin_sha256"] == PLUGIN_SHA256, "Nix identity hash mismatch")
    _require(typed["mlir_opt_sha256"] == MLIR_OPT_SHA256 and typed["mlir_version"] == MLIR_VERSION, "Nix MLIR identity mismatch")
    _require(typed["checker_source_sha256"] == CHECKER_SOURCE_SHA256, "Nix checker source identity mismatch")
    _require(typed["normalization_pipeline"] == NORMALIZATION_PIPELINE and typed["preparation_pipeline"] == PREPARATION_PIPELINE, "Nix pipeline mismatch")
    _require(_sha256(C22_INPUT) == C22_SHA256 and _sha256(Path(typed["c22_input"])) == C22_SHA256, "c22 input identity mismatch")
    _require(_sha256(Path(typed["plugin"])) == PLUGIN_SHA256, "plugin identity mismatch")
    _require(_sha256(Path(typed["mlir_opt"])) == MLIR_OPT_SHA256, "mlir-opt identity mismatch")
    _require(_sha256(CHECKER_SOURCE) == CHECKER_SOURCE_SHA256, "tracked checker source hash mismatch")
    _require(_sha256(Path(typed["checker_source"])) == CHECKER_SOURCE_SHA256, "Nix checker source hash mismatch")
    _require(Path(typed["python"]).is_file() and Path(typed["checker"]).is_file(), "Nix checker runtime missing")
    version = _run([typed["mlir_opt"], "--version"], "cannot query pinned mlir-opt").stdout.decode("utf-8", errors="replace")
    _require(re.search(rf"^\s*LLVM version {re.escape(MLIR_VERSION)}\s*$", version, re.MULTILINE) is not None, "mlir-opt version mismatch")
    _validate_materialized_checker(typed)
    return typed


def _validate_materialized_checker(authority: Mapping[str, str]) -> None:
    expected = CHECKER_SOURCE.read_bytes()
    substitutions = {
        b"@calyxPreflightMlirOptPath@": authority["mlir_opt"].encode(),
        b"@calyxPreflightMlirOptVersion@": authority["mlir_version"].encode(),
        b"@calyxPreflightMlirOptSha256@": authority["mlir_opt_sha256"].encode(),
    }
    for token, value in substitutions.items():
        _require(expected.count(token) == 1, "tracked checker substitution token mismatch")
        expected = expected.replace(token, value)
    actual = Path(authority["checker"]).read_bytes()
    _require(actual == expected, "materialized checker identity mismatch")


def _parse(mlir_opt: str, artifact: Path) -> None:
    _run([mlir_opt, str(artifact), "-o", "/dev/null"], f"MLIR parse failed for {artifact.name}")


def _registered_counts(mlir_opt: str, artifact: Path) -> dict[str, int]:
    generic = _run([mlir_opt, str(artifact), "-mlir-print-op-generic"], f"generic MLIR parse failed for {artifact.name}").stdout.decode("utf-8")
    return {name: len(re.findall(rf'"{re.escape(name)}"\(', generic)) for name in REGISTERED}


def _validate_legality(legality: dict[str, Any], authority: Mapping[str, str]) -> None:
    _require(legality.get("schema_version") == 3, "legality schema mismatch")
    unsigned = dict(legality)
    claimed = unsigned.pop("sha256", None)
    _require(isinstance(claimed, str) and claimed == hashlib.sha256(_canonical(unsigned)).hexdigest(), "legality self-hash mismatch")
    prohibited, diagnostics = legality.get("prohibited_ops"), legality.get("scanner_diagnostics")
    _require(isinstance(prohibited, dict) and isinstance(diagnostics, list), "legality census malformed")
    _require(prohibited.get("math.floor", 0) == 0, "math.floor successor frontier mismatch")
    _require(prohibited.get("arith.negf", 0) == 0, "arith.negf successor frontier mismatch")
    _require(legality.get("status") == ("blocked" if prohibited or diagnostics else "ok"), "legality status mismatch")
    validation = legality.get("parser_validation")
    _require(isinstance(validation, dict) and validation.get("identity_status") == "verified" and validation.get("input_status") == "accepted", "parser validation mismatch")
    authorized, observed = validation.get("authorized_identity"), validation.get("observed_identity")
    _require(isinstance(authorized, dict) and isinstance(observed, dict), "parser identity payload malformed")
    _require(authorized == {"canonical_path": authority["mlir_opt"], "sha256": MLIR_OPT_SHA256, "version": MLIR_VERSION}, "authorized parser identity mismatch")
    _require(observed.get("canonical_path") == authority["mlir_opt"] and observed.get("sha256") == MLIR_OPT_SHA256, "observed parser identity mismatch")


def _expected_commands(authority: Mapping[str, str], output: Path) -> dict[str, list[str]]:
    flat, prepared, legality = output / "flat.scf.mlir", output / "pre-calyx.mlir", output / "pre-calyx-legality.json"
    return {
        "normalize": [authority["mlir_opt"], authority["c22_input"], f"--load-pass-plugin={authority['plugin']}", f"--pass-pipeline={authority['normalization_pipeline']}", "-o", str(flat)],
        "parse_flat": [authority["mlir_opt"], str(flat), "-o", "/dev/null"],
        "prepare": [authority["mlir_opt"], str(flat), f"--load-pass-plugin={authority['plugin']}", f"--pass-pipeline={authority['preparation_pipeline']}", "-o", str(prepared)],
        "parse_prepared": [authority["mlir_opt"], str(prepared), "-o", "/dev/null"],
        "preflight": [authority["python"], authority["checker"], str(prepared), str(legality), "--mlir-opt", authority["mlir_opt"]],
    }


def validate_manifest(manifest: dict[str, Any], output: Path, authority: Mapping[str, str] | None = None) -> None:
    """Compare mutable bundle claims against independently resolved authority."""
    authority = dict(authority or _resolve_authority())
    _require(manifest.get("schema") == "tinystories-1m-exact-normalized-registration-v1", "manifest schema mismatch")
    _require(manifest.get("model") == "tiny-stories-1m-kev-gpt-exact", "manifest model mismatch")
    normalization, preparation, commands = manifest.get("normalization"), manifest.get("preparation"), manifest.get("commands")
    _require(isinstance(normalization, dict) and isinstance(preparation, dict) and isinstance(commands, dict), "manifest stage missing")
    _require(normalization.get("pipeline") == authority["normalization_pipeline"] and preparation.get("pipeline") == authority["preparation_pipeline"], "manifest pipeline mismatch")
    _require(normalization.get("input", {}).get("sha256") == C22_SHA256 and normalization.get("plugin", {}).get("sha256") == PLUGIN_SHA256, "manifest authority identity mismatch")
    _require(normalization.get("plugin", {}).get("path") == authority["plugin"], "manifest plugin path mismatch")
    _require(normalization.get("output", {}).get("sha256") == NORMALIZED_SHA256, "normalized manifest hash mismatch")
    _require(normalization.get("registered_blocker_counts") == {name: 0 for name in REGISTERED}, "registered raw blocker census mismatch")
    flat, prepared, legality_path = output / "flat.scf.mlir", output / "pre-calyx.mlir", output / "pre-calyx-legality.json"
    _require(all(path.is_file() for path in (flat, prepared, legality_path)), "registered output incomplete")
    _require(_sha256(flat) == NORMALIZED_SHA256 and preparation.get("input", {}).get("sha256") == NORMALIZED_SHA256, "normalized binding mismatch")
    _require(preparation.get("output", {}).get("sha256") == _sha256(prepared) and preparation.get("parse_status") == "ok", "prepared output binding mismatch")
    legality = _load(legality_path, "legality receipt")
    _validate_legality(legality, authority)
    receipt = preparation.get("legality")
    _require(isinstance(receipt, dict) and receipt == {"path": legality_path.name, "sha256": _sha256(legality_path), "status": legality["status"], "receipt_sha256": legality["sha256"]}, "legality receipt binding mismatch")
    _require(manifest.get("calyx_authorized") is (legality["status"] == "ok"), "Calyx authorization gate mismatch")
    _require(commands == _expected_commands(authority, output), "manifest command vector mismatch")
    rendered = "\n".join(" ".join(command) for command in commands.values()).lower()
    _require(all(term not in rendered for term in FORBIDDEN), "command crosses pre-Calyx boundary")


def _replay(authority: Mapping[str, str], output: Path, legality: dict[str, Any]) -> None:
    with tempfile.TemporaryDirectory(prefix="exact-normalized-replay-", dir="/dev/shm") as raw:
        temporary = Path(raw)
        flat, prepared, replay_legality = temporary / "flat.scf.mlir", temporary / "pre-calyx.mlir", temporary / "legality.json"
        _run([authority["mlir_opt"], authority["c22_input"], f"--load-pass-plugin={authority['plugin']}", f"--pass-pipeline={authority['normalization_pipeline']}", "-o", str(flat)], "normalization replay failed")
        _parse(authority["mlir_opt"], flat)
        _require(flat.read_bytes() == (output / "flat.scf.mlir").read_bytes() and _sha256(flat) == NORMALIZED_SHA256, "normalization replay mismatch")
        _require(_registered_counts(authority["mlir_opt"], flat) == {name: 0 for name in REGISTERED}, "independent raw blocker census mismatch")
        _run([authority["mlir_opt"], str(flat), f"--load-pass-plugin={authority['plugin']}", f"--pass-pipeline={authority['preparation_pipeline']}", "-o", str(prepared)], "preparation replay failed")
        _parse(authority["mlir_opt"], prepared)
        _require(prepared.read_bytes() == (output / "pre-calyx.mlir").read_bytes(), "preparation replay mismatch")
        _run([authority["python"], authority["checker"], str(prepared), str(replay_legality), "--mlir-opt", authority["mlir_opt"]], "independent checker replay failed")
        _require(_load(replay_legality, "replayed legality receipt") == legality, "independent checker replay mismatch")


def verify_output(output: Path) -> dict[str, Any]:
    authority = _resolve_authority()
    manifest = _load(output / "manifest.json", "registration manifest")
    validate_manifest(manifest, output, authority)
    legality = _load(output / "pre-calyx-legality.json", "legality receipt")
    _replay(authority, output, legality)
    return {"manifest": manifest, "legality": legality}


def _resolve_output() -> Path:
    return Path(_run(["nix", "build", "--no-link", "--print-out-paths", f".#${ALIAS}".replace("$", "")], "registered derivation did not build").stdout.decode().strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    legality = verify_output(args.output or _resolve_output())["legality"]
    print(json.dumps({"status": legality["status"], "prohibited_ops": legality["prohibited_ops"], "first_locations": legality["first_locations"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
