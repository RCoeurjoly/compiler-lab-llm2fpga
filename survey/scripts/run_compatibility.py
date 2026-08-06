#!/usr/bin/env python3
"""Generate and validate evidence receipts for the frozen compatibility routes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "survey/protocol.md"
ARTIFACT_INVENTORY = ROOT / "survey/build/artifact_inventory.csv"
REPOSITORY_AUDIT = ROOT / "survey/build/repository_audit.csv"
DEEP_REVIEW = ROOT / "survey/build/deep_review.csv"

ALLOWED_FAILURE_CODES = frozenset(
    {
        "NONE",
        "F_ENV",
        "F_SOURCE_MISSING",
        "F_LICENSE",
        "F_FRONTEND",
        "F_TYPE",
        "F_LOWERING",
        "F_SCHEDULE",
        "F_CONTROL",
        "F_MEMORY",
        "F_STATE",
        "F_RTL",
        "F_VENDOR_IP",
        "F_SYNTH_RESOURCE",
        "F_TIMING",
        "F_NUMERIC",
        "F_INTERFACE",
    }
)

FIXTURES: dict[str, dict[str, Any]] = {
    "M0-operators": {
        "batch_size": 1,
        "static_shapes": True,
        "operators": [
            "int8_matmul",
            "normalization",
            "activation",
            "rope",
            "causal_softmax",
            "kv_read_write",
        ],
        "acceptance": {
            "integer": "identical",
            "fixed_point_lsb": 1,
            "floating_absolute": 1e-5,
            "floating_relative": 1e-4,
        },
    },
    "M1-block": {
        "blocks": 1,
        "d_model": 64,
        "heads": 4,
        "d_ff": 128,
        "sequence": 16,
        "batch_size": 1,
        "acceptance": {
            "integer": "identical",
            "fixed_point_lsb": 1,
            "floating_absolute": 1e-5,
            "floating_relative": 1e-4,
        },
    },
    "M2-tiny-lm": {
        "blocks": 2,
        "d_model": 128,
        "heads": 4,
        "d_ff": 256,
        "vocabulary": 256,
        "max_sequence": 32,
        "batch_size": 1,
        "decode_tokens": 4,
        "decode_mode": "greedy",
        "kv_state": "persistent_across_decode_steps",
        "acceptance": {"token_ids": "identical"},
    },
    "M3-repository-fixture": {
        "batch_size": 1,
        "fixture": "compiler-lab TinyStories frozen repository fixture",
        "acceptance": {
            "integer": "identical",
            "reference": "frozen PT2E W8A8 evaluator",
        },
    },
}


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    slug: str
    title: str
    route_family: str
    expected_stage: str
    source_evidence: str
    source_commit: str = ""
    source_sha256: str = ""
    artifact_commit: str = ""
    artifact_sha256: str = ""
    complete_elaboratable_rtl: bool = False
    bounded_corrective_action: str = ""
    first_gate: str = "SOURCE_PIN"
    first_failure_code: str = "F_SOURCE_MISSING"
    first_failure_detail: str = "No executable source was pinned."
    fixture: str = "M0-operators"


ROUTES: dict[str, RouteSpec] = {
    "R1": RouteSpec(
        "R1",
        "R1-mlir-circt",
        "compiler-lab MLIR/CIRCT control",
        "MLIR_CIRCT",
        "M3_GENERIC_SYNTHESIS",
        "survey/build/repository_audit.csv#repository_audit_id=REPO-CONTROL-COMPILER-LAB",
        source_commit="433592c448f8b19a30dd046a1ec726b09a86d892",
        source_sha256="e1848d79218fad62e2fb8873067ee90bcf370a23e9752cf6c9545aa78d96a872",
        artifact_commit="nix-store-b8pwl1r7jq05hn5pphj4zxyg67c3zxjs",
        artifact_sha256="f0e0f500a44ef2daabecd780d743fee2585a46593c2e3d67a7e6b189fd28f983",
        first_gate="SMOKE_TESTS",
        first_failure_code="F_ENV",
        first_failure_detail=(
            "Capture and Linalg lowering complete, but the focused smoke suite has "
            "a stale patches-directory assertion. Pinned pytest also reaches the "
            "preserved Python 3.11 f-string collection failure."
        ),
        fixture="M3-repository-fixture",
    ),
    "R2": RouteSpec(
        "R2",
        "R2-parameterized-rtl",
        "FlightLLM parameterized RTL artifact",
        "PARAMETERIZED_RTL",
        "M2_STATEFUL_DECODE",
        "survey/build/artifact_inventory.csv#project_family_id=PF-7FF210B343FEAC43",
        source_sha256="efd1d505ecb353f8c7f3e16b75d1fdd43e962cc33ec0160668bbc5ab0921d8f8",
        artifact_commit="zenodo-record-10462167-version-1.0.5",
        artifact_sha256="e33b129691e81eabfe10496d7486bfdb2e6d5977fc1d2f6f4a3fa0cd36270df3",
        first_gate="SOURCE_CLOSURE",
        first_failure_code="F_VENDOR_IP",
        first_failure_detail=(
            "The licensed deposit README says the RTL is proprietary Infinigence-AI "
            "IP and supplies only a pre-generated U280 bitstream, precompiled cases, "
            "and a host file. Independent RTL lint and generic synthesis are impossible."
        ),
    ),
    "R3": RouteSpec(
        "R3",
        "R3-mase",
        "Mase compiler route",
        "DATAFLOW",
        "M1_RTL",
        "survey/build/artifact_inventory.csv (no attributed Mase artifact row)",
        first_gate="SOURCE_PIN",
        first_failure_code="F_SOURCE_MISSING",
        first_failure_detail=(
            "Task 5 contains no paper-attributed, commit-pinned Mase source artifact."
        ),
    ),
    "R4": RouteSpec(
        "R4",
        "R4-mlir-hls",
        "Allo MLIR/HLS route",
        "HLS",
        "M1_RTL",
        "survey/build/repository_audit.csv#repository_audit_id=REPO-PF-86FE8DBFB50CB04C",
        source_commit="74b0373ecbc4cfded24f5660c12eee4253c31be5",
        source_sha256="f9f59fd6e68f950b1333719c872682a188295b5f89a016383509c00b43366608",
        first_gate="SOURCE_CLOSURE",
        first_failure_code="F_SOURCE_MISSING",
        first_failure_detail=(
            "The audit observes the general Allo tree but the paper marks the LLM "
            "artifact as a future release; no complete LLM RTL artifact is pinned."
        ),
    ),
    "R5": RouteSpec(
        "R5",
        "R5-finn",
        "FINN transformer-adjacent route",
        "DATAFLOW",
        "M1_RTL",
        "survey/build/artifact_inventory.csv (no attributed FINN artifact row)",
        first_gate="ARTIFACT_ATTRIBUTION",
        first_failure_code="F_SOURCE_MISSING",
        first_failure_detail=(
            "The frozen deep-review work has no attributed and audited FINN source artifact."
        ),
    ),
    "R6": RouteSpec(
        "R6",
        "R6-hls4ml",
        "hls4ml transformer route",
        "HLS",
        "M1_RTL",
        "survey/build/artifact_inventory.csv#project_family_id=PF-3DBBE522B68ECE13",
        artifact_commit="arxiv-2409.05207v1",
        artifact_sha256="52e6be2898b331cb37bedb6745dfacb094e9c3792f73de512b9722d557b6b2b0",
        first_gate="ARTIFACT_ATTRIBUTION",
        first_failure_code="F_SOURCE_MISSING",
        first_failure_detail=(
            "The paper audit found no attributed public project artifact for the "
            "transformer extension, so a generic upstream checkout cannot substitute."
        ),
    ),
    "R7": RouteSpec(
        "R7",
        "R7-open-accelerator",
        "open reusable accelerator control",
        "PARAMETERIZED_RTL",
        "M2_STATEFUL_DECODE",
        "survey/build/artifact_inventory.csv#project_family_id=PF-4EBDD47F47E94583",
        source_commit="3b3e98fabbca7987809c681244076a646af519b9",
        source_sha256="09db867d6000c8f0d8ee8868696d7981e66ca0665762ed86c27df34bd7fe796b",
        complete_elaboratable_rtl=True,
        first_gate="CAUSAL_LM_COVERAGE",
        first_failure_code="F_INTERFACE",
        first_failure_detail=(
            "The audited MIT source is a time-series transformer and does not provide "
            "a causal-LM prefill/decode, KV-cache, or token-generation interface."
        ),
    ),
    "R8": RouteSpec(
        "R8",
        "R8-cpu-fpga-fallback",
        "Cascade CPU/FPGA fallback control",
        "CPU_FPGA_FALLBACK",
        "M2_STATEFUL_DECODE",
        "survey/build/repository_audit.csv#repository_audit_id=REPO-PF-E9C1300B04E80B95",
        source_commit="e21dafa4d877c1dc7846f9e0b60c05a995d033eb",
        source_sha256="5b3101bd5b9edfc09d115057f560b04cdecf886822f20ed4cbac3d322be41ef0",
        first_gate="CAUSAL_LM_COVERAGE",
        first_failure_code="F_INTERFACE",
        first_failure_detail=(
            "The frozen source has a BSD-2 licence despite GitHub's NOASSERTION SPDX "
            "classification, but the audited Cascade artifact is a Verilog virtualization "
            "control and contains no causal-LM prefill/decode or token-loop implementation."
        ),
    ),
}

_COMMON_AUDIT_COMMAND = (
    "sha256sum survey/protocol.md survey/build/deep_review.csv "
    "survey/build/artifact_inventory.csv survey/build/repository_audit.csv"
)
_PYTEST_SITE_PACKAGES = ":".join(
    (
        "/nix/store/wiivwk558q3nj8xnzyc901dsc5c8fqf4-python3.11-pytest-8.1.1/lib/python3.11/site-packages",
        "/nix/store/g48903rpbx6czj8fdmjckxsn7ns4xi3b-python3.11-pluggy-1.4.0/lib/python3.11/site-packages",
        "/nix/store/x86vbwafzpwk6nhcpgvfbyyma9ajp1b8-python3.11-iniconfig-2.0.0/lib/python3.11/site-packages",
        "/nix/store/dkphwn70lhdmazrl4zdnj63gy0yw4qfj-python3.11-packaging-24.0/lib/python3.11/site-packages",
    )
)
_R1_RTL = (
    "/nix/store/b8pwl1r7jq05hn5pphj4zxyg67c3zxjs-"
    "xv720lfw0g2mywl7lksp66f81gwamaha-tinystories-w8a8-rc-polynomial-exp-"
    "calyx-native-sv/sv/main.sv"
)

ROUTE_COMMANDS: dict[str, tuple[str, ...]] = {
    "R1": (
        "git rev-parse HEAD && nix --version && nix develop -c bash -c "
        "'python --version; circt-opt --version; mlir-opt --version; "
        "verilator --version; yosys -V'",
        "nix build .#tinystories-representative-core-w4a8-pytorch-exported "
        "--no-link --print-out-paths -L",
        "nix build .#tinystories-representative-core-w4a8-linalg "
        "--no-link --print-out-paths -L",
        "nix develop -c python -m unittest tests.test_torch_mlir_fingerprint "
        "tests.test_pipeline_clarity -v",
        "nix build github:NixOS/nixpkgs/"
        "b134951a4c9f3c995fd7be05f3243f8ecd65d798#python311Packages.pytest "
        "--no-link",
        f"PYTHONPATH={_PYTEST_SITE_PACKAGES} nix develop -c python -m pytest -q",
        "nix develop -c python -m py_compile tests/test_rc_observable_driver.py",
        "nix build .#tinystories-representative-core-w4a8-integer-via-linalg-"
        "no-handshake-calyx-native-sv --no-link --print-out-paths -L",
        f"sha256sum {_R1_RTL} && wc -c {_R1_RTL}",
        f"nix develop -c verilator --lint-only --timing --Wno-fatal "
        f"--top-module main {_R1_RTL}",
        f"nix develop -c yosys -p 'read_verilog -sv {_R1_RTL}; "
        "hierarchy -check -top main; synth -top main; stat'",
    ),
    "R2": (
        _COMMON_AUDIT_COMMAND,
        "curl -fsSL https://zenodo.org/api/records/10462167/files/README.md/content",
        "python3 -c \"import json; d=json.load(open('survey/build/api-cache/responses/zenodo/19f09e16466d9bcc9442e69b70f082e079eb5a6a349e4c225943c8366ac8a331.body')); print([(f['key'],f['size'],f['checksum']) for f in d['files']])\"",
    ),
    "R3": (
        _COMMON_AUDIT_COMMAND,
        "python3 -c \"import csv; r=list(csv.DictReader(open('survey/build/artifact_inventory.csv'))); m=[x for x in r if 'mase' in (x['title']+' '+x['normalized_artifact_url']).lower()]; print('matching_artifact_rows='+str(len(m)))\"",
    ),
    "R4": (
        _COMMON_AUDIT_COMMAND,
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/repository_audit.csv')) if x['project_family_id']=='PF-86FE8DBFB50CB04C'); print(json.dumps({k:r[k] for k in ('observed_commit','licence_state','licence_spdx_id','source_closure_state','generated_or_omitted_rtl','tool_indicators_json','failure_code')},sort_keys=True))\"",
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/artifact_inventory.csv')) if x['project_family_id']=='PF-86FE8DBFB50CB04C'); print(json.dumps({k:r[k] for k in ('artifact_claim_state','artifact_relation','limitations')},sort_keys=True))\"",
    ),
    "R5": (
        _COMMON_AUDIT_COMMAND,
        "python3 -c \"import csv; r=list(csv.DictReader(open('survey/build/artifact_inventory.csv'))); m=[x for x in r if 'finn' in (x['title']+' '+x['normalized_artifact_url']).lower()]; print('matching_artifact_rows='+str(len(m)))\"",
    ),
    "R6": (
        _COMMON_AUDIT_COMMAND,
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/artifact_inventory.csv')) if x['project_family_id']=='PF-3DBBE522B68ECE13'); print(json.dumps({k:r[k] for k in ('artifact_claim_state','artifact_kind','observed_status','licence_state','failure_code','limitations')},sort_keys=True))\"",
    ),
    "R7": (
        _COMMON_AUDIT_COMMAND,
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/repository_audit.csv')) if x['project_family_id']=='PF-4EBDD47F47E94583'); print(json.dumps({k:r[k] for k in ('observed_commit','licence_spdx_id','source_closure_state','generated_or_omitted_rtl','tests_json','failure_code')},sort_keys=True))\"",
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/deep_review.csv')) if x['project_family_id']=='PF-4EBDD47F47E94583'); print(json.dumps({k:r[k] for k in ('title','rq2_model_family','rq2_prefill','rq2_decode','rq2_token_loop','rq2_kv_cache','rq2_completeness')},sort_keys=True))\"",
    ),
    "R8": (
        _COMMON_AUDIT_COMMAND,
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/repository_audit.csv')) if x['project_family_id']=='PF-E9C1300B04E80B95'); print(json.dumps({k:r[k] for k in ('observed_commit','licence_state','licence_spdx_id','licence_evidence','source_closure_state','vendor_ip_indicators_json','failure_code')},sort_keys=True))\"",
        "python3 -c \"import csv,json; r=next(x for x in csv.DictReader(open('survey/build/deep_review.csv')) if x['project_family_id']=='PF-E9C1300B04E80B95'); print(json.dumps({k:r[k] for k in ('title','rq1_input_frontend','rq2_model_family','rq2_prefill','rq2_decode','rq2_token_loop','rq2_kv_cache','rq2_completeness','rq4_required_closed_tools_or_ip')},sort_keys=True))\"",
    ),
}

RECEIPT_REQUIRED_FIELDS = (
    "receipt_schema_version",
    "route_id",
    "route_family",
    "route_title",
    "source_evidence",
    "source_commit",
    "source_sha256",
    "artifact_commit",
    "artifact_sha256",
    "environment_manifest",
    "executed_commands",
    "command_results",
    "expected_stage",
    "actual_stage",
    "status",
    "decision",
    "frozen_tolerance",
    "failure_code",
    "failure_detail",
    "fixture",
    "generated_rtl_paths",
    "lint_evidence",
    "simulation_evidence",
    "synthesis_evidence",
    "m2_evidence",
    "evidence_files",
    "next_bounded_action",
    "budget_hours",
    "complete_elaboratable_rtl",
    "commands_sha256",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _environment_manifest() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cwd_policy": "repository-relative commands",
        "protocol_sha256": _sha256(PROTOCOL) if PROTOCOL.is_file() else "",
        "artifact_inventory_sha256": (
            _sha256(ARTIFACT_INVENTORY) if ARTIFACT_INVENTORY.is_file() else ""
        ),
        "repository_audit_sha256": (
            _sha256(REPOSITORY_AUDIT) if REPOSITORY_AUDIT.is_file() else ""
        ),
        "deep_review_sha256": _sha256(DEEP_REVIEW) if DEEP_REVIEW.is_file() else "",
    }


def execute_commands(
    commands: Sequence[str], *, cwd: Path = ROOT
) -> tuple[str, str, tuple[dict[str, Any], ...]]:
    """Run every diagnostic command and retain per-command exit evidence."""

    stdout_sections: list[str] = []
    stderr_sections: list[str] = []
    results: list[dict[str, Any]] = []
    for index, command in enumerate(commands, start=1):
        completed = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        header = f"===== command {index}: {command} =====\n"
        stdout_sections.append(header + completed.stdout)
        stderr_sections.append(header + completed.stderr)
        results.append(
            {
                "index": index,
                "command": command,
                "exit_code": completed.returncode,
            }
        )
    return "".join(stdout_sections), "".join(stderr_sections), tuple(results)


@dataclass(frozen=True)
class RouteReceipt:
    route_id: str
    route_family: str
    route_title: str
    source_evidence: str
    source_commit: str
    source_sha256: str
    artifact_commit: str
    artifact_sha256: str
    environment_manifest: Mapping[str, Any]
    executed_commands: tuple[str, ...]
    expected_stage: str
    actual_stage: str
    status: str
    decision: str
    frozen_tolerance: Mapping[str, Any]
    failure_code: str
    failure_detail: str
    fixture: str
    generated_rtl_paths: tuple[str, ...] = ()
    lint_evidence: tuple[str, ...] = ()
    simulation_evidence: tuple[str, ...] = ()
    synthesis_evidence: tuple[str, ...] = ()
    m2_evidence: Mapping[str, Any] = field(default_factory=dict)
    evidence_files: tuple[str, ...] = ()
    next_bounded_action: str = ""
    budget_hours: int = 16
    complete_elaboratable_rtl: bool = False
    stdout: str = ""
    stderr: str = ""
    command_results: tuple[Mapping[str, Any], ...] = ()
    commands_sha256: str = ""
    receipt_schema_version: int = 1

    @classmethod
    def controlled_failure(
        cls,
        *,
        route: RouteSpec,
        actual_stage: str,
        failure_code: str,
        next_bounded_action: str,
        executed_commands: Sequence[str] = (),
        failure_detail: str | None = None,
        budget_hours: int = 16,
    ) -> "RouteReceipt":
        return cls(
            route_id=route.route_id,
            route_family=route.route_family,
            route_title=route.title,
            source_evidence=route.source_evidence,
            source_commit=route.source_commit,
            source_sha256=route.source_sha256,
            artifact_commit=route.artifact_commit,
            artifact_sha256=route.artifact_sha256,
            environment_manifest=_environment_manifest(),
            executed_commands=tuple(executed_commands),
            expected_stage=route.expected_stage,
            actual_stage=actual_stage,
            status="STOPPED",
            decision="INELIGIBLE",
            frozen_tolerance=FIXTURES[route.fixture]["acceptance"],
            failure_code=failure_code,
            failure_detail=failure_detail or route.first_failure_detail,
            fixture=route.fixture,
            next_bounded_action=next_bounded_action,
            budget_hours=budget_hours,
            complete_elaboratable_rtl=route.complete_elaboratable_rtl,
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("stdout")
        value.pop("stderr")
        return value


def run_route(route: RouteSpec, budget_hours: int) -> RouteReceipt:
    if budget_hours not in (16, 40):
        raise ValueError("budget_hours must be the frozen 16 or 40 hour cap")
    if route.first_failure_code not in ALLOWED_FAILURE_CODES:
        raise ValueError(f"failure_code: {route.first_failure_code}")
    if (
        budget_hours >= 16
        and not route.complete_elaboratable_rtl
        and not route.bounded_corrective_action
    ):
        return RouteReceipt.controlled_failure(
            route=route,
            actual_stage=route.first_gate,
            failure_code=route.first_failure_code,
            next_bounded_action=_bounded_next_action(route),
            budget_hours=budget_hours,
        )
    return RouteReceipt.controlled_failure(
        route=route,
        actual_stage=route.first_gate,
        failure_code=route.first_failure_code,
        next_bounded_action=route.bounded_corrective_action or _bounded_next_action(route),
        budget_hours=budget_hours,
    )


def _bounded_next_action(route: RouteSpec) -> str:
    actions = {
        "R1": "Repair the baseline test collection in a separate compiler-lab change, then rerun the frozen R1 commands.",
        "R2": "Obtain redistributable source RTL from the IP owner; a closed bitstream cannot satisfy independent lint or synthesis gates.",
        "R3": "Attribute a Mase release to a frozen survey work and audit its licence and immutable source commit.",
        "R4": "Obtain and audit the paper-specific LLM release before attempting Allo M0/M1 generation.",
        "R5": "Attribute and audit the exact FINN transformer extension release; do not substitute generic FINN.",
        "R6": "Attribute and audit the exact hls4ml transformer extension release; do not substitute generic hls4ml.",
        "R7": "Select a licensed causal-LM accelerator with a prefill/decode and persistent-KV interface.",
        "R8": "Add and audit a causal-LM kernel with persistent KV state before evaluating the fallback runtime.",
    }
    return actions.get(
        route.route_id,
        "Supply complete independently elaboratable RTL or a bounded corrective action.",
    )


def _commands_text(commands: Sequence[str]) -> str:
    lines = ["#!/usr/bin/env bash", "set -u", ""]
    lines.extend(commands)
    return "\n".join(lines) + "\n"


def validate_receipt(
    receipt: Mapping[str, Any], route_dir: Path | None = None
) -> None:
    missing = [field for field in RECEIPT_REQUIRED_FIELDS if field not in receipt]
    if missing:
        raise ValueError(f"missing receipt fields: {', '.join(missing)}")
    if receipt["failure_code"] not in ALLOWED_FAILURE_CODES:
        raise ValueError(f"failure_code: {receipt['failure_code']}")
    if receipt["failure_code"] != "NONE" and receipt["decision"] == "PRIMARY":
        raise ValueError("a failed hard gate cannot have decision=PRIMARY")
    if receipt["status"] == "PASSED":
        if receipt["failure_code"] != "NONE":
            raise ValueError("PASSED receipt must use failure_code=NONE")
        if not any(
            receipt[field]
            for field in ("lint_evidence", "simulation_evidence", "synthesis_evidence")
        ):
            raise ValueError("PASSED receipt has no executable evidence")
        if receipt["actual_stage"] == "M2_STATEFUL_DECODE":
            m2 = receipt["m2_evidence"]
            required_m2 = (
                m2.get("implemented") is True
                and m2.get("kv_state_persistent") is True
                and m2.get("token_ids_identical") is True
                and m2.get("token_loop_control") == "hardware"
            )
            if receipt["fixture"] != "M2-tiny-lm" or not required_m2:
                raise ValueError(
                    "M2 pass requires implemented hardware-controlled decode, "
                    "persistent KV state, and token-identical evidence"
                )
    if receipt["fixture"] not in FIXTURES:
        raise ValueError(f"unknown fixture: {receipt['fixture']}")
    if int(receipt["budget_hours"]) not in (16, 40):
        raise ValueError("budget_hours must be 16 or 40")
    commands = list(receipt["executed_commands"])
    results = list(receipt["command_results"])
    if len(results) != len(commands):
        raise ValueError("command_results must cover every executed command")
    for index, (command, result) in enumerate(zip(commands, results), start=1):
        if (
            not isinstance(result, Mapping)
            or result.get("index") != index
            or result.get("command") != command
            or not isinstance(result.get("exit_code"), int)
        ):
            raise ValueError(
                "command_results must preserve each command, index, and exit code"
            )
    if route_dir is None:
        return
    commands_path = route_dir / "commands.sh"
    if not commands_path.is_file():
        raise ValueError("missing commands.sh")
    observed_hash = _sha256(commands_path)
    if observed_hash != receipt["commands_sha256"]:
        raise ValueError("commands_sha256 does not match commands.sh")
    if commands_path.read_text(encoding="utf-8") != _commands_text(commands):
        raise ValueError("commands.sh does not match executed_commands")
    for name in ("README.md", "stdout.log", "stderr.log"):
        if not (route_dir / name).is_file():
            raise ValueError(f"missing receipt file: {name}")
    for evidence in receipt["evidence_files"]:
        path = route_dir / str(evidence)
        if not path.is_file():
            raise ValueError(f"missing evidence file: {evidence}")


def write_route_receipt(receipt: RouteReceipt, route_dir: Path) -> Path:
    route_dir.mkdir(parents=True, exist_ok=True)
    commands_path = route_dir / "commands.sh"
    commands_path.write_text(
        _commands_text(receipt.executed_commands), encoding="utf-8"
    )
    commands_path.chmod(0o755)
    command_hash = _sha256(commands_path)
    finalized = replace(receipt, commands_sha256=command_hash)
    manifest = finalized.to_dict()
    (route_dir / "stdout.log").write_text(finalized.stdout, encoding="utf-8")
    (route_dir / "stderr.log").write_text(finalized.stderr, encoding="utf-8")
    (route_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (route_dir / "README.md").write_text(
        _receipt_readme(finalized), encoding="utf-8"
    )
    validate_receipt(manifest, route_dir)
    return route_dir / "manifest.json"


def _receipt_readme(receipt: RouteReceipt) -> str:
    return (
        f"# {receipt.route_id}: {receipt.route_title}\n\n"
        f"- Status: `{receipt.status}`\n"
        f"- Decision: `{receipt.decision}`\n"
        f"- Expected stage: `{receipt.expected_stage}`\n"
        f"- First observed gate: `{receipt.actual_stage}`\n"
        f"- Failure code: `{receipt.failure_code}`\n"
        f"- Source evidence: `{receipt.source_evidence}`\n"
        f"- Fixture: `{receipt.fixture}`\n"
        f"- Budget cap: `{receipt.budget_hours}` hours\n\n"
        f"{receipt.failure_detail}\n\n"
        f"Next bounded action: {receipt.next_bounded_action}\n\n"
        "`manifest.json` is authoritative. `commands.sh` is SHA-256 checked by "
        "that manifest; stdout and stderr are retained separately. A stopped "
        "route has no implied pass at any later stage.\n"
    )


def _write_summary(receipts: Sequence[RouteReceipt], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "route_id",
        "route_family",
        "status",
        "decision",
        "expected_stage",
        "actual_stage",
        "failure_code",
        "fixture",
        "source_commit",
        "artifact_commit",
        "next_bounded_action",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for receipt in receipts:
            row = receipt.to_dict()
            writer.writerow({field: row[field] for field in fields})


def record_route(
    route: RouteSpec, route_dir: Path, *, budget_hours: int
) -> RouteReceipt:
    """Execute the frozen route checks and persist their controlled result."""

    commands = ROUTE_COMMANDS[route.route_id]
    stdout, stderr, results = execute_commands(commands, cwd=ROOT)
    receipt = run_route(route, budget_hours)
    receipt = replace(
        receipt,
        executed_commands=commands,
        stdout=stdout,
        stderr=stderr,
        command_results=results,
    )
    if route.route_id == "R1":
        receipt = replace(
            receipt,
            failure_detail=(
                "Capture and Linalg lowering completed, but the focused smoke suite "
                "failed 18/19 at a stale patches-directory assertion. Pinned pytest "
                "collection also reported the preserved Python 3.11 f-string SyntaxError "
                "and submodule import errors. The representative-core SV derivation "
                "failed because the store-copied export script resolved an unexported "
                "verification helper to a nonexistent /nix/store path. Independent lint "
                "and generic synthesis of the hash-pinned existing RC RTL then failed in "
                "Verilator and Yosys; no RTL gate passed."
            ),
            next_bounded_action=(
                "In a separate compiler-lab change, repair the baseline test collection "
                "and missing CALYX_VERIFY_F32_CONSTANT_BITS derivation input, then "
                "regenerate RTL before rerunning lint and synthesis."
            ),
            generated_rtl_paths=(_R1_RTL,),
            lint_evidence=("stderr.log#command-10",),
            synthesis_evidence=("stdout.log#command-11",),
        )
    write_route_receipt(receipt, route_dir)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", choices=[*ROUTES, "all"], default="all")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--budget-hours", type=int, choices=(16, 40), default=16)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)

    selected = list(ROUTES.values()) if args.route == "all" else [ROUTES[args.route]]
    receipts: list[RouteReceipt] = []
    for route in selected:
        route_dir = args.out if len(selected) == 1 and args.out else ROOT / "survey/compatibility" / route.slug
        if args.validate:
            manifest = json.loads((route_dir / "manifest.json").read_text())
            validate_receipt(manifest, route_dir)
            continue
        receipt = record_route(route, route_dir, budget_hours=args.budget_hours)
        receipts.append(receipt)
    if receipts and args.route == "all":
        _write_summary(receipts, ROOT / "survey/build/compatibility_summary.csv")
        (ROOT / "survey/build/compatibility_fixtures.json").write_text(
            json.dumps(FIXTURES, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
