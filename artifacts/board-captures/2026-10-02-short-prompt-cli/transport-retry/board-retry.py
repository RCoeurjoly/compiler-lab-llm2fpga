"""Retry only the transport checks after validating the recorded SRAM program."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

root = Path.cwd()
sys.path.insert(0, str(root))
from scripts.pipeline.prompt_tinystories_generation_jtag import encode_prompt, load_tokenizer, run_prompt
from scripts.pipeline.compare_tinystories_short_prompts import compare_receipts

image = Path("/nix/store/mb1678v9k8cxwwrzsj9brzcms31b6v27-compiler-full16-two-rom-qualified-mode-checked-bitstream/model.bit")
tokenizer_dir = Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m")
transport_dir = Path("/home/roland/LLM2FPGA/scripts/task6")
serial = "210299BF3824"
accepted_sha = "bcf27e4da6abb290ad96a9d45618b0a3ef207fd5e35efbb2550996741c62426f"
reference_file = root / "artifacts/reference/tinystories-short-prompt-software-2026-10-02.json"
reference_sha = "18d20da48dfab82696756271a7e61e72df25df2ec42cdd82fb779c3270fa9e37"
campaign = root / "artifacts/board-captures/2026-10-02-short-prompt-cli"
output = campaign / "transport-retry"


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
program_log = campaign / "program.log"
program = json.loads((campaign / "programming-receipt.json").read_text())
if program["returncode"] != 0 or program["image_sha256"] != accepted_sha or program["serial"] != serial:
    raise SystemExit("recorded SRAM programming did not pass")
if program["log_sha256"] != sha(program_log):
    raise SystemExit("recorded SRAM programming log changed")
references = json.loads(reference_file.read_text())
tokenizer = load_tokenizer(tokenizer_dir)
if len(references) != 2 or any(encode_prompt(row["text"], tokenizer) != row["prompt_ids"] for row in references):
    raise SystemExit("candidate prompt encoding changed")

output.mkdir(parents=True)
shutil.copyfile(__file__, output / "board-retry.py")
results = []
for index, reference in enumerate(references):
    name = f"prompt{index}"
    raw_path = output / f"{name}-board.json"
    run = run_prompt(reference["text"], tokenizer_dir, transport_dir, serial, 300, raw_path)
    print(f"{name} transport: {run['status']} ({run.get('elapsed_seconds')})", flush=True)
    if run["status"] != "passed":
        results.append({"prompt": reference["text"], "status": "transport_failed", "error": run.get("error")})
        continue
    comparison = compare_receipts(run, reference, program, image, program_log)
    (output / f"{name}-comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    print(f"{name} comparison: {comparison['status']} first_mismatch={comparison['first_mismatch']}", flush=True)
    results.append({"prompt": reference["text"], "status": comparison["status"],
                    "first_mismatch": comparison["first_mismatch"]})

summary = {"schema": "tinystories-short-prompt-board-campaign-v1",
           "status": "passed" if len(results) == 2 and all(row["status"] == "passed" for row in results) else "failed",
           "image_sha256": accepted_sha, "software_reference_sha256": reference_sha,
           "programming_receipt_sha256": sha(campaign / "programming-receipt.json"),
           "results": results}
(output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2), flush=True)
raise SystemExit(0 if summary["status"] == "passed" else 1)
