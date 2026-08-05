#!/usr/bin/env python3
"""Shared validation and reproducible provenance helpers for the survey."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml


EXPECTED_LEVELS = {"A", "B", "C", "D", "X"}
EXPECTED_EXCLUSIONS = {
    "X_NOT_FPGA",
    "X_LLM_FOR_EDA",
    "X_TRAINING_ONLY",
    "X_NON_LM_MODEL",
    "X_VIT_NO_TRANSFER",
    "X_ASIC_GPU_ONLY",
    "X_PERFORMANCE_MODEL_ONLY",
    "X_SECONDARY",
    "X_NO_EVIDENCE",
    "X_DUPLICATE",
    "X_RETRACTED",
}
EXPECTED_WEIGHTS = {
    "demonstrator_score_0_5",
    "foss_score_0_5",
    "end_to_end_score_0_5",
    "reuse_score_0_5",
    "verification_score_0_5",
    "hardware_score_0_5",
    "performance_score_0_5",
}
PACKAGE_DISTRIBUTIONS = {
    "pandas": "pandas",
    "pyarrow": "pyarrow",
    "pyyaml": "PyYAML",
    "rapidfuzz": "RapidFuzz",
    "unidecode": "Unidecode",
    "requests": "requests",
    "requests-cache": "requests-cache",
    "tabulate": "tabulate",
}


def load_scope(path: Path) -> dict[str, object]:
    """Load and validate the frozen survey scope contract."""

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("scope must be a YAML mapping")

    levels = loaded.get("levels")
    if not isinstance(levels, dict) or set(levels) != EXPECTED_LEVELS:
        raise ValueError(
            "levels must define exactly A, B, C, D, and X; "
            f"found {sorted(levels) if isinstance(levels, dict) else 'none'}"
        )
    required_level_fields = {
        "operational_definition",
        "required_evidence",
        "review_treatment",
    }
    for level, definition in levels.items():
        if not isinstance(definition, dict) or not required_level_fields.issubset(
            definition
        ):
            raise ValueError(f"levels.{level} is missing required level definitions")
        if any(not str(definition[field]).strip() for field in required_level_fields):
            raise ValueError(f"levels.{level} contains an empty level definition")

    exclusions = loaded.get("controlled_exclusions")
    if not isinstance(exclusions, dict) or set(exclusions) != EXPECTED_EXCLUSIONS:
        missing = sorted(
            EXPECTED_EXCLUSIONS - (set(exclusions) if isinstance(exclusions, dict) else set())
        )
        extra = sorted(
            (set(exclusions) if isinstance(exclusions, dict) else set())
            - EXPECTED_EXCLUSIONS
        )
        raise ValueError(
            "controlled exclusions do not match the frozen vocabulary; "
            f"missing={missing}, extra={extra}"
        )
    if any(not str(description).strip() for description in exclusions.values()):
        raise ValueError("controlled exclusions must have non-empty definitions")

    decision_matrix = loaded.get("decision_matrix")
    weights = decision_matrix.get("weights") if isinstance(decision_matrix, dict) else None
    if not isinstance(weights, dict) or set(weights) != EXPECTED_WEIGHTS:
        raise ValueError("decision-matrix weights must define all seven criteria")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in weights.values()):
        raise ValueError("decision-matrix weights must be numeric")
    if sum(weights.values()) != 100:
        raise ValueError("decision-matrix weights must sum to 100")

    snapshot = loaded.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a mapping")
    if snapshot.get("expected_records") != 461:
        raise ValueError("snapshot expected_records must be the pinned count 461")
    if snapshot.get("protocol_stated_records") != 459:
        raise ValueError("snapshot protocol_stated_records must preserve 459")

    return loaded


def _run(*command: str, cwd: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            list(command), cwd=cwd, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        location = f" in {cwd}" if cwd is not None else ""
        raise RuntimeError(f"failed to run {' '.join(command)}{location}") from error


def _sanitize_remote(remote: str) -> str:
    """Remove HTTP credentials while preserving credential-free repository URLs."""

    if "://" not in remote:
        return remote
    parsed = urlsplit(remote)
    hostname = parsed.hostname or ""
    if parsed.port is not None:
        hostname = f"{hostname}:{parsed.port}"
    return urlunsplit((parsed.scheme, hostname, parsed.path, parsed.query, parsed.fragment))


def _source_path(root: Path, path: Path) -> str:
    relative = os.path.relpath(path.resolve(), start=root.resolve())
    return Path(relative).as_posix()


def _repository(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": _source_path(root, path),
        "commit": _run("git", "rev-parse", "HEAD", cwd=path),
        "remote": _sanitize_remote(
            _run("git", "remote", "get-url", "origin", cwd=path)
        ),
    }


def _find_sibling_repository(root: Path, name: str) -> Path:
    candidates = [root.parent / name]
    candidates.extend(parent / name for parent in root.parents)
    for candidate in candidates:
        if candidate.is_dir() and (candidate / ".git").exists():
            return candidate.resolve()
    raise FileNotFoundError(
        f"could not locate sibling repository {name!r} from source tree {root}"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _catalogue_record_count(path: Path) -> int:
    catalogue = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(catalogue, list):
        return len(catalogue)
    if isinstance(catalogue, dict):
        papers = catalogue.get("papers")
        if isinstance(papers, (list, dict)):
            return len(papers)
    raise ValueError(f"could not locate catalogue records in {path}")


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for output_name, distribution in PACKAGE_DISTRIBUTIONS.items():
        try:
            versions[output_name] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError as error:
            raise RuntimeError(
                f"required survey Python distribution is unavailable: {distribution}"
            ) from error
    return versions


def _tool_versions() -> dict[str, object]:
    return {
        "python": platform.python_version(),
        "git": _run("git", "--version"),
        "nix": _run("nix", "--version"),
        "python_packages": _package_versions(),
    }


def _atomic_write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _frozen_input_paths(root: Path, papers: Path, scope: dict[str, object]) -> list[Path]:
    inputs = [
        root / "survey/protocol.md",
        root / "survey/config/scope.yaml",
        root / "survey/data/manual_overrides.csv",
        root / "survey/data/route_vocabulary.csv",
    ]
    data_directory = papers / "data"
    inputs.extend(path for path in data_directory.rglob("*") if path.is_file())
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing frozen survey inputs: {missing}")
    return sorted(set(inputs))


def write_provenance(root: Path, output: Path) -> dict[str, object]:
    """Record commit-pinned repositories, inputs, counts, and tool versions."""

    root = root.resolve()
    scope = load_scope(root / "survey/config/scope.yaml")
    snapshot = scope["snapshot"]
    assert isinstance(snapshot, dict)
    papers = root / "LLM-inference-on-FPGA-papers"
    llm2fpga = _find_sibling_repository(root, "LLM2FPGA")

    repositories = {
        "compiler_lab": _repository(root, root),
        "papers": _repository(root, papers),
        "llm2fpga": _repository(root, llm2fpga),
    }
    expected_papers_commit = str(snapshot["papers_commit"])
    if repositories["papers"]["commit"] != expected_papers_commit:
        raise ValueError(
            "papers repository is not at the frozen commit: "
            f"expected {expected_papers_commit}, found {repositories['papers']['commit']}"
        )

    catalogue = root / str(snapshot["catalogue_path"])
    expected_records = int(snapshot["expected_records"])
    actual_records = _catalogue_record_count(catalogue)
    if actual_records != expected_records:
        raise ValueError(
            f"catalogue count mismatch: expected {expected_records}, found {actual_records}"
        )

    input_sha256 = {
        _source_path(root, path): _sha256(path)
        for path in _frozen_input_paths(root, papers, scope)
    }
    catalogue_key = _source_path(root, catalogue)
    provenance: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_records": expected_records,
        "protocol_record_count": int(snapshot["protocol_stated_records"]),
        "actual_catalogue_records": actual_records,
        "catalog_sha256": input_sha256[catalogue_key],
        "input_sha256": input_sha256,
        "tool_versions": _tool_versions(),
        "repositories": repositories,
        # Stable flat keys retain the protocol's original provenance interface.
        "compiler_lab_commit": repositories["compiler_lab"]["commit"],
        "compiler_lab_remote": repositories["compiler_lab"]["remote"],
        "papers_commit": repositories["papers"]["commit"],
        "papers_remote": repositories["papers"]["remote"],
        "llm2fpga_commit": repositories["llm2fpga"]["commit"],
        "llm2fpga_remote": repositories["llm2fpga"]["remote"],
    }
    _atomic_write_json(output, provenance)
    return provenance


def write_environment_manifest(root: Path, output: Path) -> dict[str, object]:
    """Write the pinned survey interpreter and package manifest."""

    root = root.resolve()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "interpreter": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "tools": {
            "git": _run("git", "--version"),
            "nix": _run("nix", "--version"),
        },
        "python_packages": _package_versions(),
        "flake_nix_sha256": _sha256(root / "flake.nix"),
        "flake_lock_sha256": _sha256(root / "flake.lock"),
    }
    _atomic_write_json(output, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--provenance",
        type=Path,
        default=Path("survey/build/provenance.json"),
    )
    parser.add_argument(
        "--environment",
        type=Path,
        default=Path("survey/build/environment_manifest.json"),
    )
    args = parser.parse_args()

    provenance = write_provenance(args.root, args.provenance)
    environment = write_environment_manifest(args.root, args.environment)
    print(
        json.dumps(
            {
                "provenance": str(args.provenance),
                "environment": str(args.environment),
                "expected_records": provenance["expected_records"],
                "python": environment["interpreter"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
