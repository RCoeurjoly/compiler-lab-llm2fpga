#!/usr/bin/env python3
"""Generate the bounded MLIR/CIRCT stage survey and route decision matrix.

The generated decision is deliberately eligibility-first: a weighted score is
useful for prioritising evidence gathering, but it cannot promote a route that
fails any hard gate in the frozen survey scope.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = Path("survey/config/scope.yaml")
CANONICAL_STAGE_CATALOG_PATH = Path("survey/data/mlir_circt_stage_catalog.json")
CANONICAL_PROTOCOL_SHA256 = "5112ba94144043a5d3cefa01b29d89dd3eb8643633a9a6fb26c9e20ca372fb2e"
CONTROL_PROJECT = "compiler-lab"
PROJECTS = (CONTROL_PROJECT, "Allo", "Olympus")
# Internal shorthand for the locally exercised control route rows below.
PROJECT = CONTROL_PROJECT
FIRST_FAILED_GATE_SEMANTICS = "protocol_order"

# These ceilings deliberately encode the supplied-protocol anchors rather than
# treating a citation as evidence for an arbitrarily high score.  The underlying
# source-audit receipts remain the evidence for the low, bounded values.
SCORE_ANCHOR_CEILINGS = {
    ("R1", "foss_score_0_5"): 2,
    ("R2", "demonstrator_score_0_5"): 2,
    ("R4", "demonstrator_score_0_5"): 0,
}

StageStatus = Literal[
    "native", "extension_available", "manual_implementation", "missing"
]

STAGE_STATUSES = frozenset(
    {"native", "extension_available", "manual_implementation", "missing"}
)
NATIVE_EVIDENCE_KINDS = frozenset({"source_test", "source_example"})

HARD_GATES = (
    "source_access",
    "license",
    "reproducible_minimal_build",
    "model_path",
    "no_required_closed_ip",
    "complete_rtl",
    "test_budget",
    "deterministic_reference",
)

SCORE_WEIGHTS = {
    "demonstrator_score_0_5": 25,
    "foss_score_0_5": 20,
    "end_to_end_score_0_5": 15,
    "reuse_score_0_5": 15,
    "verification_score_0_5": 10,
    "hardware_score_0_5": 10,
    "performance_score_0_5": 5,
}

STAGE_COLUMNS = (
    "ordinal",
    "project",
    "stage",
    "status",
    "evidence_kind",
    "evidence_location",
    "rationale",
)

DECISION_COLUMNS = (
    "route_id",
    "route_title",
    "route_family",
    "receipt_manifest",
    "receipt_readme",
    "actual_stage",
    "failure_code",
    "first_failed_gate",
    "first_failed_gate_semantics",
    *HARD_GATES,
    *(f"{gate}_evidence" for gate in HARD_GATES),
    *SCORE_WEIGHTS,
    *(f"{criterion}_evidence" for criterion in SCORE_WEIGHTS),
    "weighted_total",
    "effective_total",
    "selection_status",
    "notes",
)


_COMPILER_LAB_STAGE_ROWS: tuple[dict[str, object], ...] = (
    {
        "ordinal": 1,
        "project": PROJECT,
        "stage": "PyTorch model capture",
        "status": "native",
        "evidence_kind": "source_example",
        "evidence_location": (
            "scripts/compile-pytorch.py#lines=13-69; "
            "survey/compatibility/R1-mlir-circt/stdout.log#lines=16-20"
        ),
        "rationale": (
            "The checked-in capture script loads a serialized ExportedProgram and "
            "imports it through torch-mlir; the pinned R1 receipt built the export "
            "and Linalg artifacts. This is capture evidence, not a decoder pass."
        ),
    },
    {
        "ordinal": 2,
        "project": PROJECT,
        "stage": "Dynamic-to-static shape specialization",
        "status": "missing",
        "evidence_kind": "negative_evidence",
        "evidence_location": (
            "survey/config/scope.yaml#key=fixtures.M0-operators; "
            "scripts/compile-pytorch.py#lines=17-18"
        ),
        "rationale": (
            "The cited scope and CLI wiring do not exercise shape specialization or "
            "show a fixed-shape export construction. No pinned generic "
            "dynamic-shape-specialisation pass or decoder example was found."
        ),
    },
    {
        "ordinal": 3,
        "project": PROJECT,
        "stage": "Tensor-to-buffer conversion",
        "status": "missing",
        "evidence_kind": "negative_evidence",
        "evidence_location": (
            "scripts/pipeline/linalg_to_scf_no_handshake.sh#lines=18-28; "
            "tests/test_quantized_linalg_diagnostics.py#lines=89-123"
        ),
        "rationale": (
            "The pipeline declares one-shot bufferization, but the cited test inspects "
            "pipeline wiring and the final receipt stops at Linalg. No exercised "
            "tensor-to-buffer output is retained."
        ),
    },
    {
        "ordinal": 4,
        "project": PROJECT,
        "stage": "Quantized/fixed-point type legalization",
        "status": "extension_available",
        "evidence_kind": "source_test",
        "evidence_location": (
            "tools/mlir-passes/LegalizePt2eTosaZeroPoint.cpp#lines=65-160; "
            "tests/test_quantized_linalg_diagnostics.py#lines=39-103"
        ),
        "rationale": (
            "A local PT2E/TOSA zero-point legalization pass and integer-post-matmul "
            "diagnostic exist. They do not establish complete fixed-point transformer "
            "legalization."
        ),
    },
    {
        "ordinal": 5,
        "project": PROJECT,
        "stage": "MatMul tiling and data reuse",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No pinned tiling, reuse schedule, or exercised transformer MatMul mapping was found.",
    },
    {
        "ordinal": 6,
        "project": PROJECT,
        "stage": "Attention/QKV fusion",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No active source pass or exercised QKV-fusion example was found.",
    },
    {
        "ordinal": 7,
        "project": PROJECT,
        "stage": "Causal masking",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "The bounded capture evidence does not establish a generated causal-mask hardware lowering.",
    },
    {
        "ordinal": 8,
        "project": PROJECT,
        "stage": "Softmax approximation",
        "status": "missing",
        "evidence_kind": "negative_evidence",
        "evidence_location": (
            "tools/mlir-passes/FoldConstantTruncFOps.cpp#lines=668-790; "
            "tests/test_calyx_math_legalization.py#lines=22-45; "
            "docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md#lines=23-45"
        ),
        "rationale": (
            "Opt-in scalar exp ingredients exist, but there is no tested composed "
            "Softmax transformation or oracle comparison. The documented standard "
            "route rejects math.exp."
        ),
    },
    {
        "ordinal": 9,
        "project": PROJECT,
        "stage": "LayerNorm/RMSNorm lowering",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No complete LayerNorm or RMSNorm hardware lowering is exercised by the pinned route.",
    },
    {
        "ordinal": 10,
        "project": PROJECT,
        "stage": "GELU/SiLU approximation",
        "status": "missing",
        "evidence_kind": "negative_evidence",
        "evidence_location": (
            "tools/mlir-passes/FoldConstantTruncFOps.cpp#lines=668-885; "
            "tests/test_calyx_math_legalization.py#lines=22-65; "
            "docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md#lines=23-45"
        ),
        "rationale": (
            "The local source exposes scalar tanh and constant-fpowi ingredients, "
            "but no tested composed GELU or SiLU transformation or equivalence result "
            "exists."
        ),
    },
    {
        "ordinal": 11,
        "project": PROJECT,
        "stage": "RoPE lowering",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No pinned RoPE lowering pass or exercised hardware example was found.",
    },
    {
        "ordinal": 12,
        "project": PROJECT,
        "stage": "KV-cache state and addressing",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "R1 contains no M2 stateful-decode pass receipt or persistent KV-cache evidence.",
    },
    {
        "ordinal": 13,
        "project": PROJECT,
        "stage": "Buffer banking and memory-port assignment",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "Bufferization evidence does not establish a banking or port-assignment policy.",
    },
    {
        "ordinal": 14,
        "project": PROJECT,
        "stage": "Resource sharing and scheduling",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No compact decoder scheduling or resource-sharing pass is exercised by the current route.",
    },
    {
        "ordinal": 15,
        "project": PROJECT,
        "stage": "Backpressure and deadlock handling",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "The active successful pre-Calyx path deliberately omits a Handshake tail; no deadlock evidence exists.",
    },
    {
        "ordinal": 16,
        "project": PROJECT,
        "stage": "Weight-loading interface",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No exercised weight-loading ABI or generated interface is present in the final R1 receipt.",
    },
    {
        "ordinal": 17,
        "project": PROJECT,
        "stage": "AXI/stream/memory interface generation",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "R1 stops before complete RTL, so it provides no independently lintable generated interface.",
    },
    {
        "ordinal": 18,
        "project": PROJECT,
        "stage": "Synthesizable memory inference",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No independently synthesizable inferred-memory result is recorded for the current route.",
    },
    {
        "ordinal": 19,
        "project": PROJECT,
        "stage": "Clock/reset generation",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "No complete generated RTL result exists from which a clock/reset interface could be assessed.",
    },
    {
        "ordinal": 20,
        "project": PROJECT,
        "stage": "FPGA-family technology mapping",
        "status": "missing",
        "evidence_kind": "",
        "evidence_location": "",
        "rationale": "The final R1 receipt has no completed synthesis or FPGA-family mapping pass.",
    },
)


_EXTERNAL_AUDIT_CONTEXT: dict[str, dict[str, str]] = {
    "Allo": {
        "evidence_kind": "source_closure_audit",
        "evidence_location": (
            "survey/compatibility/R4-mlir-hls/README.md#lines=1-16; "
            "survey/build/repository_audit.csv#repository_audit_id=REPO-PF-86FE8DBFB50CB04C"
        ),
        "rationale": (
            "The audited general Allo tree is Apache-2.0, but the exact LLM artifact "
            "is a future-release claim. No stage-specific result is reproduced here."
        ),
    },
    "Olympus": {
        "evidence_kind": "paper_and_artifact_audit",
        "evidence_location": (
            "survey/build/deep_review.csv#project_family_id=PF-5423EA8E2FD4952E; "
            "survey/build/artifact_inventory.csv#project_family_id=PF-5423EA8E2FD4952E"
        ),
        "rationale": (
            "The deep review describes MLIR platform transformations, but no causal-LM "
            "implementation or attributed project artifact was available for a "
            "stage-specific claim."
        ),
    },
}


def _load_canonical_stage_catalog(root: Path = ROOT) -> tuple[dict[str, object], ...]:
    """Load and validate the tracked, portable source transcription."""

    catalog_path = root / CANONICAL_STAGE_CATALOG_PATH
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("canonical stage catalog must contain an object")
    provenance = payload.get("source_provenance")
    stages = payload.get("stages")
    if not isinstance(provenance, dict) or not isinstance(stages, list):
        raise ValueError("canonical stage catalog is missing provenance or stages")
    if provenance.get("source_sha256") != CANONICAL_PROTOCOL_SHA256:
        raise ValueError("canonical stage catalog source SHA-256 does not match")
    if provenance.get("source_filename") != "survey_protocol_llm2fpga.md":
        raise ValueError("canonical stage catalog source filename does not match")
    if provenance.get("source_line_range") != "1170-1203":
        raise ValueError("canonical stage catalog source line range does not match")
    expected_ordinals = list(range(1, 21))
    ordinals = [stage.get("ordinal") if isinstance(stage, dict) else None for stage in stages]
    names = [stage.get("name") if isinstance(stage, dict) else None for stage in stages]
    if ordinals != expected_ordinals or any(not isinstance(name, str) for name in names):
        raise ValueError("canonical stage catalog must define ordered ordinals 1 through 20")
    return tuple(cast(dict[str, object], stage) for stage in stages)


def _external_stage_rows(root: Path = ROOT) -> tuple[dict[str, object], ...]:
    """Return source-closure-aware audit rows for non-control projects."""

    catalog = _load_canonical_stage_catalog(root)
    rows: list[dict[str, object]] = []
    for project in PROJECTS:
        if project == CONTROL_PROJECT:
            continue
        context = _EXTERNAL_AUDIT_CONTEXT[project]
        for stage in catalog:
            rows.append(
                {
                    "ordinal": stage["ordinal"],
                    "project": project,
                    "stage": stage["name"],
                    "status": "missing",
                    "evidence_kind": context["evidence_kind"],
                    "evidence_location": context["evidence_location"],
                    "rationale": context["rationale"],
                }
            )
    return tuple(rows)


def _gate_evidence(route: str) -> dict[str, str]:
    return {gate: route for gate in HARD_GATES}


_ROUTE_ASSESSMENTS: tuple[dict[str, object], ...] = (
    {
        "route_id": "R1",
        "route_title": "compiler-lab MLIR/CIRCT control",
        "route_family": "MLIR_CIRCT",
        "receipt_manifest": "survey/compatibility/R1-mlir-circt/manifest.json",
        "receipt_readme": "survey/compatibility/R1-mlir-circt/README.md",
        "gates": {
            "source_access": "true",
            "license": "true",
            "reproducible_minimal_build": "false",
            "model_path": "false",
            "no_required_closed_ip": "true",
            "complete_rtl": "false",
            "test_budget": "true",
            "deterministic_reference": "true",
        },
        "gate_evidence": {
            "source_access": "survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB",
            "license": "survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB",
            "reproducible_minimal_build": "survey/compatibility/R1-mlir-circt/stderr.log#lines=51-64",
            "model_path": "survey/compatibility/R1-mlir-circt/README.md#lines=12-16",
            "no_required_closed_ip": "survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB",
            "complete_rtl": "survey/compatibility/R1-mlir-circt/manifest.json#field=actual_stage=RTL_GENERATION",
            "test_budget": "survey/compatibility/R1-mlir-circt/README.md#lines=9-16",
            "deterministic_reference": "survey/config/scope.yaml#key=fixtures.M3-repository-fixture",
        },
        "scores": {
            "demonstrator_score_0_5": 2,
            "foss_score_0_5": 2,
            "end_to_end_score_0_5": 0,
            "reuse_score_0_5": 3,
            "verification_score_0_5": 2,
            "hardware_score_0_5": 0,
            "performance_score_0_5": 0,
        },
        "score_evidence": {
            "demonstrator_score_0_5": "survey/compatibility/R1-mlir-circt/stdout.log#lines=16-20",
            "foss_score_0_5": "survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB",
            "reuse_score_0_5": "docs/pipeline-contract.md#lines=32-50",
            "verification_score_0_5": "survey/compatibility/R1-mlir-circt/stderr.log#lines=10-27",
        },
        "notes": "Capture and Linalg are evidenced, but R1 stops at RTL_GENERATION/F_SOURCE_MISSING; it is the next evidence-gathering route, not a primary. FOSS is capped at 2 because no qualifying open frontend+synthesis+implementation reproduction exists.",
    },
    {
        "route_id": "R2",
        "route_title": "FlightLLM parameterized RTL artifact",
        "route_family": "PARAMETERIZED_RTL",
        "receipt_manifest": "survey/compatibility/R2-parameterized-rtl/manifest.json",
        "receipt_readme": "survey/compatibility/R2-parameterized-rtl/README.md",
        "gates": {
            "source_access": "false",
            "license": "false",
            "reproducible_minimal_build": "false",
            "model_path": "true",
            "no_required_closed_ip": "false",
            "complete_rtl": "false",
            "test_budget": "false",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": {
            "source_access": "survey/compatibility/R2-parameterized-rtl/README.md#lines=1-16",
            "license": "survey/compatibility/R2-parameterized-rtl/README.md#lines=12-14",
            "reproducible_minimal_build": "survey/compatibility/R2-parameterized-rtl/README.md#lines=12-14",
            "model_path": "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43",
            "no_required_closed_ip": "survey/compatibility/R2-parameterized-rtl/README.md#lines=12-14",
            "complete_rtl": "survey/compatibility/R2-parameterized-rtl/README.md#lines=12-14",
            "test_budget": "survey/compatibility/R2-parameterized-rtl/manifest.json#field=actual_stage=SOURCE_CLOSURE",
            "deterministic_reference": "survey/compatibility/R2-parameterized-rtl/manifest.json#field=actual_stage=SOURCE_CLOSURE",
        },
        "scores": {
            "demonstrator_score_0_5": 2,
            "foss_score_0_5": 0,
            "end_to_end_score_0_5": 2,
            "reuse_score_0_5": 1,
            "verification_score_0_5": 0,
            "hardware_score_0_5": 2,
            "performance_score_0_5": 2,
        },
        "score_evidence": {
            "demonstrator_score_0_5": "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43",
            "end_to_end_score_0_5": "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43",
            "reuse_score_0_5": "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43",
            "hardware_score_0_5": "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43",
            "performance_score_0_5": "survey/build/deep_review.csv#project_family_id=PF-7FF210B343FEAC43",
        },
        "notes": "Published claims are bounded at demonstrator 2 because no complete minimal model was reproduced; proprietary RTL and an untestable closed source closure override selection.",
    },
    {
        "route_id": "R3",
        "route_title": "Mase compiler route",
        "route_family": "DATAFLOW",
        "receipt_manifest": "survey/compatibility/R3-mase/manifest.json",
        "receipt_readme": "survey/compatibility/R3-mase/README.md",
        "gates": {
            "source_access": "false",
            "license": "not_assessed",
            "reproducible_minimal_build": "not_assessed",
            "model_path": "not_assessed",
            "no_required_closed_ip": "not_assessed",
            "complete_rtl": "not_assessed",
            "test_budget": "not_assessed",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": _gate_evidence("survey/compatibility/R3-mase/manifest.json#field=actual_stage=SOURCE_PIN"),
        "scores": {criterion: 0 for criterion in SCORE_WEIGHTS},
        "score_evidence": {},
        "notes": "No paper-attributed immutable Mase artifact was available for route evaluation.",
    },
    {
        "route_id": "R4",
        "route_title": "Allo MLIR/HLS route",
        "route_family": "HLS",
        "receipt_manifest": "survey/compatibility/R4-mlir-hls/manifest.json",
        "receipt_readme": "survey/compatibility/R4-mlir-hls/README.md",
        "gates": {
            "source_access": "false",
            "license": "true",
            "reproducible_minimal_build": "not_assessed",
            "model_path": "not_assessed",
            "no_required_closed_ip": "not_assessed",
            "complete_rtl": "not_assessed",
            "test_budget": "not_assessed",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": {
            **_gate_evidence("survey/compatibility/R4-mlir-hls/manifest.json#field=actual_stage=SOURCE_CLOSURE"),
            "license": "survey/build/artifact_inventory.csv#project_family_id=PF-86FE8DBFB50CB04C",
        },
        "scores": {
            "demonstrator_score_0_5": 0,
            "foss_score_0_5": 1,
            "end_to_end_score_0_5": 1,
            "reuse_score_0_5": 1,
            "verification_score_0_5": 0,
            "hardware_score_0_5": 1,
            "performance_score_0_5": 1,
        },
        "score_evidence": {
            criterion: "survey/build/deep_review.csv#project_family_id=PF-86FE8DBFB50CB04C"
            for criterion in (
                "foss_score_0_5",
                "end_to_end_score_0_5",
                "reuse_score_0_5",
                "hardware_score_0_5",
                "performance_score_0_5",
            )
        },
        "notes": "Demonstrator is 0: the paper documents a route, but the audited tree is a future-release claim rather than a complete exact-LLM artifact.",
    },
    {
        "route_id": "R5",
        "route_title": "FINN transformer-adjacent route",
        "route_family": "DATAFLOW",
        "receipt_manifest": "survey/compatibility/R5-finn/manifest.json",
        "receipt_readme": "survey/compatibility/R5-finn/README.md",
        "gates": {
            "source_access": "false",
            "license": "not_assessed",
            "reproducible_minimal_build": "not_assessed",
            "model_path": "not_assessed",
            "no_required_closed_ip": "not_assessed",
            "complete_rtl": "not_assessed",
            "test_budget": "not_assessed",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": _gate_evidence("survey/compatibility/R5-finn/manifest.json#field=actual_stage=ARTIFACT_ATTRIBUTION"),
        "scores": {criterion: 0 for criterion in SCORE_WEIGHTS},
        "score_evidence": {},
        "notes": "No exact paper-attributed FINN transformer artifact was available; generic FINN is not substituted.",
    },
    {
        "route_id": "R6",
        "route_title": "hls4ml transformer route",
        "route_family": "HLS",
        "receipt_manifest": "survey/compatibility/R6-hls4ml/manifest.json",
        "receipt_readme": "survey/compatibility/R6-hls4ml/README.md",
        "gates": {
            "source_access": "false",
            "license": "not_assessed",
            "reproducible_minimal_build": "not_assessed",
            "model_path": "false",
            "no_required_closed_ip": "not_assessed",
            "complete_rtl": "not_assessed",
            "test_budget": "not_assessed",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": {
            **_gate_evidence("survey/compatibility/R6-hls4ml/manifest.json#field=actual_stage=ARTIFACT_ATTRIBUTION"),
            "model_path": "survey/build/deep_review.csv#project_family_id=PF-3DBBE522B68ECE13",
        },
        "scores": {
            "demonstrator_score_0_5": 2,
            "foss_score_0_5": 0,
            "end_to_end_score_0_5": 0,
            "reuse_score_0_5": 1,
            "verification_score_0_5": 0,
            "hardware_score_0_5": 3,
            "performance_score_0_5": 2,
        },
        "score_evidence": {
            criterion: "survey/build/deep_review.csv#project_family_id=PF-3DBBE522B68ECE13"
            for criterion in (
                "demonstrator_score_0_5",
                "reuse_score_0_5",
                "hardware_score_0_5",
                "performance_score_0_5",
            )
        },
        "notes": "The inspected work is a non-causal physics transformer and has no attributed project artifact.",
    },
    {
        "route_id": "R7",
        "route_title": "open reusable accelerator control",
        "route_family": "PARAMETERIZED_RTL",
        "receipt_manifest": "survey/compatibility/R7-open-accelerator/manifest.json",
        "receipt_readme": "survey/compatibility/R7-open-accelerator/README.md",
        "gates": {
            "source_access": "false",
            "license": "true",
            "reproducible_minimal_build": "not_assessed",
            "model_path": "not_assessed",
            "no_required_closed_ip": "not_assessed",
            "complete_rtl": "not_assessed",
            "test_budget": "not_assessed",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": {
            **_gate_evidence("survey/compatibility/R7-open-accelerator/manifest.json#field=actual_stage=SOURCE_CLOSURE"),
            "license": "survey/build/artifact_inventory.csv#project_family_id=PF-4EBDD47F47E94583",
        },
        "scores": {
            "demonstrator_score_0_5": 3,
            "foss_score_0_5": 3,
            "end_to_end_score_0_5": 0,
            "reuse_score_0_5": 2,
            "verification_score_0_5": 1,
            "hardware_score_0_5": 2,
            "performance_score_0_5": 2,
        },
        "score_evidence": {
            criterion: "survey/build/deep_review.csv#project_family_id=PF-4EBDD47F47E94583"
            for criterion in SCORE_WEIGHTS
            if criterion != "end_to_end_score_0_5"
        },
        "notes": "The final receipt stops at SOURCE_CLOSURE because ElasticAI.Creator is mutable and VHDL templates remain unrendered; model path is intentionally not claimed.",
    },
    {
        "route_id": "R8",
        "route_title": "Cascade CPU/FPGA fallback control",
        "route_family": "CPU_FPGA_FALLBACK",
        "receipt_manifest": "survey/compatibility/R8-cpu-fpga-fallback/manifest.json",
        "receipt_readme": "survey/compatibility/R8-cpu-fpga-fallback/README.md",
        "gates": {
            "source_access": "false",
            "license": "not_assessed",
            "reproducible_minimal_build": "not_assessed",
            "model_path": "not_assessed",
            "no_required_closed_ip": "not_assessed",
            "complete_rtl": "not_assessed",
            "test_budget": "not_assessed",
            "deterministic_reference": "not_assessed",
        },
        "gate_evidence": _gate_evidence("survey/compatibility/R8-cpu-fpga-fallback/manifest.json#field=actual_stage=SOURCE_CLOSURE"),
        "scores": {
            "demonstrator_score_0_5": 1,
            "foss_score_0_5": 2,
            "end_to_end_score_0_5": 0,
            "reuse_score_0_5": 1,
            "verification_score_0_5": 0,
            "hardware_score_0_5": 2,
            "performance_score_0_5": 0,
        },
        "score_evidence": {
            criterion: "survey/build/deep_review.csv#project_family_id=PF-E9C1300B04E80B95"
            for criterion in (
                "demonstrator_score_0_5",
                "foss_score_0_5",
                "reuse_score_0_5",
                "hardware_score_0_5",
            )
        },
        "notes": "The final receipt stops at SOURCE_CLOSURE on the absent generated QIP hierarchy; causal-LM model-path claims are intentionally not retained.",
    },
)

_ROUTE_ASSESSMENT_BY_ID = {
    str(assessment["route_id"]): assessment for assessment in _ROUTE_ASSESSMENTS
}


def _nonblank(value: object) -> bool:
    return value is not None and not pd.isna(value) and bool(str(value).strip())


_LINE_LOCATOR = re.compile(r"lines=(?P<start>[1-9][0-9]*)-(?P<end>[1-9][0-9]*)$")
_COMMAND_LOCATOR = re.compile(r"command-(?P<ordinal>[1-9][0-9]*)$")
_CSV_LOCATOR = re.compile(r"(?P<field>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.+)$")
TEXT_EVIDENCE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".log",
        ".md",
        ".mlir",
        ".nix",
        ".org",
        ".py",
        ".rst",
        ".sh",
        ".sv",
        ".tcl",
        ".txt",
        ".v",
    }
)


def _nested_key_exists(payload: object, dotted_key: str) -> bool:
    current = payload
    for component in dotted_key.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return False
        current = current[component]
    return True


def _validate_evidence_locator(path: Path, locator: str) -> None:
    """Validate a portable, typed locator against its checked-in evidence file."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        match = _CSV_LOCATOR.fullmatch(locator)
        if match is None:
            raise ValueError("CSV evidence requires a column=value locator")
        with path.open(newline="", encoding="utf-8") as source:
            rows = csv.DictReader(source)
            if rows.fieldnames is None or match["field"] not in rows.fieldnames:
                raise ValueError("CSV locator names no available column")
            if any(row.get(match["field"]) == match["value"] for row in rows):
                return
        raise ValueError("CSV locator matches no row")
    if suffix in {".yaml", ".yml"}:
        if not locator.startswith("key=") or not _nested_key_exists(
            yaml.safe_load(path.read_text(encoding="utf-8")), locator.removeprefix("key=")
        ):
            raise ValueError("YAML evidence requires an existing key=<dotted-path> locator")
        return
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if command_match := _COMMAND_LOCATOR.fullmatch(locator):
            ordinal = int(command_match["ordinal"])
            command_results = (
                payload.get("command_results") if isinstance(payload, Mapping) else None
            )
            executed_commands = (
                payload.get("executed_commands") if isinstance(payload, Mapping) else None
            )
            if isinstance(command_results, list) and any(
                isinstance(result, Mapping) and result.get("index") == ordinal
                for result in command_results
            ):
                return
            if isinstance(executed_commands, list) and ordinal <= len(executed_commands):
                return
            raise ValueError("command locator does not identify a recorded command")
        if not locator.startswith("field="):
            raise ValueError("JSON evidence requires field=<key>=<value> or command-N")
        field_and_value = locator.removeprefix("field=").split("=", 1)
        if len(field_and_value) != 2:
            raise ValueError("JSON field locator must include an expected value")
        field, expected = field_and_value
        if not isinstance(payload, Mapping) or str(payload.get(field)) != expected:
            raise ValueError("JSON field locator does not match the recorded value")
        return
    if suffix not in TEXT_EVIDENCE_SUFFIXES:
        raise ValueError(
            "evidence file is not a supported structured or text-like source"
        )
    if match := _LINE_LOCATOR.fullmatch(locator):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        start = int(match["start"])
        end = int(match["end"])
        if start <= end <= line_count:
            return
        raise ValueError("line range is outside the evidence file")
    raise ValueError("text evidence requires a lines=<start>-<end> locator")


