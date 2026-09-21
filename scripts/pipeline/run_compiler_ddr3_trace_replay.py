"""Ordered full-image load/readback and exact compiler-derived DDR3 replay gate.

This is a transport diagnostic, not accelerator inference. BAR word encoding
belongs to the device adapter; replay records are little-endian <5I.
"""
import hashlib
import argparse
import ctypes
from contextlib import contextmanager
import errno
import json
import mmap
import os
import resource
import re
import signal
import shutil
import stat
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time


LIFECYCLE_RUNTIME_ROOT = Path('/home/roland/.local/share/ypcb-tapo-runtime/venv')
LIFECYCLE_PATHS = {
    'runner': Path(__file__).resolve(),
    'cold_cycle_wrapper': Path('/usr/local/sbin/ypcb-thunderbolt-cold-cycle'),
    'cold_cycle_controller': Path('/usr/local/libexec/ypcb_thunderbolt_deferred_auth.py'),
    'lifecycle_probe': Path('/usr/local/libexec/ypcb_pcie_recover.py'),
    'lifecycle_dependency': Path('/usr/local/libexec/ypcb_pcie_power.py'),
    'tapo_wrapper': Path('/usr/local/libexec/ypcb-tapo-cycle'),
    'tapo_power_script': Path('/usr/local/libexec/ypcb_tapo_p115_power.py'),
    'controller_python': Path('/usr/bin/python3'),
    'tapo_python': LIFECYCLE_RUNTIME_ROOT / 'bin/python',
}
MIN_FREE_BYTES = 64 << 20
EVIDENCE_SLOT_BYTES = 1 << 20
MAX_RECEIPT_BYTES = 256 << 10
MAX_COMMAND_LOG_BYTES = 1 << 20
MAX_TOTAL_LOG_BYTES = 8 << 20

