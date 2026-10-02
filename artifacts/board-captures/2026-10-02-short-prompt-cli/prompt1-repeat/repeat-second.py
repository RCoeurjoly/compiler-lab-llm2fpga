"""Repeat the divergent prompt on the still-programmed image."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

root = Path.cwd()
sys.path.insert(0, str(root))
from scripts.pipeline.prompt_tinystories_generation_jtag import run_prompt
from scripts.pipeline.compare_tinystories_short_prompts import compare_receipts

campaign = root / "artifacts/board-captures/2026-10-02-short-prompt-cli"
output = campaign / "prompt1-repeat"
image = Path("/nix/store/mb1678v9k8cxwwrzsj9brzcms31b6v27-compiler-full16-two-rom-qualified-mode-checked-bitstream/model.bit")
reference = json.loads((root / "artifacts/reference/tinystories-short-prompt-software-2026-10-02.json").read_text())[1]
program = json.loads((campaign / "programming-receipt.json").read_text())
log = campaign / "program.log"
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
if output.exists() or sha(image) != program["image_sha256"] or sha(log) != program["log_sha256"]:
    raise SystemExit("programming evidence changed or repeat exists")
if Path("/sys/bus/thunderbolt/devices/1-1/authorized").read_text().strip() != "0":
    raise SystemExit("Thunderbolt isolation changed")
output.mkdir(parents=True)
shutil.copyfile(__file__, output / "repeat-second.py")
board = run_prompt(reference["text"], Path("/home/roland/kev-gpt/.worktrees/kintex-selftest/model_packages/tinystories-1m"),
                   Path("/home/roland/LLM2FPGA/scripts/task6"), "210299BF3824", 300,
                   output / "board.json")
print(f"transport={board['status']} tokens={board.get('tokens')} elapsed={board.get('elapsed_seconds')}", flush=True)
if board["status"] != "passed":
    raise SystemExit(1)
comparison = compare_receipts(board, reference, program, image, log)
(output / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
print(f"comparison={comparison['status']} first_mismatch={comparison['first_mismatch']}", flush=True)