def _evidence_source_paths(
    evidence_location: object, root: Path = ROOT
) -> tuple[Path, ...]:
    """Resolve and validate semicolon-separated portable evidence pointers."""

    if not _nonblank(evidence_location):
        return ()
    paths: list[Path] = []
    resolved_root = root.resolve()
    for reference in str(evidence_location).split(";"):
        location, separator, locator = reference.strip().partition("#")
        if not location or not separator or not locator:
            raise ValueError(f"invalid evidence locator: {reference!r}")
        location_path = Path(location)
        if location_path.is_absolute():
            raise ValueError(
                "evidence path must be relative to and remain within the repository"
            )
        path = (resolved_root / location_path).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError as error:
            raise ValueError(
                "evidence path must be relative to and remain within the repository"
            ) from error
        if path.is_file():
            try:
                _validate_evidence_locator(path, locator)
            except ValueError as error:
                raise ValueError(
                    f"invalid evidence locator {reference!r}: {error}"
                ) from error
        paths.append(path)
    return tuple(paths)


def _load_scope_contract(root: Path) -> None:
    """Reject accidental drift from the frozen hard-gate and weighting contract."""

    scope = yaml.safe_load((root / SCOPE_PATH).read_text(encoding="utf-8"))
    if not isinstance(scope, dict):
        raise ValueError("scope.yaml must contain a mapping")
    gates = scope.get("hard_eligibility_gates")
    if not isinstance(gates, dict) or tuple(gates) != HARD_GATES:
        raise ValueError("scope hard eligibility gates do not match Task 7")
    decision_matrix = scope.get("decision_matrix")
    if not isinstance(decision_matrix, dict):
        raise ValueError("scope decision_matrix is missing")
    weights = decision_matrix.get("weights")
    if weights != SCORE_WEIGHTS:
        raise ValueError("scope decision-matrix weights do not match Task 7")


