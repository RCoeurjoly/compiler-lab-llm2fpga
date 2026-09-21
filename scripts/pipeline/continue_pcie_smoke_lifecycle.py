"""One evidence-bound smoke cold-cycle continuation; no programming or MMIO.

Only the exact 2026-09-20 verified smoke attempt whose power helper failed is
eligible. The live endpoint is a precondition, not proof of the BPI image.
PASS means enumeration after one cold cycle, never compiler/DDR acceptance.
"""
import argparse
from contextlib import contextmanager
import errno
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import sys


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'artifacts/reference/pcie-smoke-lifecycle-manifest.json'
MANIFEST_SHA = 'ac77b9f83e5d46a26db787df090267350506a8f4711892059b420decfaf4fc48'
SMOKE = Path(__file__).resolve().with_name('run_pcie_smoke_lifecycle.py')
import hashlib
with SMOKE.open('rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != '4aa7f82ca13e623e36bf98d44c2b294f8d280e1f249d267e1fae3425b8e25e4b':
        raise RuntimeError('reviewed smoke harness changed; refusing import')
spec = importlib.util.spec_from_file_location('reviewed_smoke', SMOKE)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
core = smoke.core
PREFIX = ROOT / '.superpowers/sdd/2026-09-18-compiler-micron-integration/task-4-known-good-smoke-arm-20260920.json'
EVIDENCE = {
    'prior_program_log': {'path': str(PREFIX) + '.program.log', 'bytes': 377766,
                          'sha256': 'a9b7bcdaa70ad3f888f85dd13b57d3d60fc341716cd2d8d270459a565c869373'},
    'prior_cold_cycle_log': {'path': str(PREFIX) + '.cold-cycle.log', 'bytes': 572,
                             'sha256': 'a7bced2a637da057ae8b599cb495cba015227f158bd0a778a5341f4bbbd56fe6'},
    'prior_snapshot': {'path': str(PREFIX) + '.worker.json.snapshot.json', 'bytes': 5498,
                       'sha256': 'dfbb1ebb27c34f54116147c7f0f0c51529c3ff0f3e734e8cd05de9ce9da98083'},
}
BOOT_ID = '265bb206-073e-4921-8b66-5053084a5874'
CYCLE = ['sudo', '-n', '/usr/local/sbin/ypcb-thunderbolt-cold-cycle']
MIN_FREE_BYTES = 64 << 20
EVIDENCE_SLOT_BYTES = 1 << 20
MAX_RECEIPT_BYTES = 256 << 10
BASE_ATOMIC = core.atomic_receipt
BASE_CHECKPOINT = core.checkpoint
RUNTIME_ROOT = Path('/home/roland/.local/share/ypcb-tapo-runtime/venv')
RUNTIME_TREE_SHA = '48f91b0f5cd7d6fa2e60a319006bb172f00671f600cdce8ab3d18b41aacf4cca'
INSTALLED_WRAPPERS = {
    'cold_cycle_wrapper': Path('/usr/local/sbin/ypcb-thunderbolt-cold-cycle'),
    'tapo_wrapper': Path('/usr/local/libexec/ypcb-tapo-cycle'),
}
WRAPPER_SHA = {
    'cold_cycle_wrapper': 'fd5204da90cb9df14efe64421062d2309dcaed08517397b8866ea410d1c0ed0f',
    'tapo_wrapper': 'a7d88192a14c9e27e5efd9e73c83375fe53e02b7b77f661bb5faeb678eb96c8f',
}


def authenticate_runtime():
    """Hash the retained complete venv, including pyc, metadata and symlink targets.

    No imports, package resolver, network, credentials or device operations.
    Isolated/no-bytecode wrapper Python keeps this frozen runtime unchanged.
    """
    rows, artifacts = [], {}
    for path in sorted(RUNTIME_ROOT.rglob('*')):
        relative = str(path.relative_to(RUNTIME_ROOT))
        if path.is_symlink():
            rows.append([relative, 'symlink', path.readlink().as_posix()])
        elif path.is_file():
            size, sha = path.stat().st_size, smoke.digest(path)
            rows.append([relative, size, sha])
            artifacts['runtime:' + relative] = {'path': str(path), 'bytes': size, 'sha256': sha}
        elif not path.is_dir():
            raise ValueError('unexpected special runtime file')
    actual = hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()
    if actual != RUNTIME_TREE_SHA:
        raise ValueError('fixed Tapo runtime tree changed or is missing')
    expected = {name: (path, WRAPPER_SHA[name]) for name, path in INSTALLED_WRAPPERS.items()}
    expected.update({
        'controller_python': (Path('/usr/bin/python3'), 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f'),
        'tapo_python': (RUNTIME_ROOT / 'bin/python', 'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f'),
        'tapo_power_script': (Path('/usr/local/libexec/ypcb_tapo_p115_power.py'), 'db25a6bd8efb0da1a7d2dd02ad1cf8252ea241d07f47a8faf38cdee7b9289548'),
    })
    for name, (path, sha) in expected.items():
        if smoke.digest(path) != sha:
            raise ValueError(name + ' fixed-runtime hash mismatch (installation required)')
        artifacts[name] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha}
    return artifacts


def historical_smoke_config():
    """Preserve the old snapshot contract, replacing only its obsolete wrapper later.

    The exact old manifest pins paths, sizes, schema and every SHA. All retained
    artifacts except the deliberately replaced installed wrapper are rehashed.
    The old wrapper is historical evidence, never an executable authorization.
    """
    if smoke.digest(MANIFEST) != MANIFEST_SHA:
        raise ValueError('historical smoke manifest changed')
    artifacts = json.loads(MANIFEST.read_text())['artifacts']
    for name, artifact in artifacts.items():
        if name == 'cold_cycle_wrapper': continue
        path = Path(artifact['path'])
        if path.stat().st_size != artifact['bytes'] or smoke.digest(path) != artifact['sha256']:
            raise ValueError(name + ' historical artifact changed')
    artifacts['manifest'] = {'path': str(MANIFEST), 'bytes': MANIFEST.stat().st_size, 'sha256': MANIFEST_SHA}
    return {'artifacts': artifacts, 'lifecycle_probe': artifacts['lifecycle_probe']['path']}


def admit_disk(receipt_directory, extra=0):
    """Dependencies must be materialized already; this budget is runtime headroom."""
    result = {}
    for path in (Path(receipt_directory), RUNTIME_ROOT):
        free = shutil.disk_usage(path).free
        result[str(path)] = free
        if free < MIN_FREE_BYTES + extra:
            raise RuntimeError(f'insufficient disk headroom at {path}: {free} bytes; require {MIN_FREE_BYTES + extra}')
    return {'minimum_free_bytes': MIN_FREE_BYTES, 'observed_free_bytes': result}


class EvidenceReserve:
    """Eight physically allocated slots, on the same filesystem as the receipts.

    Three bounded snapshots and primary/emergency final writes for both roles
    have separate capacity. The eighth slot is cleanup/metadata margin. A
    terminal ENOSPC converts PASS to FAIL and retries once from emergency space.
    This protects against ENOSPC, not an unreadable filesystem or hardware I/O
    failure. Other writers must not deliberately consume released space.
    """
    slots = ('snapshot-0', 'snapshot-1', 'snapshot-2', 'worker-final',
             'worker-emergency', 'parent-final', 'parent-emergency', 'cleanup')

    def __init__(self, output, *, create):
        self.directory = Path(str(output) + '.reserve')
        self.snapshot_index = 0
        self.created = []
        if create:
            self.admission = admit_disk(Path(output).parent, len(self.slots) * EVIDENCE_SLOT_BYTES)
            self.directory.mkdir(mode=0o700)
            try:
                for name in self.slots:
                    path = self.directory / name
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    self.created.append(path)
                    try:
                        os.posix_fallocate(fd, 0, EVIDENCE_SLOT_BYTES)
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                self.validate()
                self.sync_directory()
            except BaseException:
                self.close()
                raise
        else:
            self.admission = admit_disk(Path(output).parent)
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
        try:
            info = path.lstat()
        except FileNotFoundError:
            if required: raise RuntimeError('evidence reserve already consumed: ' + name)
            return
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise RuntimeError('refusing changed evidence reserve slot ' + name)
        path.unlink()
        self.sync_directory()

    def close(self):
        if not self.directory.exists(): return
        # Only exact slots in this run's exclusive directory, never recursive.
        for name in self.slots: self.release(name)
        self.directory.rmdir()

    def bounded(self, receipt, identity, *, terminal, role):
        receipt.setdefault('continuation_runner', identity)
        receipt.setdefault('continuation_runners', {})[role] = identity
        receipt['evidence_capacity'] = {'reserved_bytes': len(self.slots) * EVIDENCE_SLOT_BYTES,
                                        'maximum_receipt_bytes': MAX_RECEIPT_BYTES,
                                        'minimum_runtime_headroom_bytes': MIN_FREE_BYTES}
        data = json.dumps(receipt, indent=2, sort_keys=True).encode()
        if len(data) <= MAX_RECEIPT_BYTES: return
        if not terminal: raise RuntimeError('snapshot exceeds reserved evidence bound')
        runner = receipt['continuation_runner']
        receipt.clear()
        receipt.update(status='FAIL', stage='evidence_bound',
                       error='terminal receipt exceeds reserved evidence bound',
                       oversized_receipt_sha256=hashlib.sha256(data).hexdigest(),
                       continuation_runner=runner, continuation_runners={role: identity})

    @contextmanager
    def protect(self, *, worker, identity):
        role = 'worker' if worker else 'parent'
        previous_atomic, previous_checkpoint = core.atomic_receipt, core.checkpoint
        def checkpoint(receipt):
            if not worker: raise RuntimeError('parent cannot consume worker snapshot capacity')
            self.bounded(receipt, identity, terminal=False, role=role)
            slot = f'snapshot-{self.snapshot_index}'
            if self.snapshot_index >= 3: raise RuntimeError('unexpected extra snapshot')
            self.release(slot, required=True)
            self.snapshot_index += 1
            BASE_CHECKPOINT(receipt)
        def publish(path, receipt):
            self.bounded(receipt, identity, terminal=True, role=role)
            self.release(role + '-final')
            try:
                BASE_ATOMIC(path, receipt)
            except OSError as error:
                if error.errno != errno.ENOSPC or Path(path).exists(): raise
                # Never overwrite the public path, even on a publication fault.
                receipt.update(status='FAIL', error='ENOSPC during terminal publication; emergency reserve used')
                self.release(role + '-emergency', required=True)
                BASE_ATOMIC(path, receipt)
            else:
                self.release(role + '-emergency')
        core.atomic_receipt, core.checkpoint = publish, checkpoint
        try: yield
        finally: core.atomic_receipt, core.checkpoint = previous_atomic, previous_checkpoint


def validate_logs(program, cold):
    marker = 'BPI full verification passed: 18735004 bytes at 0x00000000'
    if (program.splitlines().count(marker) != 1
            or re.findall(r'Writing (\d+) bytes to BPI flash at 0x0+\b', program) != ['18735004']
            or re.search(r'\b(?:FAILED|FAIL|failed|mismatch)\b', program)):
        raise ValueError('prior program lacks unambiguous complete BPI verification')
    events = re.findall(r'event=(\w+)', cold)
    if events != ['auth_mode_disabled', 'helios_already_deauthorized', 'auth_mode_restored', 'cleanup_authorized']:
        raise ValueError('prior controller event sequence is not the approved incomplete cycle')
    if ('error: unprivileged chassis power cycle failed:' not in cold
            or "executing SQLite statement 'pragma synchronous = off': disk I/O error" not in cold
            or '/home/roland/.cache/nix/fetcher-cache-v4.sqlite' not in cold):
        raise ValueError('prior power helper did not fail at the authenticated pre-completion boundary')


def runner_identity():
    path = Path(__file__).resolve()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': smoke.digest(path)}


def authenticate(expected_sha256):
    identity = runner_identity()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256) or identity['sha256'] != expected_sha256:
        raise ValueError('continuation self hash does not match the reviewed caller hash')
    config = historical_smoke_config()
    for name, artifact in EVIDENCE.items():
        path = Path(artifact['path'])
        if path.stat().st_size != artifact['bytes'] or smoke.digest(path) != artifact['sha256']:
            raise ValueError(name + ' evidence hash/size mismatch')
    validate_logs(Path(EVIDENCE['prior_program_log']['path']).read_text(),
                  Path(EVIDENCE['prior_cold_cycle_log']['path']).read_text())
    snapshot = json.loads(Path(EVIDENCE['prior_snapshot']['path']).read_text())
    program = snapshot['program']
    artifacts = config['artifacts']
    expected_argv = [artifacts['programmer']['path'], '-b', 'ypcb003381p1', '-c', 'digilent_hs3',
                     '--ftdi-serial', '210299BF3824', '--write-flash', '--verify', artifacts['bitstream']['path']]
    if (snapshot['schema'] != 'pcie-smoke-lifecycle-result-v1' or snapshot['stage'] != 'lifecycle'
            or snapshot['artifacts'] != artifacts or snapshot['mmio_accessed'] is not False
            or snapshot['backend']['boot_id_before'] != BOOT_ID
            or program['argv'] != expected_argv or program['returncode'] != 0
            or program['sha256'] != EVIDENCE['prior_program_log']['sha256']
            or program['verified_payload_bytes'] != 18735004):
        raise ValueError('prior snapshot does not bind this exact image/program/boot')
    config['artifacts'] = {**artifacts, **authenticate_runtime(), **EVIDENCE, 'continuation_runner': identity}
    config['runtime_tree'] = {'path': str(RUNTIME_ROOT), 'sha256': RUNTIME_TREE_SHA, 'tapo_version': '0.9.0'}
    config['continuation_runner'] = identity
    config['boot_id'] = BOOT_ID
    return config


