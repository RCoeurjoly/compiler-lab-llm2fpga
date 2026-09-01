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
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ALIAS = "tiny-stories-1m-kev-gpt-exact-normalized-flat-scf"
C22_INPUT = ROOT / (
    "artifacts/comparison/tinystories-1m-exact-frontier-determinism-flat-scf/"
    "run-1/flat.scf.mlir"
)
C22_SHA256 = "66c78e412ade3262c4eb0f61b5776e9c765fb434fdbb53d09cbba7e724ff2fc6"
PLUGIN_SHA256 = "79c0ab56022ce6c91279bca8aefeea7251a1eb19c92675f6df7b90265fb0d738"
NORMALIZED_SHA256 = "e669a26338fbcf055266db29d6351228b78314d11ea3687751cb7f2045552d77"
NORMALIZATION_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,canonicalize,cse)"
PREPARATION_PIPELINE = "builtin.module(llm2fpga-lower-static-memref-views-for-calyx,llm2fpga-drop-calyx-unsupported-asserts,llm2fpga-fold-constant-truncf,llm2fpga-lower-roundeven-for-calyx,llm2fpga-lower-exact-math-for-calyx,llm2fpga-lower-i1-uitofp-for-calyx,canonicalize,cse)"
REGISTERED = ("memref.collapse_shape", "memref.copy", "memref.expand_shape", "memref.reinterpret_cast")
FORBIDDEN = ("circt-opt", "/bin/calyx", "calyx ", "sv_mlir", "systemverilog", "yosys", "nextpnr", "vivado", "board")


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