def validate_stage_matrix(matrix: pd.DataFrame, root: Path = ROOT) -> None:
    """Validate every project's canonical stage coverage and evidence bounds."""

    if tuple(matrix.columns) != STAGE_COLUMNS:
        raise ValueError("stage matrix columns do not match the Task 7 schema")
    catalog = _load_canonical_stage_catalog(root)
    expected_ordinals = [stage["ordinal"] for stage in catalog]
    expected_names = [stage["name"] for stage in catalog]
    observed_projects = set(matrix["project"])
    required_projects = set(PROJECTS)
    if observed_projects != required_projects:
        raise ValueError(
            "stage matrix project set must be exactly the audited projects: "
            f"expected {sorted(required_projects)}, observed {sorted(observed_projects)}"
        )
    if len(matrix) != len(PROJECTS) * len(catalog):
        raise ValueError(
            f"stage matrix must contain exactly {len(PROJECTS)} × {len(catalog)} rows"
        )
    for project, project_rows in matrix.groupby("project", sort=False):
        if len(project_rows) != len(catalog):
            raise ValueError(
                f"project {project} must contain the canonical {len(catalog)} transformations"
            )
        if project_rows["ordinal"].tolist() != expected_ordinals:
            raise ValueError(f"project {project} ordinals do not match the canonical catalog")
        if project_rows["stage"].tolist() != expected_names:
            raise ValueError(f"project {project} stages do not match the canonical catalog")
    if not bool(matrix["status"].isin(STAGE_STATUSES).all()):
        invalid = sorted(set(matrix["status"]) - STAGE_STATUSES)
        raise ValueError(f"unsupported stage status values: {invalid}")
    for row in matrix.to_dict(orient="records"):
        status = str(row["status"])
        evidence = row["evidence_location"]
        kind = str(row["evidence_kind"])
        if status != "missing" and not _nonblank(evidence):
            raise ValueError(
                f"{row['stage']} has status {status} without evidence_location"
            )
        if _nonblank(evidence) and not all(
            path.is_file() for path in _evidence_source_paths(evidence, root)
        ):
            raise ValueError(
                f"{row['stage']} evidence_location does not resolve to a local source"
            )
        if status == "native" and kind not in NATIVE_EVIDENCE_KINDS:
            raise ValueError(
                f"native stage {row['stage']} requires a pinned source test or example"
            )