class ContinuationBackend:
    """No programmer/BAR adapter is inherited or exposed."""
    def __init__(self, config):
        self.config = config
        self.evidence = {}
        self.thunderbolt_root = Path('/sys/bus/thunderbolt/devices')
        self.pci_root = Path('/sys/bus/pci/devices')
        self.boot_id_path = Path('/proc/sys/kernel/random/boot_id')
        self.cycle_attempted = False

    def host_identity(self):
        boot = self.boot_id_path.read_text().strip()
        if boot != self.config['boot_id']:
            raise RuntimeError('host boot changed since the authenticated BPI write')
        tb = self.thunderbolt_root / '1-1'
        observed = {key: (tb / key).read_text().strip() for key in ('device_name', 'unique_id', 'authorized')}
        if observed != {'device_name': 'Helios 5S', 'unique_id': 'c4148780-0010-1ed9-ffff-ffffffffffff', 'authorized': '1'}:
            raise RuntimeError('wrong current Helios identity/authorization')
        return {'boot_id': boot, 'helios': observed}

    def endpoint_identity(self):
        devices = []
        for path in self.pci_root.iterdir():
            if ((path / 'vendor').read_text().strip(), (path / 'device').read_text().strip()) == ('0x10ee', '0x0480'):
                devices.append(path)
        if len(devices) != 1 or devices[0].name != '0000:42:00.0':
            raise RuntimeError('exact unique YPCB endpoint absent')
        path = devices[0]
        observed = {key: (path / key).read_text().strip() for key in
                    ('vendor', 'device', 'subsystem_vendor', 'subsystem_device', 'class',
                     'current_link_speed', 'current_link_width')}
        expected = {'vendor': '0x10ee', 'device': '0x0480', 'subsystem_vendor': '0x10ee',
                    'subsystem_device': '0xabcd', 'class': '0x058000',
                    'current_link_speed': '2.5 GT/s PCIe', 'current_link_width': '1'}
        if observed != expected:
            raise RuntimeError('endpoint identity/subsystem/link mismatch')
        resource = [int(word, 16) for word in (path / 'resource').read_text().splitlines()[0].split()]
        if resource != [0x74000000, 0x74000fff, 0x40200] or (path / 'resource0').stat().st_size != 4096:
            raise RuntimeError('endpoint BAR0 address/flags/size mismatch')
        # Standard PCI configuration read only, never BAR/resource0 access.
        with (path / 'config').open('rb') as stream:
            stream.seek(4)
            command = struct.unpack('<H', stream.read(2))[0]
        if command != 2:
            raise RuntimeError('endpoint PCI COMMAND mismatch')
        return {**observed, 'bdf': path.name, 'bar0': resource, 'command': command}

    def precondition(self):
        return {**self.host_identity(), 'endpoint': self.endpoint_identity()}

    def command(self, label, argv, timeout):
        allowed_cycle = label == 'cold-cycle' and argv == CYCLE
        allowed_probe = re.fullmatch(r'probe-\d+', label) and argv == [sys.executable, self.config['lifecycle_probe']]
        if not (allowed_cycle or allowed_probe):
            raise RuntimeError('continuation forbids programming or non-lifecycle commands')
        return core.HardwareBackend.command(self, label, argv, timeout)

    def lifecycle(self):
        if self.cycle_attempted:
            raise RuntimeError('continuation cold-cycle already attempted')
        self.evidence['immediate_precondition'] = self.precondition()
        # Rehash even extra files/symlink targets immediately before the only cycle.
        authenticate_runtime()
        self.evidence['disk_admission'] = admit_disk(Path(self.config['log_prefix']).parent)
        self.cycle_attempted = True
        result, _ = self.command('cold-cycle', CYCLE, 300)
        if result:
            raise RuntimeError('continuation cold-cycle failed; no retry')
        deadline = core.time.monotonic() + 90
        self.evidence['post_cycle_host'] = self.host_identity()
        attempt = 0
        while True:
            remaining = deadline - core.time.monotonic()
            if remaining <= 0:
                raise RuntimeError('continuation lifecycle deadline expired')
            code, output = self.command(f'probe-{attempt}', [sys.executable, self.config['lifecycle_probe']], min(15, remaining))
            attempt += 1
            if core.time.monotonic() >= deadline:
                raise RuntimeError('continuation lifecycle deadline expired during probe')
            snapshot = json.loads(output)
            self.evidence['lifecycle'] = snapshot
            if code == 0 and snapshot.get('classification') == 'pcie_ready' and snapshot.get('actions') == []:
                snapshot['identity'] = self.precondition()
                if core.time.monotonic() >= deadline:
                    raise RuntimeError('continuation lifecycle deadline expired during identity validation')
                return snapshot
            core.time.sleep(min(1, max(0, deadline - core.time.monotonic())))


