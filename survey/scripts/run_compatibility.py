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
        "operator_shapes": {
            "int8_matmul": {
                "lhs": [1, 16, 64],
                "rhs": [64, 64],
                "output": [1, 16, 64],
            },
            "normalization": {
                "input": [1, 16, 64],
                "scale": [64],
                "bias": [64],
                "output": [1, 16, 64],
            },
            "activation": {
                "input": [1, 16, 64],
                "output": [1, 16, 64],
            },
            "rope": {
                "query": [1, 4, 16, 16],
                "key": [1, 4, 16, 16],
                "position": [1, 16],
                "query_output": [1, 4, 16, 16],
                "key_output": [1, 4, 16, 16],
            },
            "causal_softmax": {
                "logits": [1, 4, 16, 16],
                "causal_mask": [1, 1, 16, 16],
                "output": [1, 4, 16, 16],
            },
            "kv_read_write": {
                "key_write": [1, 4, 1, 16],
                "value_write": [1, 4, 1, 16],
                "key_cache": [1, 4, 16, 16],
                "value_cache": [1, 4, 16, 16],
                "key_read": [1, 4, 16, 16],
                "value_read": [1, 4, 16, 16],
            },
        },
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
        first_gate="OBSERVATION_REQUIRED",
        first_failure_code="NONE",
        first_failure_detail="R1 must be classified from the recorded command evidence.",
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
        first_gate="OBSERVATION_REQUIRED",
        first_failure_code="NONE",
        first_failure_detail="R7 must be classified from the exact checkout evidence.",
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
        first_gate="OBSERVATION_REQUIRED",
        first_failure_code="NONE",
        first_failure_detail="R8 must be classified from the exact checkout evidence.",
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
_R1_FROZEN_CONTROL = "433592c448f8b19a30dd046a1ec726b09a86d892"
_R7_SOURCE_URL = "https://github.com/Edwina1030/TinyTransformer4TS.git"
_R7_SOURCE_COMMIT = "3b3e98fabbca7987809c681244076a646af519b9"
_R7_SOURCE_DIR = "/tmp/llm2fpga-task6-r7-receipt-source"
_R8_SOURCE_URL = "https://github.com/JoshuaLandgraf/cascade.git"
_R8_SOURCE_COMMIT = "e21dafa4d877c1dc7846f9e0b60c05a995d033eb"
_R8_SOURCE_DIR = "/tmp/llm2fpga-task6-r8-receipt-source"
_R8_BUILD_DIR = "/tmp/llm2fpga-task6-r8-receipt-build"

