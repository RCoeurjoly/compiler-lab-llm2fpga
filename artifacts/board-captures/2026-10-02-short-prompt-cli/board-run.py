"""One bounded SRAM program followed by two short-prompt board comparisons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

root = Path.cwd()
sys.path.insert(0, str(root))
from scripts.pipeline.prompt_tinystories_generation_jtag import encode_prompt, load_tokenizer, run_prompt
from scripts.pipeline.compare_tinystories_short_prompts import compare_receipts

image = Path("/nix/store/mb1678v9k8cxwwrzsj9brzcms31b6v27-compiler-full16-two-rom-qualified-mode-checked-bitstream/model.bit")
loader = Path("/nix/store/39xij3c8kp29nkldm436g8im3rqb8jaj-openfpgaloader-3ae5e5e-bpi-full-verify/bin/openFPGALoader")
tokenizer_dir = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
transport_dir = Path("/home/roland/LLM2FPGA/scripts/task6")
serial = "210299BF3824"
accepted_sha = "bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f"
reference_file = root / "artifacts/reference/tinystories-short-prompt-software-2026-10-02.json"
reference_sha = "18d20da48dfab82696756271a7e61e72df25df2ec42cdd82fb779c3270fa9e37"
output = root / "artifacts/board-captures/2026-10-02-short-prompt-cli"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if output.exists():
    raise SystemExit(f"refusing to overwrite {output}")
if sha(image) != accepted_sha or sha(reference_file) != reference_sha:
    raise SystemExit("image or software reference identity mismatch")
if Path("/sys/bus/thunderbolt/devices/1-1/authorized").read_text().strip() != "0":
    raise SystemExit("Thunderbolt isolation precondition changed")
if Path("/sys/bus/pci/devices/0000:42:00.0").exists():
    raise SystemExit("PCIe endpoint active; board not isolated for JTAG run")
references = json.loads(reference_file.read_text())
tokenizer = load_tokenizer(tokenizer_dir)
if len(references) != 2 or any(encode_prompt(row["text"], tokenizer) != row["prompt_ids"] for row in references):
    raise SystemExit("candidate prompt encoding changed")

output.mkdir(parents=True)
shutil.copyfile(__file__, output / "board-run.py")
log = output / "program.log"
command = [str(loader), "-c", "digilent_hs3", "--ftdi-serial", serial,
           "--freq", "1000000", "-m", str(image)]
program = {"command": command, "image_sha256": accepted_sha, "serial": serial,
           "returncode": None, "log_sha256": None}
(output / "programming-receipt.json").write_text(json.dumps(program, indent=2) + "\n")
started = time.monotonic()
with log.open("w") as stream:
    completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                               timeout=360, check=False)
program["returncode"] = completed.returncode
program["elapsed_seconds"] = time.monotonic() - started
program["log_sha256"] = sha(log)
(output / "programming-receipt.json").write_text(json.dumps(program, indent=2) + "\n")
if completed.returncode != 0:
    raise SystemExit(f"SRAM programming failed with code {completed.returncode}")
print(f"SRAM programmed in {program['elapsed_seconds']:.2f}s", flush=True)

results = []
for index, reference in enumerate(references):
    name = f"prompt{index}"
    raw_path = output / f"{name}-board.json"
    run = run_prompt(reference["text"], tokenizer_dir, transport_dir, serial, 300, raw_path)
    print(f"{name} transport: {run['status']} ({run.get('elapsed_seconds')})", flush=True)
    if run["status"] != "passed":
        results.append({"prompt": reference["text"], "status": "transport_failed",
                        "error": run.get("error")})
        continue
    comparison = compare_receipts(run, reference, program, image, log)
    (output / f"{name}-comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(f"{name} comparison: {comparison['status']} first_mismatch={comparison['first_mismatch']}", flush=True)
    results.append({"prompt": reference["text"], "status": comparison["status"],
                    "first_mismatch": comparison["first_mismatch"]})

summary = {"schema": "tinystories-short-prompt-board-campaign-v1",
           "status": "passed" if len(results) == 2 and all(row["status"] == "passed" for row in results) else "failed",
           "image_sha256": accepted_sha, "software_reference_sha256": reference_sha,
           "programming_receipt_sha256": sha(output / "programming-receipt.json"),
           "results": results}
(output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2), flush=True)
raise SystemExit(0 if summary["status"] == "passed" else 1)