def run_gate(config, backend, output):
    if Path(output).exists():
        return 1
    receipt = {'schema': 'pcie-smoke-lifecycle-continuation-v1', 'status': 'FAIL',
               'scope': 'one evidence-bound cold-cycle and read-only enumeration; no programming/MMIO/DDR/replay',
               'mmio_accessed': False, 'stage': 'authentication', 'backend': backend.evidence,
               'checkpoint_path': str(output) + '.snapshot.json',
               'continuation_runner': config['continuation_runner']}
    try:
        core.checkpoint(receipt)
        for name, artifact in config['artifacts'].items():
            path = Path(artifact['path'])
            if path.stat().st_size != artifact['bytes'] or smoke.digest(path) != artifact['sha256']:
                raise ValueError(name + ' changed after evidence authentication')
        receipt['artifacts'] = config['artifacts']
        receipt['runtime_tree'] = config['runtime_tree']
        receipt['stage'] = 'precondition'
        core.checkpoint(receipt)
        receipt['precondition'] = backend.precondition()
        receipt['stage'] = 'cold_cycle_and_lifecycle'
        core.checkpoint(receipt)
        receipt['lifecycle'] = backend.lifecycle()
        receipt.update(status='PASS', stage='complete')
    except Exception as error:
        receipt['error'] = str(error)
    core.atomic_receipt(output, receipt)
    return 0 if receipt['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True,
                        help='externally reviewed continuation hash; verified by parent and worker')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    target = Path(str(args.receipt) + '.worker.json') if args.worker else args.receipt
    if args.receipt.exists() or target.exists():
        return 1
    reserve = None
    try:
        config = authenticate(args.expected_sha256)
        config['log_prefix'] = str(args.receipt)
        if not args.worker:
            if any(args.receipt.parent.glob(args.receipt.name + '.*')):
                raise ValueError('receipt/log prefix already used')
            reserve = EvidenceReserve(args.receipt, create=True)
            with reserve.protect(worker=False, identity=config['continuation_runner']):
                return core.supervise([sys.executable, str(Path(__file__).resolve()),
                                       *sys.argv[1:], '--worker'], args.receipt, 480)
        reserve = EvidenceReserve(args.receipt, create=False)
        with reserve.protect(worker=True, identity=config['continuation_runner']):
            return run_gate(config, ContinuationBackend(config), target)
    except Exception as error:
        core.atomic_receipt(target, {'schema': 'pcie-smoke-lifecycle-continuation-v1',
                                    'status': 'FAIL', 'stage': 'preflight', 'error': str(error),
                                    'continuation_runner': runner_identity()})
        return 1
    finally:
        if reserve is not None and not args.worker: reserve.close()


if __name__ == '__main__':
    raise SystemExit(main())