def _parse(mlir_opt: Path, artifact: Path) -> None:
    complete = subprocess.run([str(mlir_opt), str(artifact), "-o", "/dev/null"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    _require(complete.returncode == 0, f"MLIR parse failed for {artifact.name}")


def _registered_counts(mlir_opt: Path, artifact: Path) -> dict[str, int]:
    complete = subprocess.run([str(mlir_opt), str(artifact), "-mlir-print-op-generic"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    _require(complete.returncode == 0, f"generic MLIR parse failed for {artifact.name}")
    generic = complete.stdout.decode("utf-8")
    return {name: len(re.findall(rf'"{re.escape(name)}"\(', generic)) for name in REGISTERED}


def _validate_legality(legality: dict[str, Any]) -> Path:
    _require(legality.get("schema_version") == 3, "legality schema mismatch")
    unsigned = dict(legality)
    claimed = unsigned.pop("sha256", None)
    _require(isinstance(claimed, str) and claimed == hashlib.sha256(_canonical(unsigned)).hexdigest(), "legality self-hash mismatch")
    prohibited, diagnostics = legality.get("prohibited_ops"), legality.get("scanner_diagnostics")
    _require(isinstance(prohibited, dict) and isinstance(diagnostics, list), "legality census malformed")
    _require(legality.get("status") == ("blocked" if prohibited or diagnostics else "ok"), "legality status mismatch")
    validation = legality.get("parser_validation")
    _require(isinstance(validation, dict) and validation.get("identity_status") == "verified" and validation.get("input_status") == "accepted", "parser validation mismatch")
    authorized, observed = validation.get("authorized_identity"), validation.get("observed_identity")
    _require(isinstance(authorized, dict) and isinstance(observed, dict), "parser identity payload malformed")
    parser = Path(str(authorized.get("canonical_path", "")))
    _require(parser.is_file() and observed.get("canonical_path") == str(parser.resolve()), "parser path mismatch")
    _require(authorized.get("sha256") == observed.get("sha256") == _sha256(parser), "parser hash mismatch")
    return parser


def validate_manifest(manifest: dict[str, Any], output: Path) -> None:
    """Validate all static bindings without relying on the producer's claims."""
    _require(manifest.get("schema") == "tinystories-1m-exact-normalized-registration-v1", "manifest schema mismatch")
    _require(manifest.get("model") == "tiny-stories-1m-kev-gpt-exact", "manifest model mismatch")
    normalization, preparation, commands = (manifest.get("normalization"), manifest.get("preparation"), manifest.get("commands"))
    _require(isinstance(normalization, dict) and isinstance(preparation, dict) and isinstance(commands, dict), "manifest stage missing")
    _require(set(commands) == {"normalize", "parse_flat", "prepare", "parse_prepared", "preflight"}, "manifest commands mismatch")
    _require(normalization.get("pipeline") == NORMALIZATION_PIPELINE, "normalization pipeline mismatch")
    _require(preparation.get("pipeline") == PREPARATION_PIPELINE, "preparation pipeline mismatch")
    _require(normalization.get("input", {}).get("sha256") == C22_SHA256, "c22 manifest hash mismatch")
    _require(normalization.get("plugin", {}).get("sha256") == PLUGIN_SHA256, "plugin manifest hash mismatch")
    _require(normalization.get("output", {}).get("sha256") == NORMALIZED_SHA256, "normalized manifest hash mismatch")
    _require(normalization.get("registered_blocker_counts") == {name: 0 for name in REGISTERED}, "registered raw blocker census mismatch")
    flat, prepared, legality_path = output / "flat.scf.mlir", output / "pre-calyx.mlir", output / "pre-calyx-legality.json"
    _require(all(path.is_file() for path in (flat, prepared, legality_path)), "registered output incomplete")
    _require(_sha256(flat) == NORMALIZED_SHA256, "normalized output hash mismatch")
    _require(preparation.get("input", {}).get("sha256") == NORMALIZED_SHA256, "prepared input binding mismatch")
    _require(preparation.get("output", {}).get("sha256") == _sha256(prepared), "prepared output hash mismatch")
    _require(preparation.get("parse_status") == "ok", "prepared parse status mismatch")
    legality = _load(legality_path, "legality receipt")
    _validate_legality(legality)
    receipt = preparation.get("legality")
    _require(isinstance(receipt, dict), "prepared legality binding missing")
    _require(receipt.get("path") == legality_path.name and receipt.get("sha256") == _sha256(legality_path), "legality file binding mismatch")
    _require(receipt.get("receipt_sha256") == legality.get("sha256") and receipt.get("status") == legality.get("status"), "legality receipt binding mismatch")
    _require(manifest.get("calyx_authorized") is (legality.get("status") == "ok"), "Calyx authorization gate mismatch")
    rendered = "\n".join(" ".join(command) for command in commands.values() if isinstance(command, list)).lower()
    _require(all(term not in rendered for term in FORBIDDEN), "command crosses pre-Calyx boundary")
    _require(all(isinstance(command, list) and command and str(command[0]).endswith(("/mlir-opt", "/python3")) for command in commands.values()), "unexpected command executable")


def verify_output(output: Path) -> dict[str, Any]:
    manifest = _load(output / "manifest.json", "registration manifest")
    validate_manifest(manifest, output)
    _require(_sha256(C22_INPUT) == C22_SHA256, "tracked c22 input hash mismatch")
    plugin = Path(str(manifest["normalization"]["plugin"]["path"]))
    _require(plugin.is_file() and _sha256(plugin) == PLUGIN_SHA256, "plugin identity mismatch")
    legality = _load(output / "pre-calyx-legality.json", "legality receipt")
    parser = _validate_legality(legality)
    _parse(parser, output / "flat.scf.mlir")
    _parse(parser, output / "pre-calyx.mlir")
    _require(_registered_counts(parser, output / "flat.scf.mlir") == {name: 0 for name in REGISTERED}, "independent raw blocker census mismatch")
    preflight = Path(str(manifest["commands"]["preflight"][1]))
    _require(preflight.is_file(), "materialized legality checker missing")
    with tempfile.TemporaryDirectory(prefix="exact-precalyx-", dir="/dev/shm") as raw:
        replay = Path(raw) / "legality.json"
        complete = subprocess.run([str(manifest["commands"]["preflight"][0]), str(preflight), str(output / "pre-calyx.mlir"), str(replay), "--mlir-opt", str(parser)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        _require(complete.returncode == 0 and _load(replay, "replayed legality receipt") == legality, "legality checker replay mismatch")
    return {"manifest": manifest, "legality": legality}


def _resolve_output() -> Path:
    complete = subprocess.run(["nix", "build", "--no-link", "--print-out-paths", f".#${ALIAS}".replace("$", "")], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    _require(complete.returncode == 0, "registered derivation did not build: " + complete.stderr)
    return Path(complete.stdout.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_output(args.output or _resolve_output())
    legality = result["legality"]
    print(json.dumps({"status": legality["status"], "prohibited_ops": legality["prohibited_ops"], "first_locations": legality["first_locations"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