def build_stage_matrix(root: Path = ROOT) -> pd.DataFrame:
    """Return canonical 20-stage assessments for all audited projects."""

    _load_canonical_stage_catalog(root)
    rows = (*_COMPILER_LAB_STAGE_ROWS, *_external_stage_rows(root))
    matrix = pd.DataFrame(rows, columns=STAGE_COLUMNS)
    validate_stage_matrix(matrix, root)
    return matrix


def stage_status(project: str, stage: str, root: Path = ROOT) -> StageStatus:
    """Return the evidence-qualified implementation status for one stage."""

    matrix = build_stage_matrix(root)
    row = matrix.loc[(matrix["project"] == project) & (matrix["stage"] == stage)]
    if len(row) != 1:
        raise KeyError(f"unknown project/stage pair: {project!r}, {stage!r}")
    return cast(StageStatus, row.iloc[0]["status"])


def _score_value(row: Mapping[str, object], criterion: str) -> float:
    if criterion not in row:
        raise ValueError(f"missing score column: {criterion}")
    value = row[criterion]
    if isinstance(value, bool):
        raise ValueError(f"{criterion} must be numeric, not Boolean")
    try:
        score = float(cast(str | int | float, value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{criterion} must be numeric") from error
    if not 0 <= score <= 5:
        raise ValueError(f"{criterion} must be in the inclusive range 0..5")
    if score > 0:
        evidence_column = f"{criterion}_evidence"
        if not _nonblank(row.get(evidence_column)):
            raise ValueError(
                f"positive {criterion} requires {evidence_column}"
            )
    return score


def score_route(row: Mapping[str, object]) -> float:
    """Return the exact frozen 0--100 weighted score for one route."""

    total = sum(
        _score_value(row, criterion) / 5 * weight
        for criterion, weight in SCORE_WEIGHTS.items()
    )
    return round(total, 6)


def _gate_is_true(value: object, gate: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized in {"false", "not_assessed", "", "nan", "none"}:
        return False
    raise ValueError(f"{gate} must be true, false, or not_assessed")


def hard_gates_pass(row: Mapping[str, object]) -> bool:
    """Return true only when all eight frozen hard gates are explicitly true."""

    missing = [gate for gate in HARD_GATES if gate not in row]
    if missing:
        raise ValueError(f"route is missing hard gates: {', '.join(missing)}")
    return all(_gate_is_true(row[gate], gate) for gate in HARD_GATES)


def _first_failed_gate_in_protocol_order(row: Mapping[str, object]) -> str:
    """Return the first false gate in the frozen declaration order.

    ``first_failed_gate`` is deliberately not an observed compatibility-stage
    label.  The receipt's ``actual_stage`` remains that observed stage; this
    field is the deterministic first failed item in ``HARD_GATES``.
    """

    for gate in HARD_GATES:
        if not _gate_is_true(row[gate], gate):
            return gate
    return ""


def _require_local_evidence(
    evidence_location: object, root: Path, label: str
) -> None:
    try:
        paths = _evidence_source_paths(evidence_location, root)
    except ValueError as error:
        raise ValueError(f"{label}: {error}") from error
    if not paths or not all(path.is_file() for path in paths):
        raise ValueError(f"{label} does not resolve to local evidence")


def validate_decision_matrix(matrix: pd.DataFrame, root: Path = ROOT) -> None:
    """Validate gate provenance, scoring anchors, and eligibility-derived fields."""

    if tuple(matrix.columns) != DECISION_COLUMNS:
        raise ValueError("decision matrix columns do not match the Task 7 schema")
    for row in matrix.to_dict(orient="records"):
        route_id = str(row["route_id"])
        if not _nonblank(route_id):
            raise ValueError("decision matrix route_id must be nonblank")
        assessment = _ROUTE_ASSESSMENT_BY_ID.get(route_id)
        if assessment is None:
            raise ValueError(f"decision matrix contains an unknown route: {route_id}")
        expected_gates = cast(Mapping[str, object], assessment["gates"])
        expected_gate_evidence = cast(
            Mapping[str, object], assessment["gate_evidence"]
        )
        if row["first_failed_gate_semantics"] != FIRST_FAILED_GATE_SEMANTICS:
            raise ValueError("first_failed_gate semantics must be protocol_order")
        expected_first_failure = _first_failed_gate_in_protocol_order(row)
        if row["first_failed_gate"] != expected_first_failure:
            raise ValueError(
                f"first_failed_gate for {route_id} must be {expected_first_failure!r} "
                "under protocol order"
            )
        for gate in HARD_GATES:
            if str(row[gate]).strip().lower() != str(expected_gates[gate]).strip().lower():
                raise ValueError(f"gate value for {route_id}/{gate} is inconsistent")
            if row[f"{gate}_evidence"] != expected_gate_evidence[gate]:
                raise ValueError(f"gate evidence for {route_id}/{gate} is inconsistent")
            _gate_is_true(row[gate], gate)
            _require_local_evidence(
                row[f"{gate}_evidence"], root, f"gate evidence for {route_id}/{gate}"
            )
        for criterion in SCORE_WEIGHTS:
            score = _score_value(row, criterion)
            if score > 0:
                _require_local_evidence(
                    row[f"{criterion}_evidence"],
                    root,
                    f"score evidence for {route_id}/{criterion}",
                )
            ceiling = SCORE_ANCHOR_CEILINGS.get((route_id, criterion))
            if ceiling is not None and score > ceiling:
                raise ValueError(
                    f"score anchor for {route_id}/{criterion} permits at most {ceiling}"
                )
        expected_total = score_route(row)
        try:
            actual_total = float(cast(str | int | float, row["weighted_total"]))
        except (TypeError, ValueError) as error:
            raise ValueError(f"weighted_total for {route_id} must be numeric") from error
        if actual_total != expected_total:
            raise ValueError(f"weighted_total for {route_id} does not match frozen weights")
        eligible = hard_gates_pass(row)
        expected_status = "ELIGIBLE" if eligible else "INELIGIBLE"
        if row["selection_status"] != expected_status:
            raise ValueError(f"selection_status for {route_id} does not match hard gates")
        if eligible:
            try:
                effective_total = float(cast(str | int | float, row["effective_total"]))
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"effective_total for eligible {route_id} must be numeric"
                ) from error
            if effective_total != expected_total:
                raise ValueError(
                    f"effective_total for eligible {route_id} does not match weighted_total"
                )
        elif _nonblank(row["effective_total"]):
            raise ValueError(f"ineligible {route_id} must have a blank effective_total")


def choose_routes(routes: pd.DataFrame) -> tuple[str, str]:
    """Choose a gate-passing primary and distinct-family gate-passing fallback.

    A score cannot rescue an ineligible route.  In particular, callers must
    handle ``NO_PRIMARY_ROUTE_PASSED`` instead of selecting the highest score
    from an ineligible matrix.
    """

    required = {"route_id", "route_family", *HARD_GATES, *SCORE_WEIGHTS}
    missing = sorted(required - set(routes.columns))
    if missing:
        raise ValueError(f"routes are missing required columns: {missing}")
    assessed: list[dict[str, object]] = []
    for row in routes.to_dict(orient="records"):
        if not _nonblank(row.get("route_id")) or not _nonblank(row.get("route_family")):
            raise ValueError("every route needs route_id and route_family")
        assessed.append(
            {
                **row,
                "weighted_total": score_route(row),
                "eligible": hard_gates_pass(row),
            }
        )
    eligible = [row for row in assessed if bool(row["eligible"])]
    if not eligible:
        raise ValueError("NO_PRIMARY_ROUTE_PASSED")
    eligible.sort(key=lambda row: (-float(row["weighted_total"]), str(row["route_id"])))
    primary = eligible[0]
    fallback = next(
        (
            row
            for row in eligible[1:]
            if row["route_family"] != primary["route_family"]
        ),
        None,
    )
    if fallback is None:
        raise ValueError("NO_DISTINCT_FAMILY_FALLBACK_PASSED")
    return str(primary["route_id"]), str(fallback["route_id"])


def _read_manifest(root: Path, relative_path: str) -> dict[str, object]:
    manifest_path = root / relative_path
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"receipt manifest is not an object: {relative_path}")
    return payload


def _validate_route_assessment(assessment: Mapping[str, object], manifest: Mapping[str, object]) -> None:
    route_id = str(assessment["route_id"])
    if manifest.get("route_id") != route_id:
        raise ValueError(f"receipt route_id mismatch for {route_id}")
    if manifest.get("route_family") != assessment["route_family"]:
        raise ValueError(f"receipt route_family mismatch for {route_id}")
    if route_id == "R1" and (
        manifest.get("actual_stage"), manifest.get("failure_code")
    ) != ("RTL_GENERATION", "F_SOURCE_MISSING"):
        raise ValueError("R1 must use its final RTL_GENERATION/F_SOURCE_MISSING receipt")
    if route_id in {"R7", "R8"} and (
        manifest.get("actual_stage"), manifest.get("failure_code")
    ) != ("SOURCE_CLOSURE", "F_SOURCE_MISSING"):
        raise ValueError(
            f"{route_id} must use its final SOURCE_CLOSURE/F_SOURCE_MISSING receipt"
        )


def build_decision_matrix(root: Path = ROOT) -> pd.DataFrame:
    """Return the eight route rows with final Task 6 receipt provenance."""

    _load_scope_contract(root)
    rows: list[dict[str, object]] = []
    for assessment in _ROUTE_ASSESSMENTS:
        manifest = _read_manifest(root, str(assessment["receipt_manifest"]))
        _validate_route_assessment(assessment, manifest)
        gates = cast(Mapping[str, object], assessment["gates"])
        gate_evidence = cast(Mapping[str, str], assessment["gate_evidence"])
        scores = cast(Mapping[str, object], assessment["scores"])
        score_evidence = cast(Mapping[str, str], assessment["score_evidence"])
        row: dict[str, object] = {
            "route_id": assessment["route_id"],
            "route_title": assessment["route_title"],
            "route_family": assessment["route_family"],
            "receipt_manifest": assessment["receipt_manifest"],
            "receipt_readme": assessment["receipt_readme"],
            "actual_stage": manifest["actual_stage"],
            "failure_code": manifest["failure_code"],
            "first_failed_gate": _first_failed_gate_in_protocol_order(gates),
            "first_failed_gate_semantics": FIRST_FAILED_GATE_SEMANTICS,
            **{gate: gates[gate] for gate in HARD_GATES},
            **{
                f"{gate}_evidence": gate_evidence[gate]
                for gate in HARD_GATES
            },
            **{criterion: scores[criterion] for criterion in SCORE_WEIGHTS},
            **{
                f"{criterion}_evidence": score_evidence.get(criterion, "")
                for criterion in SCORE_WEIGHTS
            },
            "notes": assessment["notes"],
        }
        row["weighted_total"] = score_route(row)
        eligible = hard_gates_pass(row)
        row["effective_total"] = row["weighted_total"] if eligible else ""
        row["selection_status"] = "ELIGIBLE" if eligible else "INELIGIBLE"
        rows.append(row)
    matrix = pd.DataFrame(rows, columns=DECISION_COLUMNS)
    if matrix["route_id"].tolist() != [f"R{number}" for number in range(1, 9)]:
        raise ValueError("decision matrix must retain exactly R1 through R8")
    validate_decision_matrix(matrix, root)
    return matrix


def render_stage_markdown(matrix: pd.DataFrame, root: Path = ROOT) -> str:
    """Render the D11 matrix and conservative H1--H3 conclusions."""

    validate_stage_matrix(matrix, root)
    catalog = _load_canonical_stage_catalog(root)
    provenance = json.loads((root / CANONICAL_STAGE_CATALOG_PATH).read_text(encoding="utf-8"))["source_provenance"]
    lines = [
        "# D11 MLIR/CIRCT stage matrix",
        "",
        "## Canonical catalog, correction, and portable provenance",
        "",
        f"The tracked [`{CANONICAL_STAGE_CATALOG_PATH.as_posix()}`](../data/mlir_circt_stage_catalog.json) transcribes the supplied protocol's exact ordered 20 transformations, including **Weight-loading interface** between **Backpressure and deadlock handling** and **AXI/stream/memory interface generation**. Its provenance records source file `{provenance['source_filename']}`, SHA-256 `{provenance['source_sha256']}`, and lines `{provenance['source_line_range']}`. The original source was supplied outside this repository, so its absolute path is intentionally omitted.",
        "",
        "The frozen in-worktree [`survey/protocol.md`](../protocol.md) prose omits that row; this tracked catalog and D11 output are a source-faithful correction only, and the frozen protocol file was not modified or rehashed.",
        "",
        f"Per the protocol, the matrix is constructed for each audited project. This output fixes the audited project set to {', '.join(PROJECTS)} and contains {len(matrix)} assessment rows: {matrix['project'].nunique()} projects × {len(catalog)} canonical transformations.",
        "",
        "`native` requires a pinned source test or example. `extension_available` requires a bounded, concrete local extension. `manual_implementation` requires a documented implementation boundary. `missing` can retain negative audit evidence, but makes no stage claim.",
        "",
        "Evidence pointers are checked-in, repository-relative, portable locators and must resolve within the repository. Locator grammar is selected by suffix: text-like files use `#lines=start-end`, YAML uses `#key=dotted.path`, CSV uses `#column=value`, JSON uses `#field=key=value`, and receipts may use `#command-N`. The generator validates the referenced range, key, row, field value, or recorded command.",
    ]
    for project, project_rows in matrix.groupby("project", sort=False):
        lines.extend(
            [
                "",
                f"## Project: {project}",
                "",
                "| # | Transformation | Status | Evidence kind | Concrete evidence | Bounded assessment |",
                "| ---: | --- | --- | --- | --- | --- |",
            ]
        )
        for row in project_rows.to_dict(orient="records"):
            def cell(value: object) -> str:
                return str(value).replace("|", "\\|").replace("\n", " ")

            lines.append(
                "| {ordinal} | {stage} | {status} | {kind} | {evidence} | {rationale} |".format(
                    ordinal=cell(row["ordinal"]),
                    stage=cell(row["stage"]),
                    status=cell(row["status"]),
                    kind=cell(row["evidence_kind"]),
                    evidence=cell(row["evidence_location"]) or "—",
                    rationale=cell(row["rationale"]),
                )
            )
    lines.extend(
        [
            "",
            "## H1-H3 bounded conclusions",
            "",
            "- **H1 — unsupported for the current route.** R1's final Task 6 receipt records `RTL_GENERATION/F_SOURCE_MISSING`, even though capture and Linalg artifacts were built. Separately, the fixed RC nonlinear report records `math.exp` rejected before a valid Calyx artifact. Therefore this matrix does not claim an M0, M1, M2, or M3 pass. Evidence: `survey/compatibility/R1-mlir-circt/README.md#lines=1-16`; `docs/results/2026-07-16-quantized-rc-nonlinear-lowering-frontier.md#lines=23-45`.",
            "- **H2 — bounded/partial support only.** Torch-MLIR capture and a narrow quantization compatibility pass are reusable local components. Declared bufferization wiring, static-fixture references, and scalar nonlinear ingredients do not establish exercised tensor-to-buffer, shape-specialisation, Softmax, GELU, or SiLU transformations. Evidence: `scripts/compile-pytorch.py#lines=13-69`; `scripts/pipeline/linalg_to_scf_no_handshake.sh#lines=18-28`; `tools/mlir-passes/LegalizePt2eTosaZeroPoint.cpp#lines=65-160`.",
            "- **H3 — inconclusive.** No final receipt combines MLIR orchestration with a parameterized causal-LM backend that passes the hard gates or simulation. Allo's exact LLM artifact remains a future-release claim; Olympus is a non-LLM MLIR system generator with no attributed project artifact; R2 is source-closed; and R7/R8 stop at `SOURCE_CLOSURE/F_SOURCE_MISSING`. This is a hypothesis for separate evidence gathering, not a selected hybrid route. Evidence: `survey/compatibility/R4-mlir-hls/README.md#lines=1-16`; `survey/build/deep_review.csv#project_family_id=PF-5423EA8E2FD4952E`; `survey/compatibility/R2-parameterized-rtl/README.md#lines=1-16`; `survey/compatibility/R7-open-accelerator/README.md#lines=1-16`; `survey/compatibility/R8-cpu-fpga-fallback/README.md#lines=1-16`.",
            "",
        ]
    )
    return "\n".join(lines)


def _route_selection_markdown(matrix: pd.DataFrame) -> str:
    """Render selection output, explicitly handling an all-ineligible matrix."""

    try:
        primary, fallback = choose_routes(matrix)
    except ValueError as error:
        if str(error) != "NO_PRIMARY_ROUTE_PASSED":
            raise
        r1 = matrix.loc[matrix["route_id"].eq("R1")].iloc[0]
        r2 = matrix.loc[matrix["route_id"].eq("R2")].iloc[0]
        return "\n".join(
            [
                "# Route selection",
                "",
                "- Status: `NO_PRIMARY_ROUTE_PASSED`",
                "- Primary route: ``",
                "",
                "Every R1-R8 candidate fails at least one hard gate. Weighted totals remain visible in `decision_matrix_scored.csv` for evidence prioritisation only; none overrides eligibility.",
                "",
                "`first_failed_gate` in the scored CSV means the first false gate in the frozen protocol order; it is distinct from the receipt's observed `actual_stage`.",
                "",
                "## Next evidence-gathering route (not selected primary)",
                "",
                f"- Next evidence-gathering route: `{r1['route_id']}` ({r1['route_family']})",
                f"- Current eligibility: `{r1['selection_status']}`; final receipt `{r1['actual_stage']}/{r1['failure_code']}`.",
                "- Bounded action: restore the committed native-SV helper, regenerate RTL, then rerun independent lint and synthesis before any M0-M3 claim.",
                "",
                "## Different-family fallback hypothesis (also not selected)",
                "",
                f"- Fallback hypothesis: `{r2['route_id']}` ({r2['route_family']})",
                f"- Current eligibility: `{r2['selection_status']}` — ineligible because its final receipt is `{r2['actual_stage']}/{r2['failure_code']}` and the RTL is proprietary.",
                "- This is a different-family research hypothesis only; it is not a fallback route selection and cannot become one without redistributable RTL and new hard-gate evidence.",
                "",
            ]
        )
    return "\n".join(
        [
            "# Route selection",
            "",
            "- Status: `PRIMARY_ROUTE_PASSED`",
            f"- Primary route: `{primary}`",
            f"- Different-family fallback: `{fallback}`",
            "",
        ]
    )


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)


