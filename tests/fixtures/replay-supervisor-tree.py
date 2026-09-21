"""Harmless process tree for supervisor termination controls; no hardware."""
import os
import json
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import time

role, mode, directory = sys.argv[1:]
root = Path(directory)
if role == "descendant":
    if mode == "separate-group": os.setpgid(0, 0)
    if mode == "separate-session": os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (root / "descendant.pid").write_text(str(os.getpid()))
    while True: time.sleep(0.1)
elif role == "worker":
    (root / "worker.pid").write_text(str(os.getpid()))
    subprocess.Popen([sys.executable, __file__, "descendant", mode, directory])
    while not (root / "descendant.pid").exists(): time.sleep(0.01)
    if mode == "exit": sys.exit(1)
    if mode in ("separate-group", "separate-session"):
        (root / "receipt.json.worker.json").write_text(json.dumps({"status": "PASS", "stage": "complete"}))
        sys.exit(0)
    if mode == "interrupt-after-pass":
        (root / "receipt.json.worker.json").write_text(json.dumps({"status": "PASS", "stage": "complete"}))
    if mode in ("interrupt", "terminate", "interrupt-after-pass"):
        os.kill(os.getppid(), signal.SIGTERM if mode == "terminate" else signal.SIGINT)
    while True: time.sleep(0.1)
else:
    runner = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/pipeline/run_compiler_ddr3_trace_replay.py"))
    sys.exit(runner["supervise"]([sys.executable, __file__, "worker", mode, directory],
                               root / "receipt.json", 0.5 if mode == "timeout" else 5))
