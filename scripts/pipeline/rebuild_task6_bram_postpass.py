#!/usr/bin/env python3
"""Rebuild the accepted full16 compiler SV and its isolated c_proj ROM variant."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


CONTROL_SHA256 = "e548f90b91d78f63280b9158ba1af9f0bd2c46b5122bb87a6108d256871ae012"
VARIANT_SHA256 = "85c8466690431545c9fdf5731e140dbe1c5755c4efc1022c55ef57579fac26c2"
IR_SHA256 = "13f2a5f8de4e82fdedbd306e2c4c28c8d7932a92b365752c30e684a42d6ec974"


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def primitive_body(source: str, name: str) -> str:
    start = source.index(f"module {name} #")
    end = source.index("endmodule", start) + len("endmodule")
    return (source[start:end]
            .replace(name, "seq_mem_d1_variant", 1)
            .replace('  (* ram_style = "block" *)\n', "")
            .replace('  (* ram_style = "distributed" *)\n', ""))


def main() -> None:
    repo, calyx, out = map(Path, sys.argv[1:])
    sys.path.insert(0, str(repo))
    from scripts.pipeline import run_bram_production_sv as runner

    artifact = runner.production.generate_production_kernel(generation_steps=16)
    assert sha256(artifact.futil) == IR_SHA256, "compiler IR differs from the accepted full16 artifact"
    out.mkdir()
    (out / "model.futil").write_text(artifact.futil)
    library = runner.prepare_production_library(calyx, Path("calyx-library").resolve())
    raw = out / "compiler-raw.sv"
    command = [str(calyx / "bin/calyx"), str(out / "model.futil"),
               "-l", str(library), "-d", "cell-share", "-b", "verilog",
               "--synthesis", "--nested", "-o", str(raw)]
    with (out / "calyx.log").open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600, check=True)
    control = runner.annotate_bram_memories(raw.read_text())
    assert sha256(control) == CONTROL_SHA256, "one-ROM compiler SV differs from accepted control"
    runner.LUTRAM_MEMORIES = runner.LUTRAM_MEMORIES - {"c_proj_weight_codes_i8"}
    variant = runner.annotate_bram_memories(raw.read_text())
    instance = control.index(" c_proj_weight_codes_i8 (")
    start = control.rfind("seq_mem_d1_lutram # (", 0, instance)
    assert start >= 0, "missing c_proj LUTRAM instance"
    expected = control[:start] + "seq_mem_d1_bram" + control[start + len("seq_mem_d1_lutram"):]
    assert variant == expected, "two-ROM change exceeds the c_proj instance mapping"
    assert primitive_body(control, "seq_mem_d1_lutram") == primitive_body(control, "seq_mem_d1_bram")
    assert sha256(variant) == VARIANT_SHA256, "two-ROM compiler SV differs from accepted artifact"
    (out / "control.sv").write_text(control)
    (out / "model.sv").write_text(variant)
    (out / "generator-provenance.json").write_text(json.dumps(artifact.provenance, indent=2) + "\n")
    receipt = {
        "status": "source-rebuilt-accepted-two-rom-compiler-sv",
        "compiler_ir_sha256": sha256(artifact.futil),
        "control_sv_sha256": sha256(control),
        "variant_sv_sha256": sha256(variant),
        "changed_memory": "c_proj_weight_codes_i8",
        "primitive_behavior_identical": True,
        "limits": ["Compiler/Calyx stage only; model image, synthesis, route, bitstream and board not rebuilt."],
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
