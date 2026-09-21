"""Controlled BAR device tests; no physical device or lifecycle writes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import subprocess
import sys
import signal
import ctypes
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class Device:
    def __init__(self, fault=None):
        self.fault = fault
        self.reg = {0: 0x54365043, 4: 3, 8: 0x61, 0x34: 3, 0x54: 23,
                    0x900: 0x52504c59, 0x904: 1, 0x928: 0, 0x92c: 3}
        self.memory = {}
        self.slots = {}
        self.commands = []
        self.blocked = 2 if fault == "backpressure" else 0
        if fault == "identity": self.reg[0] = 0
        if fault == "calibration": self.reg[0x34] = 0
        if fault == "bist_state": self.reg[0x54] = 18
        if fault == "stale": self.reg[0x928] = 2

    def rd32(self, address):
        if self.fault == "disappear" and self.commands:
            raise OSError("endpoint disappeared")
        if address == 0x92c and self.reg[0x928] == 1 and self.blocked:
            self.blocked -= 1
            return 1
        if address == 0x92c and self.fault == "timeout": return 1
        return self.reg.get(address, 0)

    def wr32(self, address, value):
        self.commands.append((address, value))
        self.reg[address] = value
        if address == 8: self.reg[8] = 0x61
        if address == 0x30:
            opcode = self.reg[0x14] & 255
            target = self.reg[0x18]
            data = struct.pack("<4I", *(self.reg[0x20 + i * 4] for i in range(4)))
            if opcode == 15: self.slots[target] = data
            elif opcode == 16:
                for i in range(target >> 29):
                    self.memory[(target & 0x1fffffff) + i] = self.slots[i]
            elif opcode == 6:
                data = self.memory[target]
                if self.fault == "readback": data = bytes(16)
            for i, word in enumerate(struct.unpack("<4I", data)):
                self.reg[0x44 + i * 4] = word
            self.reg[0xc] = self.reg.get(0xc, 0) + 1
            self.reg[8] = 0x65
            self.reg[0x34] = 0x37
        if address == 0x908 and value == 2:
            self.reg[0x928] = 0
            for a in (0x90c, 0x934, 0x938, 0x93c, 0x940, 0x944, 0x970): self.reg[a] = 0
        if address == 0x908 and value == 1:
            self.reg[0x928] = 2 if self.fault == "early_pass" else 1
        if address == 0x924:
            self.assert_record()
            for a in (0x934, 0x938, 0x93c, 0x940): self.reg[a] += 1
            if self.fault == "replay_fail":
                self.reg[0x928] = 3
                self.reg[0x944] = 1
                self.reg[0x948] = self.reg[0x940] - 1
                self.reg[0x94c] = self.reg[0x910]
        if address == 0x908 and value == 4:
            self.reg[0x928] = 2
            self.reg[0x92c] = 5

    def assert_record(self):
        assert self.reg[0x928] == 1
        assert self.reg[0x910] in self.memory
        expected = struct.pack("<4I", *(self.reg[0x914 + i * 4] for i in range(4)))
        assert expected == self.memory[self.reg[0x910]]


class Backend:
    def __init__(self, fault):
        self.device = Device(fault)
        self.events = []
        self.fault = fault

    def isolation(self):
        self.events.append("isolation")
        if self.fault == "isolation": raise RuntimeError("not isolated")
        return {"authorized": "0"}
    def prepare_isolation(self):
        self.events.append("prepare-isolation")
        if self.fault == "prepare-isolation": raise RuntimeError("isolation helper failed")
        return {"status": "isolated_for_programming"}
    def program(self):
        self.events.append("program")
        if self.fault == "verify": raise RuntimeError("BPI verification failed")
        return {"returncode": 0}
    def lifecycle(self):
        self.events.append("lifecycle")
        if self.fault == "bar": raise RuntimeError("missing BAR0")
        return {"classification": "pcie_ready"}
    def open(self): self.events.append("open"); return self.device
    def close(self): pass


class RunnerTest(unittest.TestCase):
    def test_hardware_mmio_uses_aligned_volatile_32_bit_accessor(self):
        spec = importlib.util.spec_from_file_location(
            "volatile_mmio_runner", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)

        class Function:
            def __init__(self, result=None):
                self.result = result
                self.calls = []
            def __call__(self, *args):
                self.calls.append(args)
                return self.result

        class Library:
            def __init__(self):
                self.ypcb_mmio_read32_be = Function(0x54365043)
                self.ypcb_mmio_write32_be = Function()

        backing = bytearray(4096)
        library = Library()
        accessor = runner.VolatileMmio32(backing, library)
        self.assertEqual(accessor.rd32(0), 0x54365043)
        accessor.wr32(4, 0x11223344)
        self.assertEqual(library.ypcb_mmio_read32_be.calls[0][1].value, 0)
        self.assertEqual(library.ypcb_mmio_write32_be.calls[0][1].value, 4)
        self.assertEqual(library.ypcb_mmio_write32_be.calls[0][2].value, 0x11223344)
        with self.assertRaisesRegex(ValueError, "aligned"):
            accessor.rd32(1)

        source = (ROOT / "scripts/host/ypcb_mmio32.c").read_text()
        self.assertIn("volatile uint32_t", source)
        self.assertIn("__atomic_signal_fence", source)

    def test_supervisor_reaps_entire_tree_and_records_interruptions(self):
        for mode in ("timeout", "interrupt", "terminate", "exit", "interrupt-after-pass", "separate-group", "separate-session"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                process = subprocess.Popen([sys.executable, str(ROOT / "tests/fixtures/replay-supervisor-tree.py"),
                                            "supervisor", mode, temporary], start_new_session=True,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    self.assertNotEqual(process.wait(timeout=12), 0)
                    output = root / "receipt.json"
                    self.assertTrue(output.exists(), "interrupted supervisor omitted atomic FAIL receipt")
                    receipt = json.loads(output.read_text())
                    self.assertEqual(receipt["status"], "FAIL")
                    self.assertFalse(list(root.glob("*.tmp")))
                    for name in ("worker", "descendant"):
                        pid = int((root / (name + ".pid")).read_text())
                        stat = Path(f"/proc/{pid}/stat")
                        self.assertFalse(stat.exists(), f"{name} {pid} remains alive/unreaped after {mode}")
                finally:
                    # Even a RED regression must never leak its harmless sleeper.
                    for name in ("worker", "descendant"):
                        path = root / (name + ".pid")
                        if path.exists():
                            try: os.kill(int(path.read_text()), signal.SIGKILL)
                            except ProcessLookupError: pass
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    process.wait(timeout=5)

    def test_supervisor_owns_final_receipt_and_preserves_worker_evidence(self):
        spec = importlib.util.spec_from_file_location("receipt_owner", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipt.json"
            worker = Path(str(output) + ".worker.json")
            script = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\",\"stage\":\"complete\"}}')"
            self.assertEqual(runner.supervise([sys.executable, "-c", script], output, 5), 0)
            self.assertEqual(json.loads(output.read_text())["status"], "PASS")
            self.assertEqual(json.loads(worker.read_text())["status"], "PASS")
            saved = output.read_bytes()
            self.assertEqual(runner.supervise(["/must-not-run"], output, 5), 1)
            self.assertEqual(output.read_bytes(), saved)

    def test_signal_during_cleanup_cannot_publish_pass(self):
        spec = importlib.util.spec_from_file_location("cleanup_signal", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipt.json"
            worker = Path(str(output) + ".worker.json")
            script = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\"}}')"
            original = runner.stop_process_group
            def interrupted_cleanup(*args, **kwargs):
                os.kill(os.getpid(), signal.SIGTERM)
                return original(*args, **kwargs)
            with patch.object(runner, "stop_process_group", side_effect=interrupted_cleanup):
                self.assertEqual(runner.supervise([sys.executable, "-c", script], output, 5), 1)
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(receipt["supervisor"]["interrupted_signal"], "SIGTERM")

    def test_publication_window_interruptions_force_atomic_fail(self):
        for phase in ("entry", "fsync", "link"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temporary:
                spec = importlib.util.spec_from_file_location("publication_signal", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
                runner = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(runner)
                output = Path(temporary) / "receipt.json"
                worker = Path(str(output) + ".worker.json")
                script = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\"}}')"
                owner, name = (runner, "atomic_receipt") if phase == "entry" else (runner.os, phase)
                original = getattr(owner, name)
                injected = False
                def interrupt_once(*args, **kwargs):
                    nonlocal injected
                    if not injected:
                        injected = True
                        os.kill(os.getpid(), signal.SIGTERM)
                    return original(*args, **kwargs)
                with patch.object(owner, name, side_effect=interrupt_once):
                    self.assertEqual(runner.supervise([sys.executable, "-c", script], output, 5), 1)
                receipt = json.loads(output.read_text())
                self.assertEqual(receipt["status"], "FAIL")
                self.assertEqual(receipt["supervisor"]["interrupted_signal"], "SIGTERM")
                self.assertFalse(list(Path(temporary).glob("*.tmp")))

    def test_signal_after_publication_preserves_completed_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipt.json"
            worker = Path(str(output) + ".worker.json")
            child = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\"}}')"
            script = f'''import os,runpy,signal,sys
m=runpy.run_path({str(ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")!r})
original=m["supervise"].__globals__["atomic_receipt"]
def after_commit(*args):
    original(*args)
    os.kill(os.getpid(), signal.SIGTERM)
m["supervise"].__globals__["atomic_receipt"]=after_commit
m["supervise"]([sys.executable,"-c",{child!r}],{str(output)!r},5)
'''
            result = subprocess.run([sys.executable, "-c", script], timeout=10)
            self.assertEqual(result.returncode, -signal.SIGTERM)
            self.assertEqual(json.loads(output.read_text())["status"], "PASS")

    def test_bpi_full_verify_precedes_cycle_and_ready_identity(self):
        spec = importlib.util.spec_from_file_location("bpi_runner", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for fault in (None, "program", "prefix", "short", "cycle", "boot", "probe", "identity", "bar"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                from tests.test_replay_runtime_lifecycle import fixture, sha
                runtime_paths, runtime_root, runtime_document, runtime_manifest = fixture(root)
                tb = root / "thunderbolt/1-1"
                tb.mkdir(parents=True)
                pci = root / "pci"
                pci.mkdir()
                for key, value in {"device_name": "Helios 5S", "unique_id": "c4148780-0010-1ed9-ffff-ffffffffffff", "authorized": "0"}.items():
                    (tb / key).write_text(value)
                boot = root / "boot_id"
                boot.write_text("same-boot")
                config = {"program_mode": "bpi", "bpi_verification": "full-readback-v1",
                          "bitstream_payload_bytes": 9001, "programmer": "/qualified/programmer",
                          "artifacts": {"bitstream": {"path": "/authenticated.bit"}},
                          "lifecycle_probe": "/read-only/probe", "log_prefix": str(root / "receipt.json"),
                          "lifecycle_timeout": 0, "program_timeout": 1}
                backend = runner.HardwareBackend(config)
                backend.thunderbolt_root, backend.pci_root, backend.boot_id_path = root / "thunderbolt", pci, boot
                events = []
                def execute(argv, **kwargs):
                    if argv[0] == "/qualified/programmer":
                        self.assertNotIn("OPENFPGALOADER_SOJ_DIR", kwargs.get("env", {"OPENFPGALOADER_SOJ_DIR": "untrusted"}))
                        events.append("program")
                        self.assertEqual(argv[1:-1], ["-b", "ypcb003381p1", "-c", "digilent_hs3", "--ftdi-serial", "210299BF3824", "--write-flash", "--verify"])
                        self.assertEqual((tb / "authorized").read_text(), "0")
                        output = "Writing 9001 bytes to BPI flash at 0x000000\nBPI full verification passed: 9001 bytes at 0x00000000\n"
                        if fault == "prefix": output = "Verification passed for first 32 words\n"
                        if fault == "short": output = output.replace("passed: 9001", "passed: 64")
                        code = 1 if fault == "program" else 0
                    elif argv[0] == "sudo":
                        events.append("cycle")
                        self.assertEqual(argv, ["sudo", "-n", "/usr/local/sbin/ypcb-thunderbolt-cold-cycle"])
                        (tb / "authorized").write_text("1")
                        if fault == "boot": boot.write_text("new-boot")
                        endpoint = pci / "0000:07:00.0"
                        endpoint.mkdir()
                        for key, value in {"vendor": "0x10ee", "device": "0x0480", "subsystem_vendor": "0x10ee", "subsystem_device": "0xabcd"}.items():
                            (endpoint / key).write_text(value)
                        if fault == "identity": (endpoint / "subsystem_device").write_text("0xffff")
                        if fault != "bar": (endpoint / "resource0").write_bytes(bytes(4096))
                        output, code = '{}\n', 1 if fault == "cycle" else 0
                    else:
                        events.append("probe")
                        self.assertEqual(argv[0], str(runtime_paths['controller_python']))
                        self.assertEqual(argv[1:5], ['-I', '-S', '-B', '-c'])
                        self.assertEqual(json.loads(argv[-1])['lifecycle_dependency'],
                                         runtime_document['artifacts']['lifecycle_dependency'])
                        output = json.dumps({"classification": "missing_endpoint" if fault == "probe" else "pcie_ready", "actions": []})
                        code = 1 if fault == "probe" else 0
                    if "stdout" in kwargs: kwargs["stdout"].write(output)
                    return subprocess.CompletedProcess(argv, code, output, "")
                config['artifacts']['runtime_manifest'] = {
                    'path': str(runtime_manifest), 'sha256': sha(runtime_manifest)}
                config['artifacts'].update(runtime_document['artifacts'])
                with patch.object(runner.subprocess, "run", side_effect=execute), \
                     patch.object(runner, 'LIFECYCLE_PATHS', runtime_paths), \
                     patch.object(runner, 'LIFECYCLE_RUNTIME_ROOT', runtime_root):
                    with self.assertRaisesRegex(RuntimeError, "verif"):
                        backend.lifecycle()
                    self.assertEqual(events, [])
                    if fault is None:
                        backend.program()
                        self.assertEqual(backend.lifecycle()["classification"], "pcie_ready")
                        self.assertEqual(events, ["program", "cycle", "probe"])
                    else:
                        with self.assertRaises((RuntimeError, OSError, TimeoutError)):
                            backend.program()
                            backend.lifecycle()
                        if fault in ("program", "prefix", "short"): self.assertEqual(events, ["program"])
                        if fault in ("cycle", "boot"): self.assertEqual(events, ["program", "cycle"])

    def test_sram_and_incomplete_bpi_verifier_cannot_invoke_programmer(self):
        spec = importlib.util.spec_from_file_location("program_mode_runner", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for mode in (None, "sram", "bpi"):
            with self.subTest(mode=mode):
                backend = runner.HardwareBackend({"program_mode": mode,
                    "programmer": "/home/roland/openFPGALoader/build/openFPGALoader",
                    "artifacts": {"bitstream": {"path": "/authenticated.bit"}}})
                with patch.object(backend, "isolation", return_value={"authorized": "0"}), \
                     patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as command:
                    with self.assertRaisesRegex(RuntimeError, "BPI|SRAM|verification"):
                        backend.program()
                    command.assert_not_called()

    def test_program_fails_closed_without_exact_isolation(self):
        spec = importlib.util.spec_from_file_location("isolated_runner", ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for fault in ("authorized", "missing", "name", "uuid", "unreadable", "endpoint"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                tb = root / "thunderbolt" / "1-1"
                tb.mkdir(parents=True)
                pci = root / "pci"
                pci.mkdir()
                for name, value in {"authorized": "0", "device_name": "Helios 5S",
                                    "unique_id": "c4148780-0010-1ed9-ffff-ffffffffffff"}.items():
                    (tb / name).write_text(value)
                if fault == "authorized": (tb / "authorized").write_text("1")
                if fault == "missing": (tb / "authorized").unlink()
                if fault == "name": (tb / "device_name").write_text("Other chassis")
                if fault == "uuid": (tb / "unique_id").write_text("wrong")
                if fault == "unreadable":
                    (tb / "authorized").unlink()
                    (tb / "authorized").mkdir()
                if fault == "endpoint":
                    endpoint = pci / "0000:07:00.0"
                    endpoint.mkdir()
                    (endpoint / "vendor").write_text("0x10ee")
                    (endpoint / "device").write_text("0x0480")
                backend = runner.HardwareBackend({"program_mode": "bpi", "programmer": "/nonexistent/programmer",
                                                  "artifacts": {"bitstream": {"path": "/authenticated.bit"}}})
                backend.thunderbolt_root = root / "thunderbolt"
                backend.pci_root = pci
                with patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")) as command:
                    with self.assertRaises((RuntimeError, OSError)):
                        backend.program()
                    command.assert_not_called()

    def test_bitstream_receipt_authenticates_current_artifacts_without_hardware_claim(self):
        path = ROOT / "artifacts/reference/compiler-ddr3-trace-replay-bitstream.json"
        self.assertTrue(path.exists(), "Task 4 bitstream provenance receipt is missing")
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["status"], "ROUTE_AND_BITSTREAM_PASS")
        self.assertFalse(receipt["hardware_qualified"])
        self.assertEqual(receipt["route"]["checksum"], "0xf9db6456")
        # Historical execution-tool hashes are not current runtime authority.
        # The new runtime-only manifest is checked separately; build evidence
        # and this original receipt must never be rewritten to follow installs.
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '9ffb546ff379ba3461a8819768250d8f93054dd046eb610c5f6be3ad820a76b7')
        for name, artifact in receipt["artifacts"].items():
            if name in ('runner', 'cold_cycle_wrapper', 'cold_cycle_controller',
                        'lifecycle_probe', 'lifecycle_dependency'):
                continue
            target = Path(artifact["path"])
            self.assertEqual(target.stat().st_size, artifact["bytes"], name)
            with target.open("rb") as stream:
                self.assertEqual(hashlib.file_digest(stream, "sha256").hexdigest(), artifact["sha256"], name)

    def test_worker_signal_or_timeout_produces_atomic_failed_receipt(self):
        path = ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py"
        spec = importlib.util.spec_from_file_location("replay_runner_supervise", path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        self.assertTrue(hasattr(runner, "supervise"), "BAR worker needs signal-safe receipt supervision")
        for script, timeout in [("import os,signal; os.kill(os.getpid(), signal.SIGBUS)", 5),
                                ("import time; time.sleep(10)", 0.01), ("pass", 5)]:
            with self.subTest(script=script), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "receipt.json"
                self.assertNotEqual(runner.supervise([sys.executable, "-c", script], output, timeout), 0)
                self.assertEqual(json.loads(output.read_text())["status"], "FAIL")
                self.assertFalse(list(Path(temporary).glob("*.tmp")))
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "receipt.json"
            snapshot = Path(str(output) + ".snapshot.json")
            snapshot.write_text(json.dumps({"status": "RUNNING", "stage": "load", "load": {"bytes_loaded": 64}}))
            script = "import os,signal; os.kill(os.getpid(), signal.SIGBUS)"
            self.assertNotEqual(runner.supervise([sys.executable, "-c", script], output, 5), 0)
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt.get("load"), {"bytes_loaded": 64})
            self.assertEqual(receipt.get("last_stage"), "load")

    def test_bar_wire_order_preserves_all_ones_payload_and_flushes_writes(self):
        path = ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py"
        spec = importlib.util.spec_from_file_location("replay_runner_bar", path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        backend = runner.HardwareBackend({})
        backend.mapping = bytearray(4096)
        class ByteMmio:
            def rd32(self, offset):
                return struct.unpack_from(">I", backend.mapping, offset)[0]
            def wr32(self, offset, value):
                struct.pack_into(">I", backend.mapping, offset, value)
        backend.mmio = ByteMmio()
        backend.mapping[:4] = bytes.fromhex("54365043")
        backend.mapping[0x44:0x48] = bytes.fromhex("ffffffff")
        self.assertEqual(backend.rd32(0x44), 0xffffffff)
        backend.wr32(0x910, 0x12345678)
        self.assertEqual(backend.mapping[0x910:0x914], bytes.fromhex("12345678"))
        backend.mapping[:4] = bytes.fromhex("ffffffff")
        with self.assertRaises(OSError): backend.wr32(0x910, 1)

    def test_cli_rejects_nonproduction_package_with_atomic_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "package.json"
            package.write_text('{"record_count": 2}')
            output = root / "failed.json"
            command = [sys.executable, str(ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py"),
                       "--package", str(package), "--bitstream-receipt", str(package),
                       "--image", str(package), "--receipt", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, "CLI must not silently accept missing entrypoint")
            self.assertEqual(json.loads(output.read_text())["status"], "FAIL")

    def test_order_full_readback_backpressure_and_atomic_failures(self):
        path = ROOT / "scripts/pipeline/run_compiler_ddr3_trace_replay.py"
        self.assertTrue(path.exists(), "streaming hardware gate runner is missing")
        spec = importlib.util.spec_from_file_location("replay_runner", path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        for fault in (None, "backpressure", "prepare-isolation", "isolation", "verify", "identity", "bar", "calibration", "bist_state", "image_hash",
                      "readback", "early_pass", "replay_fail", "timeout", "disappear", "stale"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                image = bytes(range(32))
                binary = struct.pack("<I", 0) + image[:16] + struct.pack("<I", 1) + image[16:]
                artifacts = {}
                for name, data in [("image", image), ("replay", binary), ("bitstream", b"bit"), ("source", b"source")]:
                    target = root / name
                    target.write_bytes(data)
                    artifacts[name] = {"path": str(target), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                if fault == "image_hash": artifacts["image"]["sha256"] = "0" * 64
                config = {"artifacts": artifacts, "record_count": 2, "image_bytes": 32,
                          "timeout": 0.01, "boot_timeout": 0.01, "poll_interval": 0}
                backend = Backend(fault)
                output = root / "receipt.json"
                status = runner.run_gate(config, backend, output)
                receipt = json.loads(output.read_text())
                if fault in (None, "backpressure"):
                    self.assertEqual(status, 0)
                    self.assertEqual(receipt["status"], "PASS")
                    self.assertEqual(receipt["load"]["bytes_read_back"], 32)
                    self.assertEqual(receipt["load"]["sha256_readback"], hashlib.sha256(image).hexdigest())
                    self.assertEqual(receipt["replay"]["checked"], 2)
                    self.assertEqual(backend.events[:5], ["prepare-isolation", "isolation", "program", "lifecycle", "open"])
                    writes = backend.device.commands
                    clear_index = writes.index((0x908, 2))
                    self.assertEqual(sum(a == 0x14 and v == 6 for a, v in writes[:clear_index]), 2)
                else:
                    self.assertNotEqual(status, 0)
                    self.assertEqual(receipt["status"], "FAIL")
                    self.assertTrue(receipt["error"])
                    self.assertFalse(any(root.glob("*.tmp")))
                    if fault == "image_hash": self.assertEqual(backend.events, [])
                    if fault == "prepare-isolation": self.assertEqual(backend.events, ["prepare-isolation"])
                    if fault == "isolation": self.assertEqual(backend.events, ["prepare-isolation", "isolation"])
                    if fault == "verify": self.assertEqual(backend.events, ["prepare-isolation", "isolation", "program"])
                    if fault == "replay_fail":
                        self.assertEqual(receipt["replay"]["first_index"], 0)
                        self.assertEqual(receipt["replay"]["errors"], 1)
                    if fault in ("stale", "readback", "calibration"):
                        self.assertNotIn((0x908, 2), backend.device.commands)
                original = output.read_bytes()
                self.assertNotEqual(runner.run_gate(config, backend, output), 0)
                self.assertEqual(output.read_bytes(), original, "first receipt must never be replaced")


if __name__ == "__main__": unittest.main()