# -I -S -B removes environment/site/current-directory import influence. Compile
# authenticated source bytes directly, never loading a stale/unpinned pyc.
PROBE_BOOTSTRAP = '''import hashlib,json,sys,types
artifacts=json.loads(sys.argv[1])
def source(name):
    row=artifacts[name]
    with open(row['path'],'rb') as stream: data=stream.read()
    if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
        raise RuntimeError(name+' changed before isolated probe execution')
    return compile(data,row['path'],'exec')
dependency=source('lifecycle_dependency')
probe=source('lifecycle_probe')
package=types.ModuleType('tools');package.__path__=[]
module=types.ModuleType('tools.ypcb_pcie_power')
module.__file__=artifacts['lifecycle_dependency']['path']
sys.modules['tools']=package
sys.modules['tools.ypcb_pcie_power']=module
sys.modules['ypcb_pcie_power']=module
package.ypcb_pcie_power=module
exec(dependency,module.__dict__)
sys.argv=[artifacts['lifecycle_probe']['path']]
entry=types.ModuleType('__main__');entry.__file__=sys.argv[0]
sys.modules['__main__']=entry
exec(probe,entry.__dict__)
'''


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def authenticate_runtime_lifecycle(path, expected_sha256):
    """Authenticate runtime separately from immutable historical build evidence.

    The caller supplies the reviewed manifest SHA; a manifest cannot choose new
    executable paths or supersede bitstream/programmer/build identities. No
    imports, resolver, credentials or device operations are used here.
    """
    if not path or not expected_sha256:
        raise ValueError('explicit lifecycle manifest path and SHA-256 required')
    path = Path(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('runtime lifecycle manifest hash mismatch')
    document = json.loads(raw)
    if document.get('schema') != 'pcie-runtime-lifecycle-manifest-v1':
        raise ValueError('wrong runtime lifecycle manifest schema')
    artifacts = document['artifacts']
    if set(artifacts) != set(LIFECYCLE_PATHS):
        raise ValueError('runtime lifecycle artifact set mismatch')
    for name, executed_path in LIFECYCLE_PATHS.items():
        artifact = artifacts[name]
        if artifact['path'] != str(executed_path):
            raise ValueError(name + ' does not authenticate the executed path')
        if executed_path.stat().st_size != artifact['bytes'] or digest(executed_path) != artifact['sha256']:
            raise ValueError(name + ' runtime artifact hash/size mismatch')
    tree = document['runtime_tree']
    if tree['path'] != str(LIFECYCLE_RUNTIME_ROOT):
        raise ValueError('runtime tree path mismatch')
    rows = []
    for entry in sorted(LIFECYCLE_RUNTIME_ROOT.rglob('*')):
        relative = str(entry.relative_to(LIFECYCLE_RUNTIME_ROOT))
        if entry.is_symlink():
            rows.append([relative, 'symlink', entry.readlink().as_posix()])
        elif entry.is_file():
            size, sha256 = entry.stat().st_size, digest(entry)
            rows.append([relative, size, sha256])
            artifacts['runtime:' + relative] = {'path': str(entry), 'bytes': size, 'sha256': sha256}
        elif not entry.is_dir():
            raise ValueError('unexpected special runtime file')
    actual = hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()
    if len(rows) != tree['entries'] or actual != tree['sha256']:
        raise ValueError('fixed Tapo runtime tree changed or is missing')
    artifacts['runtime_manifest'] = {'path': str(path.resolve()), 'bytes': len(raw),
                                     'sha256': expected_sha256, 'runtime_tree': tree}
    return artifacts


def bind_runtime_lifecycle(build_artifacts, path, expected_sha256):
    # Copy, never rewrite historical receipts. Only the fixed runtime keys can
    # replace historical entries; every other build artifact remains a gate.
    artifacts = dict(build_artifacts)
    artifacts.update(authenticate_runtime_lifecycle(path, expected_sha256))
    return artifacts


def atomic_receipt(path, receipt):
    """Install one complete receipt without replacing earlier evidence."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def checkpoint(receipt):
    """Durable latest progress, separate from the never-overwritten receipt."""
    if "checkpoint_path" not in receipt:
        return
    path = Path(receipt["checkpoint_path"])
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(receipt, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


BASE_ATOMIC = atomic_receipt
BASE_CHECKPOINT = checkpoint


def admit_disk(receipt_directory, extra=0):
    observed = {}
    for path in (Path(receipt_directory), LIFECYCLE_RUNTIME_ROOT):
        free = shutil.disk_usage(path).free
        observed[str(path)] = free
        if free < MIN_FREE_BYTES + extra:
            raise RuntimeError(f'insufficient disk headroom at {path}: {free}; require {MIN_FREE_BYTES + extra}')
    return {'minimum_free_bytes': MIN_FREE_BYTES, 'observed_free_bytes': observed}


class EvidenceReserve:
    """Continuation-reviewed physical reserve, adapted for repeated replay snapshots.

    One released 1MiB snapshot slot covers old+temporary 256KiB checkpoints.
    Each replacement reuses that capacity; terminal/emergency slots stay held.
    ENOSPC at any later checkpoint stops the run and uses terminal capacity.
    This cannot defend against concurrent writers consuming released space or
    arbitrary filesystem failure; each terminal publication has one emergency.
    """
    slots = ('snapshot-0', 'snapshot-1', 'snapshot-2', 'worker-final',
             'worker-emergency', 'parent-final', 'parent-emergency', 'cleanup')

    def __init__(self, output, *, create):
        self.directory = Path(str(output) + '.reserve')
        self.snapshot_started = False
        self.admission = admit_disk(Path(output).parent, len(self.slots) * EVIDENCE_SLOT_BYTES if create else 0)
        if create:
            self.directory.mkdir(mode=0o700)
            try:
                for name in self.slots:
                    fd = os.open(self.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    try:
                        os.posix_fallocate(fd, 0, EVIDENCE_SLOT_BYTES)
                        os.fsync(fd)
                    finally: os.close(fd)
                self.validate()
                self.sync_directory()
            except BaseException:
                self.close()
                raise
        else:
            self.validate()

    def sync_directory(self):
        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)

    def validate(self):
        directory = self.directory.lstat()
        if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.getuid():
            raise RuntimeError('invalid evidence reserve directory')
        for name in self.slots:
            info = (self.directory / name).lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or info.st_size != EVIDENCE_SLOT_BYTES
                    or info.st_blocks * 512 < EVIDENCE_SLOT_BYTES):
                raise RuntimeError('missing/nonallocated evidence reserve slot ' + name)

    def release(self, name, *, required=False):
        path = self.directory / name
        try: info = path.lstat()
        except FileNotFoundError:
            if required: raise RuntimeError('evidence reserve already consumed: ' + name)
            return
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise RuntimeError('refusing changed evidence reserve slot ' + name)
        path.unlink()
        self.sync_directory()

    def close(self):
        if not self.directory.exists(): return
        for name in self.slots: self.release(name)
        self.directory.rmdir()

    def bounded(self, receipt, *, terminal):
        receipt['evidence_capacity'] = {'reserved_bytes': len(self.slots) * EVIDENCE_SLOT_BYTES,
            'maximum_receipt_bytes': MAX_RECEIPT_BYTES, 'minimum_runtime_headroom_bytes': MIN_FREE_BYTES}
        data = json.dumps(receipt, indent=2, sort_keys=True).encode()
        if len(data) <= MAX_RECEIPT_BYTES: return
        if not terminal: raise RuntimeError('snapshot exceeds reserved evidence bound')
        identities = {name: row for name, row in receipt.get('artifacts', {}).items()
                      if name in ('source', 'runtime_manifest', 'runner')}
        receipt.clear()
        receipt.update(status='FAIL', stage='evidence_bound',
                       error='terminal receipt exceeds reserved evidence bound',
                       oversized_receipt_sha256=hashlib.sha256(data).hexdigest(), artifacts=identities)

    @contextmanager
    def protect(self, *, worker):
        global atomic_receipt, checkpoint
        role = 'worker' if worker else 'parent'
        previous_atomic, previous_checkpoint = atomic_receipt, checkpoint
        def snapshot(receipt):
            if not worker: raise RuntimeError('parent cannot consume worker snapshot capacity')
            self.bounded(receipt, terminal=False)
            if not self.snapshot_started:
                self.release('snapshot-0', required=True)
                self.snapshot_started = True
            BASE_CHECKPOINT(receipt)
        def publish(path, receipt):
            self.bounded(receipt, terminal=True)
            self.release(role + '-final')
            try:
                BASE_ATOMIC(path, receipt)
            except OSError as error:
                if error.errno != errno.ENOSPC or Path(path).exists(): raise
                receipt.update(status='FAIL', error='ENOSPC during terminal publication; emergency reserve used')
                self.release(role + '-emergency', required=True)
                BASE_ATOMIC(path, receipt)
            else:
                self.release(role + '-emergency')
        atomic_receipt, checkpoint = publish, snapshot
        try: yield
        finally: atomic_receipt, checkpoint = previous_atomic, previous_checkpoint


class OwnedProcessTree:
    """Linux subreaper plus pidfds: children cannot escape by changing PGID/SID."""
    def __init__(self):
        self.parent = os.getpid()
        self.owned = {}
        self.signal_denials = []
        if any(value["ppid"] == self.parent for value in self.snapshot().values()):
            raise RuntimeError("supervisor requires no pre-existing child processes")
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.previous = ctypes.c_int()
        if self.libc.prctl(37, ctypes.byref(self.previous), 0, 0, 0):  # GET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "cannot read subreaper state")
        if self.libc.prctl(36, 1, 0, 0, 0):  # SET_CHILD_SUBREAPER
            raise OSError(ctypes.get_errno(), "cannot own orphan descendants")

    @staticmethod
    def information(pid):
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"state": fields[0], "ppid": int(fields[1]), "pgid": int(fields[2]),
                "sid": int(fields[3]), "start": int(fields[19])}

    def snapshot(self):
        result = {}
        for path in Path("/proc").iterdir():
            if path.name.isdigit():
                try:
                    result[int(path.name)] = self.information(int(path.name))
                except (FileNotFoundError, ProcessLookupError):
                    pass
                except PermissionError:
                    if int(path.name) in self.owned: raise
        return result

    def discover(self):
        current = self.snapshot()
        parents = {self.parent}
        while True:
            added = {pid for pid, info in current.items() if info["ppid"] in parents} - parents
            if not added: break
            parents.update(added)
        # This standalone supervisor launches exactly one child. Orphaned
        # grandchildren are adopted here even after setsid()/double-fork.
        for pid in parents - {self.parent}:
            info = current[pid]
            old = self.owned.get(pid)
            if old is not None and old["start"] == info["start"]: continue
            fd = None
            try:
                fd = os.pidfd_open(pid)
                if self.information(pid)["start"] != info["start"]:
                    os.close(fd)
                    continue
            except ProcessLookupError:
                continue
            except FileNotFoundError:
                if fd is not None: os.close(fd)
                continue
            if old is not None: os.close(old["fd"])
            self.owned[pid] = dict(info, fd=fd)
        return {pid: info for pid, info in current.items() if pid in self.owned
                and info["start"] == self.owned[pid]["start"] and info["state"] != "Z"}

    def reap(self, process):
        process.poll()
        for pid in self.owned:
            if pid != process.pid:
                try: os.waitpid(pid, os.WNOHANG)
                except ChildProcessError: pass

    def close(self):
        for info in self.owned.values(): os.close(info["fd"])
        if self.libc.prctl(36, self.previous.value, 0, 0, 0):
            raise OSError(ctypes.get_errno(), "cannot restore subreaper state")


def stop_process_group(process, tree, grace=1):
    """Bound TERM→KILL over the complete owned tree, repeatedly closing fork races."""
    terminated = False
    for sig in (signal.SIGTERM, signal.SIGKILL):
        sent = set()
        deadline = time.monotonic() + grace
        while True:
            live = tree.discover()
            tree.reap(process)
            if not live:
                # Recheck after reaping: subreaper adoption can expose a child
                # whose parent exited during the previous /proc enumeration.
                if not tree.discover():
                    tree.reap(process)
                    process.wait(timeout=grace)
                    return terminated
                continue
            terminated = True
            for pid, info in live.items():
                identity = (pid, info["start"])
                if identity not in sent:
                    try: signal.pidfd_send_signal(tree.owned[pid]["fd"], sig)
                    except ProcessLookupError: pass
                    except PermissionError:
                        # sudo's unprivileged monitor forwards signals to its
                        # privileged command group. Never assume that succeeded:
                        # repeated enumeration must prove every child has exited.
                        tree.signal_denials.append({"pid": pid, "start": info["start"], "signal": sig.name})
                    sent.add(identity)
            if time.monotonic() >= deadline: break
            time.sleep(0.01)
    tree.reap(process)
    live = tree.discover()
    if live: raise RuntimeError(f"owned processes remain after TERM/KILL: {live}")
    process.wait(timeout=grace)
    return terminated


def supervise(command, output, timeout):
    """Own the worker session and final receipt, including interrupt/SIGBUS paths."""
    if Path(output).exists():
        return 1
    started = time.monotonic()
    worker_receipt = Path(str(output) + ".worker.json")
    process = None
    tree = None
    status = 1
    error = None
    interrupted_signal = None
    previous = {}
    cleanup = {}
    def interrupted(signum, frame):
        nonlocal interrupted_signal
        interrupted_signal = signal.Signals(signum).name
        raise KeyboardInterrupt(interrupted_signal)
    def record_interrupt(signum, frame):
        nonlocal interrupted_signal
        interrupted_signal = signal.Signals(signum).name
    def publication_interrupt(signum, frame):
        # Successful no-overwrite link in atomic_receipt is the linearization
        # point. A signal observed after that publication belongs to the caller,
        # not to the completed hardware gate: restore/forward its disposition.
        if Path(output).exists():
            signal.signal(signum, previous[signum])
            os.kill(os.getpid(), signum)
            return
        record_interrupt(signum, frame)
        # Interrupt a PASS temporary write/fsync/pre-link, then let the failure
        # receipt finish even if further signals arrive during its publication.
        for sig in previous: signal.signal(sig, record_interrupt)
        raise KeyboardInterrupt(interrupted_signal)
    try:
        try:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                previous[sig] = signal.signal(sig, interrupted)
            if worker_receipt.exists():
                raise FileExistsError("existing worker receipt; choose a fresh receipt path")
            tree = OwnedProcessTree()
            launch_mask = signal.pthread_sigmask(signal.SIG_BLOCK, tuple(previous))
            def no_core():
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                signal.pthread_sigmask(signal.SIG_SETMASK, launch_mask)
            try:
                process = subprocess.Popen(command, start_new_session=True, preexec_fn=no_core)
            finally:
                # Deliver pending interrupts only once the session is owned.
                signal.pthread_sigmask(signal.SIG_SETMASK, launch_mask)
            status = process.wait(timeout=timeout)
            if status:
                error = f"hardware worker exit {status} (negative value is terminating signal)"
        except subprocess.TimeoutExpired:
            error = "hardware worker deadline exceeded"
        except KeyboardInterrupt:
            error = "hardware supervisor interrupted: " + (interrupted_signal or "KeyboardInterrupt")
        except Exception as failure:
            error = f"hardware supervisor failure: {type(failure).__name__}: {failure}"
        finally:
            # Record every cleanup interruption without unwinding cleanup.
            for sig in previous: signal.signal(sig, record_interrupt)
            if process is not None:
                try:
                    cleanup["group_terminated"] = stop_process_group(process, tree)
                    cleanup["worker_returncode"] = process.returncode
                    if cleanup["group_terminated"] and error is None:
                        error = "hardware worker left descendants running"
                except Exception as failure:
                    cleanup["error"] = str(failure)
                    error = error or "hardware process-group cleanup failed"
            if tree is not None:
                cleanup["owned_processes"] = [{"pid": pid, "start": info["start"],
                                               "sid": info["sid"], "pgid": info["pgid"]}
                                              for pid, info in tree.owned.items()]
                cleanup["signal_denials"] = tree.signal_denials
                try: tree.close()
                except Exception as failure:
                    cleanup["close_error"] = str(failure)
                    error = error or "hardware process-tree ownership cleanup failed"
                finally: tree = None
        receipt = {}
        for path in (worker_receipt, Path(str(worker_receipt) + ".snapshot.json"),
                     Path(str(output) + ".snapshot.json")):
            if path.exists():
                try:
                    receipt = json.loads(path.read_text())
                    break
                except (OSError, ValueError) as failure:
                    error = error or f"invalid worker evidence: {failure}"
        if interrupted_signal:
            error = "hardware supervisor interrupted: " + interrupted_signal
        if error or status != 0 or receipt.get("status") != "PASS":
            receipt.update({"status": "FAIL", "last_stage": receipt.get("stage"),
                            "stage": "hardware_worker" if error else receipt.get("stage", "hardware_worker"),
                            "error": error or receipt.get("error", "worker exited without an acceptance receipt")})
        receipt["supervisor"] = {"cleanup": cleanup, "interrupted_signal": interrupted_signal,
                                 "worker_receipt": str(worker_receipt),
                                 "elapsed_seconds": time.monotonic() - started}
        try:
            for sig in previous: signal.signal(sig, publication_interrupt)
            # Include a signal recorded while switching publication handlers.
            if interrupted_signal:
                receipt.update({"status": "FAIL", "error": "hardware supervisor interrupted: " + interrupted_signal})
                receipt["supervisor"]["interrupted_signal"] = interrupted_signal
            atomic_receipt(output, receipt)
        except KeyboardInterrupt:
            if Path(output).exists():
                raise  # Forwarded caller interruption after completed publication.
            # atomic_receipt removes its interrupted temporary file. The public
            # path is still absent, so install one immutable failed receipt.
            for sig in previous: signal.signal(sig, record_interrupt)
            receipt.update({"status": "FAIL", "error": "hardware supervisor interrupted: " +
                            (interrupted_signal or "KeyboardInterrupt")})
            receipt["supervisor"]["interrupted_signal"] = interrupted_signal or "KeyboardInterrupt"
            atomic_receipt(output, receipt)
        return 0 if receipt.get("status") == "PASS" else 1
    finally:
        if tree is not None: tree.close()
        for sig, handler in previous.items(): signal.signal(sig, handler)


def replay_snapshot(device):
    fields = {"state": 0x928, "flags": 0x92c, "fifo_level": 0x930,
              "configured": 0x90c, "pushed": 0x934, "accepted": 0x938,
              "responded": 0x93c, "checked": 0x940, "errors": 0x944,
              "first_index": 0x948, "first_address": 0x94c}
    result = {name: device.rd32(address) for name, address in fields.items()}
    for name, base in [("first_expected", 0x950), ("first_actual", 0x960)]:
        result[name] = struct.pack("<4I", *(device.rd32(base + i * 4) for i in range(4))).hex()
    return result


def wait_register(device, offset, mask, timeout, interval):
    deadline = time.monotonic() + timeout
    while True:
        value = device.rd32(offset)
        if value == 0xffffffff:
            raise OSError("endpoint returned all ones")
        if value & mask == mask:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timeout at BAR offset {offset:#x}: {value:#x}")
        time.sleep(interval)


def loader_command(device, opcode, address, data, timeout, interval):
    # Pinned task6 packet protocol: clear completion, stage, doorbell, count.
    device.wr32(8, 1)
    device.wr32(0x10, 0x33445244)
    device.wr32(0x14, opcode)
    device.wr32(0x18, address)
    for i, word in enumerate(struct.unpack("<4I", data.ljust(16, b"\0"))):
        device.wr32(0x20 + i * 4, word)
    before = device.rd32(0xc)
    device.wr32(0x30, 1)
    status = wait_register(device, 8, 4, timeout, interval)
    loader = wait_register(device, 0x34, 0x34, timeout, interval)
    if status & 0x18 or loader & 8 or device.rd32(0xc) != (before + 1) & 0xffffffff:
        raise RuntimeError("loader command error or stale completion")
    return struct.pack("<4I", *(device.rd32(0x44 + i * 4) for i in range(4)))


def load_and_verify(device, image_path, timeout, interval, receipt):
    receipt["load"] = progress = {"bytes_loaded": 0, "bytes_read_back": 0}
    with Path(image_path).open("rb") as stream:
        line = 0
        while packet := stream.read(64):
            if len(packet) % 16:
                raise ValueError("image is not complete 128-bit lines")
            for slot in range(len(packet) // 16):
                data = packet[slot * 16:(slot + 1) * 16]
                echo = loader_command(device, 15, slot, data, timeout, interval)
                if echo != data:
                    raise RuntimeError(f"loader slot echo mismatch at line {line + slot}")
            loader_command(device, 16, line | ((len(packet) // 16) << 29), b"", timeout, interval)
            line += len(packet) // 16
            progress["bytes_loaded"] += len(packet)
            if progress["bytes_loaded"] % 65536 == 0: checkpoint(receipt)
    checksum = hashlib.sha256()
    with Path(image_path).open("rb") as stream:
        line = 0
        while expected := stream.read(16):
            actual = loader_command(device, 6, line, b"", timeout, interval)
            if actual != expected:
                progress["first_mismatch"] = {"line": line, "expected": expected.hex(), "actual": actual.hex()}
                raise RuntimeError(f"complete image readback mismatch at line {line}")
            checksum.update(actual)
            progress["bytes_read_back"] += len(actual)
            line += 1
            if progress["bytes_read_back"] % 65536 == 0: checkpoint(receipt)
    progress["sha256_readback"] = checksum.hexdigest()


def stream_replay(device, path, count, timeout, interval, receipt):
    device.wr32(0x908, 2)
    cleared = replay_snapshot(device)
    if any(cleared[key] for key in ("state", "configured", "pushed", "accepted", "responded", "checked", "errors")):
        raise RuntimeError("CLEAR did not establish fresh replay state")
    device.wr32(0x90c, count)
    device.wr32(0x908, 1)
    deadline = time.monotonic() + timeout
    with Path(path).open("rb") as stream:
        for index in range(count):
            record = stream.read(20)
            if len(record) != 20:
                raise ValueError("replay truncated during streaming")
            while True:
                state = device.rd32(0x928)
                if state != 1:
                    receipt["replay"] = replay_snapshot(device)
                    raise RuntimeError(f"premature replay terminal state {state} at record {index}")
                flags = device.rd32(0x92c)
                if not flags & 1:
                    raise RuntimeError("calibration lost during replay")
                if flags & 2:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("replay FIFO timeout")
                time.sleep(interval)
            if time.monotonic() >= deadline:
                raise TimeoutError("full replay timeout")
            for i, word in enumerate(struct.unpack("<5I", record)):
                device.wr32(0x910 + i * 4, word)
            device.wr32(0x924, 1)
            if (index + 1) % 65536 == 0:
                receipt["replay_progress"] = replay_snapshot(device)
                checkpoint(receipt)
        if stream.read(1):
            raise ValueError("trailing replay records")
    if device.rd32(0x928) != 1:
        receipt["replay"] = replay_snapshot(device)
        raise RuntimeError("terminal replay state before FINISH")
    device.wr32(0x908, 4)
    while device.rd32(0x928) == 1:
        if time.monotonic() >= deadline:
            raise TimeoutError("replay completion timeout")
        time.sleep(interval)
    receipt["replay"] = final = replay_snapshot(device)
    if final["state"] != 2 or final["errors"] or not final["flags"] & 4 or any(
            final[key] != count for key in ("configured", "pushed", "accepted", "responded", "checked")):
        raise RuntimeError("replay failed exact terminal counters/PASS")


def run_gate(config, backend, output):
    """Backend owns authenticated programming/lifecycle and the BAR adapter."""
    if Path(output).exists():
        return 1
    started = time.monotonic()
    receipt = {"schema": "compiler-ddr3-trace-replay-hardware-v1", "status": "FAIL",
               "scope": "exact compiler-derived DDR3 replay diagnostic; not inference",
               "checkpoint_path": str(output) + ".snapshot.json", "stage": "authentication"}
    device = None
    try:
        checkpoint(receipt)
        artifacts = config["artifacts"]
        if not {"source", "bitstream", "image", "replay"}.issubset(artifacts):
            raise ValueError("missing authenticated artifact")
        for name in artifacts:
            artifact = artifacts[name]
            if Path(artifact["path"]).stat().st_size != artifact["bytes"] or digest(artifact["path"]) != artifact["sha256"]:
                raise ValueError(f"{name} artifact hash/size mismatch")
        receipt["artifacts"] = artifacts
        count = config["record_count"]
        if count < 1 or artifacts["replay"]["bytes"] != count * 20:
            raise ValueError("invalid exact replay length")
        if artifacts["image"]["bytes"] != config["image_bytes"] or config["image_bytes"] % 16:
            raise ValueError("invalid exact image length")
        receipt["stage"] = "prepare_isolation"
        checkpoint(receipt)
        receipt["isolation_transition"] = backend.prepare_isolation()
        receipt["stage"] = "isolation"
        checkpoint(receipt)
        receipt["isolation"] = backend.isolation()
        receipt["stage"] = "program"
        if hasattr(backend, "evidence"): receipt["backend"] = backend.evidence
        checkpoint(receipt)
        receipt["program"] = backend.program()
        receipt["stage"] = "lifecycle"
        checkpoint(receipt)
        receipt["lifecycle"] = backend.lifecycle()
        if receipt["lifecycle"]["classification"] != "pcie_ready":
            raise RuntimeError("endpoint is not lifecycle-ready")
        receipt["stage"] = "bar_identity"
        checkpoint(receipt)
        device = backend.open()
        identity = [device.rd32(offset) for offset in (0, 4, 0x900, 0x904)]
        receipt["bar_identity"] = identity
        if identity != [0x54365043, 3, 0x52504c59, 1]:
            raise RuntimeError("wrong BAR endpoint identity/version")
        receipt["initial_replay"] = replay_snapshot(device)
        if receipt["initial_replay"]["state"] != 0:
            raise RuntimeError("stale replay state after programming; preserving evidence")
        timeout = config["timeout"]
        receipt["stage"] = "calibration_bist"
        checkpoint(receipt)
        interval = config.get("poll_interval", 0.0001)
        status = wait_register(device, 8, 0x61, config["boot_timeout"], interval)
        loader = wait_register(device, 0x34, 3, config["boot_timeout"], interval)
        bist_state = device.rd32(0x54)
        receipt["calibration_bist"] = {"status": status, "loader": loader, "bist_mode": 2,
                                       "state": bist_state, "required_done_state": 23}
        if status & 0x18 or loader & 8 or bist_state != 23:
            raise RuntimeError("production calibration/BIST/boot failure")
        receipt["stage"] = "load_readback"
        checkpoint(receipt)
        load_and_verify(device, artifacts["image"]["path"], config.get("command_timeout", timeout), interval, receipt)
        if receipt["load"]["sha256_readback"] != artifacts["image"]["sha256"] or receipt["load"]["bytes_read_back"] != config["image_bytes"]:
            raise RuntimeError("complete image readback hash/length mismatch")
        receipt["stage"] = "replay"
        checkpoint(receipt)
        stream_replay(device, artifacts["replay"]["path"], count, timeout, interval, receipt)
        receipt["status"] = "PASS"
        receipt["stage"] = "complete"
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
        if hasattr(backend, "evidence"):
            receipt["backend"] = backend.evidence
        if device is not None and "replay" not in receipt:
            try:
                receipt["replay"] = replay_snapshot(device)
            except Exception as snapshot_error:
                receipt["snapshot_error"] = str(snapshot_error)
    finally:
        try:
            backend.close()
        except Exception as error:
            receipt["status"] = "FAIL"
            receipt["close_error"] = str(error)
    receipt["elapsed_seconds"] = time.monotonic() - started
    atomic_receipt(output, receipt)
    return 0 if receipt["status"] == "PASS" else 1


class VolatileMmio32:
    """Issue exactly one aligned volatile 32-bit access per BAR operation."""

    def __init__(self, mapping, library):
        self.mapping = mapping
        self.size = len(mapping)
        self.buffer = (ctypes.c_ubyte * self.size).from_buffer(mapping)
        self.base = ctypes.c_void_p(ctypes.addressof(self.buffer))
        self.read = library.ypcb_mmio_read32_be
        self.read.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
        self.read.restype = ctypes.c_uint32
        self.write = library.ypcb_mmio_write32_be
        self.write.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32)
        self.write.restype = None

    def _check(self, offset):
        if offset < 0 or offset + 4 > self.size or offset & 3:
            raise ValueError(f"MMIO offset must be aligned and in range: {offset:#x}")

    def rd32(self, offset):
        self._check(offset)
        return int(self.read(self.base, ctypes.c_size_t(offset)))

    def wr32(self, offset, value):
        self._check(offset)
        self.write(self.base, ctypes.c_size_t(offset), ctypes.c_uint32(value & 0xffffffff))

    def close(self):
        self.buffer = None


class HardwareBackend:
    """Programming is forbidden unless the exact chassis is isolated first."""
    def __init__(self, config):
        self.config = config
        self.evidence = {}
        self.mapping = None
        self.mmio = None
        self.fd = None
        self.thunderbolt_root = Path("/sys/bus/thunderbolt/devices")
        self.pci_root = Path("/sys/bus/pci/devices")
        self.boot_id_path = Path("/proc/sys/kernel/random/boot_id")
        self.verified = False
        self.log_bytes = 0

    def prepare_isolation(self):
        command = ["sudo", "-n", "/usr/local/sbin/ypcb-thunderbolt-isolate-for-programming"]
        result, output = self.command("isolate-for-programming", command, 30)
        if result:
            raise RuntimeError("Thunderbolt programming isolation helper failed")
        try:
            receipt = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Thunderbolt programming isolation helper returned invalid JSON") from exc
        expected = {
            "status": "isolated_for_programming",
            "device": "1-1",
            "device_name": "Helios 5S",
            "uuid": "c4148780-0010-1ed9-ffff-ffffffffffff",
            "endpoint_bdf": "0000:42:00.0",
            "endpoint": "absent",
        }
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Thunderbolt programming isolation receipt mismatch")
        if receipt.get("authorization") not in {"deauthorized", "already_deauthorized"}:
            raise RuntimeError("Thunderbolt programming isolation action mismatch")
        self.evidence["isolation_transition"] = receipt
        return receipt

    def isolation(self):
        path = self.thunderbolt_root / "1-1"
        observed = {key: (path / key).read_text().strip()
                    for key in ("device_name", "unique_id", "authorized")}
        self.evidence["isolation"] = observed
        if observed != {"device_name": "Helios 5S",
                        "unique_id": "c4148780-0010-1ed9-ffff-ffffffffffff",
                        "authorized": "0"}:
            raise RuntimeError("programming requires the exact Helios chassis with authorized=0")
        # Do not ignore unreadable PCI identity: absence must be established.
        for endpoint in self.pci_root.iterdir():
            vendor = (endpoint / "vendor").read_text().strip()
            device = (endpoint / "device").read_text().strip()
            if (vendor, device) == ("0x10ee", "0x0480"):
                raise RuntimeError("YPCB endpoint is still present; programming forbidden")
        return observed

    def program(self):
        # Recheck immediately at the destructive boundary, even for direct callers.
        self.isolation()
        if self.config.get("program_mode") != "bpi":
            raise RuntimeError("explicit BPI mode required; SRAM programming is forbidden")
        command = [self.config["programmer"], "-b", "ypcb003381p1", "-c", "digilent_hs3", "--ftdi-serial",
                   "210299BF3824", "--write-flash", "--verify",
                   self.config["artifacts"]["bitstream"]["path"]]
        self.evidence["program"] = {"argv": command, "invoked": False}
        if self.config.get("bpi_verification") != "full-readback-v1":
            raise RuntimeError("BPI programming blocked: no qualified full-image verification backend")
        self.evidence['disk_admission_before_program'] = admit_disk(Path(self.config['log_prefix']).parent)
        self.boot_id = self.boot_id_path.read_text().strip()
        if not self.boot_id:
            raise RuntimeError("host boot identity unreadable")
        self.evidence["boot_id_before"] = self.boot_id
        self.verified = False
        result, output = self.command("program", command, self.config["program_timeout"])
        expected = self.config["bitstream_payload_bytes"]
        written = re.findall(r"Writing (\d+) bytes to BPI flash at 0x0+\b", output)
        verified = re.findall(r"BPI full verification passed: (\d+) bytes at 0x0+\b", output)
        if result or written != [str(expected)] or verified != [str(expected)] or re.search(r"\b(?:FAILED|FAIL|failed|mismatch)\b", output):
            raise RuntimeError("BPI write/full verification failed or missing exact completion evidence")
        self.verified = True
        self.evidence["program"]["verified_payload_bytes"] = expected
        return self.evidence["program"]

    def command(self, label, argv, timeout):
        limit = min(MAX_COMMAND_LOG_BYTES, MAX_TOTAL_LOG_BYTES - self.log_bytes)
        if limit <= 0: raise RuntimeError('total command log bound exhausted')
        path = Path(str(self.config["log_prefix"]) + "." + label + ".log")
        entry = {"argv": argv, "log": str(path), "invoked": False}
        self.evidence[label] = entry
        # Stream output to an exclusive durable file, including partial output
        # if the worker dies or its command times out.
        with path.open("x") as log:
            entry["invoked"] = True
            try:
                environment = dict(os.environ)
                environment.pop("OPENFPGALOADER_SOJ_DIR", None)
                def bounded_output():
                    resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
                    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT,
                                        text=True, timeout=timeout, env=environment, preexec_fn=bounded_output)
                entry["returncode"] = result.returncode
            finally:
                log.flush()
                os.fsync(log.fileno())
                entry["sha256"] = digest(path)
                entry['bytes'] = path.stat().st_size
                self.log_bytes += entry['bytes']
        entry['log_limit_exceeded'] = entry['bytes'] >= limit
        return result.returncode or int(entry['log_limit_exceeded']), path.read_text()

    def probe_command(self):
        artifacts = self.config['artifacts']
        interpreter = artifacts['controller_python']
        path = Path(interpreter['path'])
        if path.stat().st_size != interpreter['bytes'] or digest(path) != interpreter['sha256']:
            raise ValueError('probe interpreter changed')
        selected = {name: artifacts[name] for name in ('lifecycle_probe', 'lifecycle_dependency')}
        return [str(path), '-I', '-S', '-B', '-c', PROBE_BOOTSTRAP, json.dumps(selected)]

    def lifecycle(self):
        if not self.verified:
            raise RuntimeError("cold-cycle forbidden before successful full BPI verification")
        self.isolation()
        manifest = self.config['artifacts']['runtime_manifest']
        authenticate_runtime_lifecycle(manifest['path'], manifest['sha256'])
        self.evidence['disk_admission_before_cycle'] = admit_disk(Path(self.config['log_prefix']).parent)
        result, _ = self.command("cold-cycle", ["sudo", "-n", "/usr/local/sbin/ypcb-thunderbolt-cold-cycle"], 300)
        if result:
            raise RuntimeError("deferred-authorization cold-cycle failed")
        after = self.boot_id_path.read_text().strip()
        self.evidence["boot_id_after"] = after
        if after != self.boot_id:
            raise RuntimeError("host boot identity changed during cold-cycle")
        path = self.thunderbolt_root / "1-1"
        observed = {key: (path / key).read_text().strip() for key in ("device_name", "unique_id", "authorized")}
        if observed != {"device_name": "Helios 5S", "unique_id": "c4148780-0010-1ed9-ffff-ffffffffffff", "authorized": "1"}:
            raise RuntimeError("post-cycle Thunderbolt identity/authorization mismatch")
        deadline = time.monotonic() + self.config.get("lifecycle_timeout", 90)
        attempt = 0
        while True:
            result, output = self.command(f"probe-{attempt}", self.probe_command(), 15)
            attempt += 1
            snapshot = json.loads(output)
            self.evidence["lifecycle"] = snapshot
            if result == 0 and snapshot["classification"] == "pcie_ready" and snapshot.get("actions") == []:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("PCIe lifecycle not ready after verified BPI cold-cycle")
            time.sleep(1)
        devices = []
        for path in self.pci_root.iterdir():
            if (path / "vendor").read_text().strip() == "0x10ee" and (path / "device").read_text().strip() == "0x0480":
                devices.append(path)
        if len(devices) != 1:
            raise RuntimeError("ambiguous or absent YPCB endpoint")
        self.device_path = devices[0]
        if [(self.device_path / name).read_text().strip() for name in ("subsystem_vendor", "subsystem_device")] != ["0x10ee", "0xabcd"]:
            raise RuntimeError("wrong post-cycle PCI endpoint subsystem identity")
        if not (self.device_path / "resource0").exists() or (self.device_path / "resource0").stat().st_size < 4096:
            raise RuntimeError("missing or short BAR0 before MMIO")
        snapshot["bdf"] = self.device_path.name
        return snapshot

    def open(self):
        self.fd = os.open(self.device_path / "resource0", os.O_RDWR | os.O_SYNC)
        self.mapping = mmap.mmap(self.fd, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        library = ctypes.CDLL(self.config["artifacts"]["mmio32_library"]["path"])
        self.mmio = VolatileMmio32(self.mapping, library)
        return self

    def rd32(self, offset):
        value = self.mmio.rd32(offset)
        # Identity/status cannot legitimately be all ones; payload can.
        if value == 0xffffffff and offset in (0, 4, 8, 0x34, 0x900, 0x904, 0x928, 0x92c):
            raise OSError(f"BAR all-ones read at {offset:#x}")
        return value

    def wr32(self, offset, value):
        self.mmio.wr32(offset, value)
        # A PCIe read drains posted writes before any subsequent command.
        if self.rd32(0) != 0x54365043:
            raise OSError("endpoint identity lost after BAR write")

    def close(self):
        if self.mmio is not None:
            self.mmio.close()
            self.mmio = None
        if self.mapping is not None:
            self.mapping.close()
        if self.fd is not None:
            os.close(self.fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--bitstream-receipt", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--lifecycle-manifest", type=Path,
                        help="required runtime-only lifecycle manifest; historical build receipt is unchanged")
    parser.add_argument("--lifecycle-manifest-sha256", help="required reviewed runtime manifest SHA-256")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--timeout", type=float, default=28800)
    parser.add_argument("--program-mode", choices=["bpi"], help="required for hardware; SRAM is forbidden")
    parser.add_argument("--program-timeout", type=float, default=21600,
                        help="bounded BPI programming plus complete readback seconds")
    parser.add_argument("--mmio-library", type=Path,
                        help="Nix-built volatile aligned 32-bit BAR accessor")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.receipt.exists():
        return 1
    reserve = None
    try:
        package = json.loads(args.package.read_text())
        required = {"record_count": 13116912, "binary_bytes": 262338240, "image_bytes": 4136720,
                    "record_bytes": 20, "prompt": [7454, 2402, 257, 640], "token": 11,
                    "candidate_sha256": "daed4badbce39933ffbbec461fa40603ddfdec0d137f543132fd02fd7ec1d88a",
                    "image_sha256": "e44d9bac0ddcf267cb2b41eb6f0aee623bacfb28809d9dffb7edc0319c43e593",
                    "binary_sha256": "46332a3a8d9ebf3a12d2fe968ae4e412200f9d419f3131ae46152dee26ee7d71",
                    "source_trace_sha256": "e61bb6100af2c612f3cbd3beef0f4fff0dce3194f1590fca0cee9d0f7ed2df23"}
        if any(package.get(key) != value for key, value in required.items()):
            raise ValueError("package is not the full authenticated production replay")
        build = json.loads(args.bitstream_receipt.read_text())
        if build.get("status") != "ROUTE_AND_BITSTREAM_PASS":
            raise ValueError("bitstream has not passed route and independent decode")
        if build.get("bpi_programmer", {}).get("verification") != "full-readback-v1":
            raise ValueError("receipt does not authenticate a full BPI verifier")
        if build["artifacts"]["programmer"]["sha256"] != "8686c42aabac9d720f128741d3f6fe27de8b8b9e5615f02c3d1450d78b759740":
            raise ValueError("unqualified BPI programmer binary")
        artifacts = bind_runtime_lifecycle(build['artifacts'], args.lifecycle_manifest,
                                           args.lifecycle_manifest_sha256)
        artifacts["source"] = {"path": str(args.bitstream_receipt), "bytes": args.bitstream_receipt.stat().st_size,
                               "sha256": digest(args.bitstream_receipt)}
        artifacts["image"] = {"path": str(args.image), "bytes": 4136720, "sha256": required["image_sha256"]}
        artifacts["replay"] = {"path": str(args.replay or package["binary_artifact"]),
                               "bytes": 262338240, "sha256": required["binary_sha256"]}
        if args.mmio_library is None or not args.mmio_library.is_file():
            raise ValueError("--mmio-library is required for physical BAR access")
        artifacts["mmio32_library"] = {
            "path": str(args.mmio_library), "bytes": args.mmio_library.stat().st_size,
            "sha256": digest(args.mmio_library)}
        config = {"artifacts": artifacts, "record_count": 13116912, "image_bytes": 4136720,
                  "program_mode": args.program_mode,
                  "program_timeout": args.program_timeout, "log_prefix": str(args.receipt),
                  "bpi_verification": "full-readback-v1", "bitstream_payload_bytes": 18735004,
                  "timeout": args.timeout, "command_timeout": 5, "boot_timeout": 300,
                  "programmer": artifacts["programmer"]["path"],
                  "lifecycle_probe": artifacts["lifecycle_probe"]["path"]}
        if not args.worker:
            if any(args.receipt.parent.glob(args.receipt.name + '.*')):
                raise ValueError('receipt/log prefix already used')
            reserve = EvidenceReserve(args.receipt, create=True)
            with reserve.protect(worker=False):
                return supervise([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"],
                                 args.receipt, args.timeout + args.program_timeout + 7200)
        # Only the supervisor installs the public final receipt after all
        # descendants have stopped. Preserve the worker's evidence separately.
        reserve = EvidenceReserve(args.receipt, create=False)
        with reserve.protect(worker=True):
            return run_gate(config, HardwareBackend(config), Path(str(args.receipt) + ".worker.json"))
    except Exception as error:
        target = Path(str(args.receipt) + ".worker.json") if args.worker else args.receipt
        receipt = {"status": "FAIL", "stage": "preflight", "error": str(error)}
        if reserve is not None:
            with reserve.protect(worker=args.worker): atomic_receipt(target, receipt)
        else:
            atomic_receipt(target, receipt)
        return 1
    finally:
        if reserve is not None and not args.worker: reserve.close()


if __name__ == "__main__":
    raise SystemExit(main())