def write_decision_template(path: Path) -> None:
    """Write a blank scored-decision template retaining frozen route identities."""

    template_rows = []
    for assessment in _ROUTE_ASSESSMENTS:
        row = {column: "" for column in DECISION_COLUMNS}
        row.update(
            {
                "route_id": assessment["route_id"],
                "route_title": assessment["route_title"],
                "route_family": assessment["route_family"],
                "receipt_manifest": assessment["receipt_manifest"],
                "receipt_readme": assessment["receipt_readme"],
            }
        )
        template_rows.append(row)
    frame = pd.DataFrame(template_rows, columns=DECISION_COLUMNS)
    _write_csv(frame, path)


def write_outputs(root: Path, out: Path) -> None:
    """Write D11 matrix, scored routes, and no-primary-aware selection report."""

    stage_matrix = build_stage_matrix(root)
    decision_matrix = build_decision_matrix(root)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(stage_matrix, out / "mlir_circt_stage_matrix.csv")
    (out / "mlir_circt_stage_matrix.md").write_text(
        render_stage_markdown(stage_matrix, root), encoding="utf-8"
    )
    _write_csv(decision_matrix, out / "decision_matrix_scored.csv")
    (out / "route_selection.md").write_text(
        _route_selection_markdown(decision_matrix), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the MLIR/CIRCT stage matrix and eligibility-first route decision."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "survey/build",
        help="directory for generated D11 and decision outputs",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=ROOT / "survey/templates/decision_matrix.csv",
        help="decision-matrix template path",
    )
    args = parser.parse_args()
    write_outputs(ROOT, args.out)
    write_decision_template(args.template)


if __name__ == "__main__":
    main()