ROUTE_COMMANDS: dict[str, tuple[str, ...]] = {
    "R1": (
        "git rev-parse HEAD && nix --version && nix develop -c bash -c "
        "'python --version; circt-opt --version; mlir-opt --version; "
        "verilator --version; yosys -V'",
        "git diff --quiet 433592c448f8b19a30dd046a1ec726b09a86d892..HEAD -- "
        ". ':(exclude)survey/**' ':(exclude).superpowers/**' "
        "':(exclude)tests/test_survey_*' && git diff --quiet -- . "
        "':(exclude)survey/**' ':(exclude).superpowers/**' "
        "':(exclude)tests/test_survey_*' && "
        "printf 'compiler_scope_equivalent=true\\n'",
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
        f"if test -d {_R7_SOURCE_DIR}/.git; then git -C {_R7_SOURCE_DIR} fetch --quiet origin {_R7_SOURCE_COMMIT}; else git clone --filter=blob:none --no-checkout {_R7_SOURCE_URL} {_R7_SOURCE_DIR}; fi && git -C {_R7_SOURCE_DIR} checkout --detach {_R7_SOURCE_COMMIT} && git -C {_R7_SOURCE_DIR} rev-parse HEAD && git -C {_R7_SOURCE_DIR} status --short",
        f"python3 -c \"from pathlib import Path; r=Path('{_R7_SOURCE_DIR}'); req=(r/'requirements.txt').read_text(); dep=next(x for x in req.splitlines() if x.startswith('git+ssh://')); ref=dep.rsplit('@',1)[-1]; immutable=len(ref)==40 and all(c in '0123456789abcdef' for c in ref.lower()); marker=chr(36)+'{{'; templates=list((r/'models/quant').glob('*.tpl.vhd')); print('r7_external_dependency='+dep); print('r7_external_dependency_immutable='+str(immutable).lower()); print('r7_templates_fully_rendered='+str(not any(marker in p.read_text() for p in templates)).lower())\"",
        "GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10' git ls-remote git@github.com:es-ude/elastic-ai.creator.git add-linear-quantization",
        f"python3 -m py_compile {_R7_SOURCE_DIR}/models/quant/design.py {_R7_SOURCE_DIR}/hw_converter/convert2hw.py",
        f"cd {_R7_SOURCE_DIR} && python3 -c 'import hw_converter.convert2hw'",
        f"nix develop -c bash -c 'command -v ghdl; ghdl -a {_R7_SOURCE_DIR}/models/quant/transformer.tpl.vhd'",
        f"python3 -c \"from pathlib import Path; t=(Path('{_R7_SOURCE_DIR}')/'README.md').read_text(); print('r7_causal_lm_interface='+str('causal' in t.lower() and 'decode' in t.lower()).lower()); print('r7_declared_workload=time_series')\"",
    ),
    "R8": (
        _COMMON_AUDIT_COMMAND,
        f"if test -d {_R8_SOURCE_DIR}/.git; then git -C {_R8_SOURCE_DIR} fetch --quiet origin {_R8_SOURCE_COMMIT}; else git clone --filter=blob:none --no-checkout {_R8_SOURCE_URL} {_R8_SOURCE_DIR}; fi && git -C {_R8_SOURCE_DIR} checkout --detach {_R8_SOURCE_COMMIT} && git -C {_R8_SOURCE_DIR} rev-parse HEAD && git -C {_R8_SOURCE_DIR} status --short",
        f"python3 -c \"from pathlib import Path; d=Path('{_R8_SOURCE_DIR}')/'share/cascade/de10'; qsf=(d/'DE10_NANO_SoC_GHRD.qsf').read_text(); needed=['soc_system/synthesis/soc_system.qip']; referenced=[p for p in needed if p in qsf]; missing=[p for p in referenced if not (d/p).is_file()]; print('r8_qsf_references='+','.join(referenced)); print('r8_qsys_source_present='+str((d/'soc_system.qsys').is_file()).lower()); print('r8_missing_required_files='+','.join(missing)); print('r8_source_closure_complete='+str(not missing).lower())\"",
        f"cmake -S {_R8_SOURCE_DIR} -B {_R8_BUILD_DIR} -DCMAKE_BUILD_TYPE=Release && cmake --build {_R8_BUILD_DIR} -j2",
        f"nix develop -c yosys -p 'read_verilog -I {_R8_SOURCE_DIR} {_R8_SOURCE_DIR}/share/cascade/test/benchmark/adpcm/adpcm.v; hierarchy -check -top test; proc; check'",
        f"python3 -c \"from pathlib import Path; t=(Path('{_R8_SOURCE_DIR}')/'experiments/README.md').read_text().lower(); print('r8_causal_lm_interface='+str('causal' in t and 'decode' in t).lower()); print('r8_declared_workload=fpga_virtualization')\"",
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
    "execution_provenance",
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
    execution_provenance: Mapping[str, Any] = field(default_factory=dict)
    evidence_files: tuple[str, ...] = ()
    next_bounded_action: str = ""
    budget_hours: int = 16
    complete_elaboratable_rtl: bool = False
    stdout: str = ""
    stderr: str = ""
    command_results: tuple[Mapping[str, Any], ...] = ()
    commands_sha256: str = ""
    receipt_schema_version: int = 2

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


_OBSERVATION_DRIVEN_ROUTE_IDS = frozenset({"R1", "R7", "R8"})


def _load_recorded_receipt(route: RouteSpec, budget_hours: int) -> RouteReceipt:
    """Return validated persisted evidence for a route whose gate is observed."""

    route_dir = ROOT / "survey/compatibility" / route.slug
    manifest_path = route_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"{route.route_id} requires an observed receipt at {manifest_path}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_receipt(manifest, route_dir)
    if (
        manifest["route_id"] != route.route_id
        or manifest["source_commit"] != route.source_commit
    ):
        raise ValueError(
            f"{route.route_id} recorded receipt does not match the requested route"
        )
    receipt_data = dict(manifest)
    for field_name in (
        "executed_commands",
        "generated_rtl_paths",
        "lint_evidence",
        "simulation_evidence",
        "synthesis_evidence",
        "evidence_files",
        "command_results",
    ):
        receipt_data[field_name] = tuple(receipt_data[field_name])
    receipt_data["stdout"] = (route_dir / "stdout.log").read_text(encoding="utf-8")
    receipt_data["stderr"] = (route_dir / "stderr.log").read_text(encoding="utf-8")
    return replace(RouteReceipt(**receipt_data), budget_hours=budget_hours)


def run_route(route: RouteSpec, budget_hours: int) -> RouteReceipt:
    if budget_hours not in (16, 40):
        raise ValueError("budget_hours must be the frozen 16 or 40 hour cap")
    if route.route_id in _OBSERVATION_DRIVEN_ROUTE_IDS:
        return _load_recorded_receipt(route, budget_hours)
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


def _result_containing(
    results: Sequence[Mapping[str, Any]], fragment: str
) -> Mapping[str, Any]:
    for result in results:
        if fragment in str(result["command"]):
            return result
    raise ValueError(f"missing executed command containing: {fragment}")


def _command_stdout(
    stdout: str, commands: Sequence[str], command_index: int
) -> str:
    header = f"===== command {command_index}: {commands[command_index - 1]} =====\n"
    if header not in stdout:
        raise ValueError(f"missing stdout section for command {command_index}")
    section = stdout.split(header, 1)[1]
    next_header = f"===== command {command_index + 1}:"
    return section.split(next_header, 1)[0]


def _derived_observed_failure(
    route: RouteSpec,
    commands: Sequence[str],
    stdout: str,
    stderr: str,
    results: Sequence[Mapping[str, Any]],
    budget_hours: int,
) -> RouteReceipt:
    """Classify R1/R7/R8 only from the persisted command observations."""

    if route.route_id == "R1":
        environment = results[0]
        if environment["exit_code"] != 0:
            return RouteReceipt.controlled_failure(
                route=route,
                actual_stage="ENVIRONMENT_REPRODUCTION",
                failure_code="F_ENV",
                failure_detail=(
                    "The recorded environment reproduction command failed; no later "
                    "compatibility conclusion is inferred."
                ),
                next_bounded_action="Repair the pinned execution environment and rerun R1.",
                executed_commands=commands,
                budget_hours=budget_hours,
            )
        native_sv = _result_containing(results, "calyx-native-sv")
        if (
            native_sv["exit_code"] != 0
            and "verify_calyx_f32_constant_bits.py" in stderr
            and "can't open file" in stderr
        ):
            executed_commit = _command_stdout(stdout, commands, 1).splitlines()[0]
            if len(executed_commit) != 40:
                raise ValueError("R1 did not record a full execution commit")
            scope_check = _result_containing(results, "compiler_scope_equivalent=true")
            scope_equivalent = (
                scope_check["exit_code"] == 0
                and "compiler_scope_equivalent=true" in stdout
            )
            if not scope_equivalent:
                raise ValueError("R1 execution scope differs from frozen control")
            return replace(
                RouteReceipt.controlled_failure(
                    route=route,
                    actual_stage="RTL_GENERATION",
                    failure_code="F_SOURCE_MISSING",
                    failure_detail=(
                        "The environment and capture/Linalg commands completed. The "
                        "earlier smoke-suite stale assertion and pytest collection errors "
                        "are preserved baseline diagnostics, not F_ENV. The first protocol "
                        "taxonomy match is RTL generation: the native-SV derivation's "
                        "store-copied export script references the missing "
                        "verify_calyx_f32_constant_bits.py helper."
                    ),
                    next_bounded_action=(
                        "In a separate compiler-lab change, supply the committed "
                        "CALYX_VERIFY_F32_CONSTANT_BITS derivation input, regenerate RTL, "
                        "then rerun lint and synthesis."
                    ),
                    executed_commands=commands,
                    budget_hours=budget_hours,
                ),
                execution_provenance={
                    "executed_commit": executed_commit,
                    "frozen_control_commit": route.source_commit,
                    "compiler_scope_check_command": scope_check["command"],
                    "compiler_scope_equivalent": True,
                    "scope": (
                        "tracked compiler-lab files excluding survey/, .superpowers/, "
                        "and tests/test_survey_*"
                    ),
                },
            )
        raise ValueError(
            "R1 did not reproduce the observed missing native-SV helper blocker"
        )

    if route.route_id == "R7":
        checkout = _result_containing(results, "TinyTransformer4TS.git")
        if checkout["exit_code"] != 0:
            return RouteReceipt.controlled_failure(
                route=route,
                actual_stage="SOURCE_RETRIEVAL",
                failure_code="F_SOURCE_MISSING",
                failure_detail="The exact TinyTransformer4TS commit could not be checked out.",
                next_bounded_action="Recover the exact paper-reported source commit.",
                executed_commands=commands,
                budget_hours=budget_hours,
            )
        if (
            "r7_external_dependency_immutable=false" in stdout
            and "r7_templates_fully_rendered=false" in stdout
        ):
            return RouteReceipt.controlled_failure(
                route=route,
                actual_stage="SOURCE_CLOSURE",
                failure_code="F_SOURCE_MISSING",
                failure_detail=(
                    "The exact MIT checkout is accessible, but its hardware-generation "
                    "templates depend on elastic-ai.creator through a mutable git branch "
                    "rather than a source-pinned release; the checked-in VHDL templates "
                    "remain unrendered. The later import and GHDL checks are retained as "
                    "diagnostics, while source closure is the first failed gate."
                ),
                next_bounded_action=(
                    "Pin and include the exact ElasticAI.Creator source/template revision "
                    "needed to render complete VHDL before attempting operator triage."
                ),
                executed_commands=commands,
                budget_hours=budget_hours,
            )
        raise ValueError("R7 did not record the expected source-closure evidence")

    if route.route_id == "R8":
        checkout = _result_containing(results, "cascade.git")
        if checkout["exit_code"] != 0:
            return RouteReceipt.controlled_failure(
                route=route,
                actual_stage="SOURCE_RETRIEVAL",
                failure_code="F_SOURCE_MISSING",
                failure_detail="The exact Cascade artifact commit could not be checked out.",
                next_bounded_action="Recover the exact artifact commit and its dependencies.",
                executed_commands=commands,
                budget_hours=budget_hours,
            )
        if (
            "r8_source_closure_complete=false" in stdout
            and "soc_system/synthesis/soc_system.qip" in stdout
        ):
            return RouteReceipt.controlled_failure(
                route=route,
                actual_stage="SOURCE_CLOSURE",
                failure_code="F_SOURCE_MISSING",
                failure_detail=(
                    "The exact Cascade checkout is accessible and includes "
                    "soc_system.qsys, but its DE10 Quartus project references the absent "
                    "generated soc_system/synthesis/soc_system.qip hierarchy. The source "
                    "requires vendor Qsys generation to produce that input. The later "
                    "CMake and Yosys checks are retained as "
                    "diagnostics; causal-LM coverage is not reached."
                ),
                next_bounded_action=(
                    "Provide the generated DE10 QIP hierarchy or a reproducible, "
                    "replaceable generation path before attempting fallback-route evaluation."
                ),
                executed_commands=commands,
                budget_hours=budget_hours,
            )
        raise ValueError("R8 did not record the expected source-closure evidence")

    raise ValueError(f"no observed failure derivation for {route.route_id}")


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


def _m2_dimensions() -> dict[str, Any]:
    fixture = FIXTURES["M2-tiny-lm"]
    return {
        field: fixture[field]
        for field in (
            "blocks",
            "d_model",
            "heads",
            "d_ff",
            "vocabulary",
            "max_sequence",
            "batch_size",
            "decode_tokens",
            "decode_mode",
            "kv_state",
        )
    }


def _route_file(route_dir: Path, value: str, field: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if ".." in candidate.parts:
        raise ValueError(f"{field}: path traversal is not an evidence anchor")
    return route_dir / candidate


def _validate_evidence_anchor(
    anchor: Any,
    *,
    field: str,
    route_dir: Path,
    commands: Sequence[str],
) -> None:
    if not isinstance(anchor, str) or not anchor:
        raise ValueError(f"{field}: evidence anchor must be a nonempty string")
    if "#command-" in anchor:
        log_name, separator, command_number = anchor.partition("#command-")
        if separator != "#command-" or log_name not in {"stdout.log", "stderr.log"}:
            raise ValueError(f"{field}: invalid log command anchor: {anchor}")
        try:
            index = int(command_number)
        except ValueError as error:
            raise ValueError(f"{field}: invalid command anchor: {anchor}") from error
        if index < 1 or index > len(commands):
            raise ValueError(f"{field}: command anchor is out of range: {anchor}")
        log_path = route_dir / log_name
        expected_header = f"===== command {index}: {commands[index - 1]} =====\n"
        if not log_path.is_file() or expected_header not in log_path.read_text(encoding="utf-8"):
            raise ValueError(f"{field}: unresolved log command anchor: {anchor}")
        return
    path = _route_file(route_dir, anchor, field)
    if not path.is_file():
        raise ValueError(f"{field}: missing evidence file: {anchor}")


def _validate_m2_pass(
    receipt: Mapping[str, Any],
    *,
    route_dir: Path,
    commands: Sequence[str],
    results: Sequence[Mapping[str, Any]],
) -> None:
    if receipt["fixture"] != "M2-tiny-lm":
        raise ValueError("M2 pass requires the frozen M2-tiny-lm fixture")
    m2 = receipt["m2_evidence"]
    if not isinstance(m2, Mapping):
        raise ValueError("M2 pass requires a structured m2_evidence mapping")
    evidence_name = m2.get("evidence_file")
    command_index = m2.get("command_index")
    if not isinstance(evidence_name, str) or not evidence_name:
        raise ValueError("M2 pass requires an existing parsed evidence_file")
    if not isinstance(command_index, int) or not 1 <= command_index <= len(commands):
        raise ValueError("M2 pass requires an executed command_index")
    if results[command_index - 1]["exit_code"] != 0:
        raise ValueError("M2 pass evidence command did not succeed")
    if evidence_name not in commands[command_index - 1]:
        raise ValueError("M2 pass evidence is not tied to its executed command")
    if evidence_name not in receipt["simulation_evidence"]:
        raise ValueError("M2 pass requires simulation_evidence for its parsed result")
    evidence_path = _route_file(route_dir, evidence_name, "m2_evidence")
    if not evidence_path.is_file():
        raise ValueError("M2 pass requires an existing parsed evidence file")
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("M2 pass evidence file is not valid JSON") from error
    if not isinstance(evidence, Mapping):
        raise ValueError("M2 pass evidence JSON must be an object")
    if evidence.get("fixture") != "M2-tiny-lm":
        raise ValueError("M2 pass evidence fixture does not match M2-tiny-lm")
    if evidence.get("dimensions") != _m2_dimensions():
        raise ValueError("M2 pass evidence dimensions do not match the frozen fixture")
    if evidence.get("token_loop_control") != "hardware":
        raise ValueError("M2 pass requires a hardware token loop")
    if evidence.get("kv_state_persistent") is not True:
        raise ValueError("M2 pass requires persistent KV state")
    reference_tokens = evidence.get("reference_token_ids")
    observed_tokens = evidence.get("observed_token_ids")
    token_count = FIXTURES["M2-tiny-lm"]["decode_tokens"]
    if (
        not isinstance(reference_tokens, list)
        or not isinstance(observed_tokens, list)
        or len(reference_tokens) != token_count
        or len(observed_tokens) != token_count
        or not all(isinstance(token, int) for token in reference_tokens + observed_tokens)
        or reference_tokens != observed_tokens
    ):
        raise ValueError("M2 pass requires token-identical greedy decode outputs")


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
    if receipt["route_id"] == "R1":
        provenance = receipt["execution_provenance"]
        if (
            not isinstance(provenance, Mapping)
            or not isinstance(provenance.get("executed_commit"), str)
            or len(provenance["executed_commit"]) != 40
            or provenance["executed_commit"] == receipt["source_commit"]
            or provenance.get("frozen_control_commit") != receipt["source_commit"]
            or provenance.get("compiler_scope_equivalent") is not True
        ):
            raise ValueError(
                "execution_provenance must distinguish R1 execution from the frozen control"
            )
    is_m2_pass = (
        receipt["status"] == "PASSED"
        and receipt["actual_stage"] == "M2_STATEFUL_DECODE"
    )
    if receipt["status"] == "PASSED":
        if receipt["failure_code"] != "NONE":
            raise ValueError("PASSED receipt must use failure_code=NONE")
        if not any(
            receipt[field]
            for field in ("lint_evidence", "simulation_evidence", "synthesis_evidence")
        ):
            raise ValueError("PASSED receipt has no executable evidence")
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
        if is_m2_pass:
            raise ValueError("M2 pass requires a route directory with parsed evidence")
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
    if is_m2_pass:
        _validate_m2_pass(
            receipt, route_dir=route_dir, commands=commands, results=results
        )
    for field in ("lint_evidence", "simulation_evidence", "synthesis_evidence"):
        for anchor in receipt[field]:
            _validate_evidence_anchor(
                anchor, field=field, route_dir=route_dir, commands=commands
            )
    for rtl_path in receipt["generated_rtl_paths"]:
        path = _route_file(route_dir, str(rtl_path), "generated_rtl_paths")
        if not path.is_file():
            raise ValueError(f"generated_rtl_paths: missing RTL file: {rtl_path}")
    for evidence in receipt["evidence_files"]:
        _validate_evidence_anchor(
            evidence, field="evidence_files", route_dir=route_dir, commands=commands
        )


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
    if route.route_id in {"R1", "R7", "R8"}:
        receipt = _derived_observed_failure(
            route, commands, stdout, stderr, results, budget_hours
        )
    else:
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
                "The environment and capture/Linalg commands completed. The focused "
                "smoke suite's stale patches-directory assertion and the pinned pytest "
                "collection errors are preserved baseline diagnostics, not F_ENV. The "
                "first protocol-taxonomy blocker is RTL generation: the native-SV "
                "derivation's store-copied export script references the missing "
                "verify_calyx_f32_constant_bits.py helper. Independent lint and generic "
                "synthesis of a hash-pinned existing RC RTL then also failed; no RTL "
                "gate passed."
            ),
            next_bounded_action=(
                "In a separate compiler-lab change, supply the committed "
                "CALYX_VERIFY_F32_CONSTANT_BITS derivation input, then regenerate RTL "
                "before rerunning lint and synthesis."
            ),
            generated_rtl_paths=(_R1_RTL,),
            lint_evidence=("stderr.log#command-11",),
            synthesis_evidence=("stderr.log#command-12",),
        )
    if route.route_id == "R7":
        receipt = replace(receipt, lint_evidence=("stderr.log#command-7",))
    if route.route_id == "R8":
        receipt = replace(receipt, lint_evidence=("stderr.log#command-5",))
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
