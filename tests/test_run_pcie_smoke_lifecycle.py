"""Smoke lifecycle safety controls; fake sysfs and subprocess, no hardware."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/pipeline/run_pcie_smoke_lifecycle.py'
MANIFEST = ROOT / 'artifacts/reference/pcie-smoke-lifecycle-manifest.json'


class SmokeTest(unittest.TestCase):
    def load(self):
        self.assertTrue(SCRIPT.exists(), 'missing isolated smoke-only lifecycle harness')
        spec = importlib.util.spec_from_file_location('smoke_lifecycle', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_authenticated_manifest_rejects_replacement_or_mutated_artifacts(self):
        """Removing any trusted identity/digest check admits a replacement image/tool."""
        module = self.load()
        config = module.authenticate(MANIFEST, module.digest(MANIFEST))
        self.assertEqual(config['bitstream_payload_bytes'], 18735004)
        self.assertEqual(config['lifecycle_timeout'], 90)
        self.assertNotIn('image', config['artifacts'])
        self.assertNotIn('replay', config['artifacts'])
        with self.assertRaises(ValueError): module.authenticate(MANIFEST, '0' * 64)
        original = json.loads(MANIFEST.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'manifest.json'
            for name in original['artifacts']:
                with self.subTest(name=name):
                    changed = copy.deepcopy(original)
                    changed['artifacts'][name]['sha256'] = '0' * 64
                    target.write_text(json.dumps(changed))
                    with self.assertRaises((ValueError, OSError)):
                        module.authenticate(target, module.digest(target))
            changed = copy.deepcopy(original)
            changed['payload_bytes'] = 64
            target.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): module.authenticate(target, module.digest(target))

    def fixture(self, module, root, fault):
        config = module.authenticate(MANIFEST, module.digest(MANIFEST))
        config['log_prefix'] = str(root / 'run')
        backend = module.SmokeBackend(config)
        tb = root / 'tb' / '1-1'; tb.mkdir(parents=True)
        pci = root / 'pci'; pci.mkdir()
        for key, value in {'device_name': 'Helios 5S', 'authorized': '0',
                           'unique_id': 'c4148780-0010-1ed9-ffff-ffffffffffff'}.items():
            (tb / key).write_text(value)
        boot = root / 'boot'; boot.write_text('original-boot')
        backend.thunderbolt_root = tb.parent; backend.pci_root = pci
        backend.boot_id_path = boot
        events = []
        def command(argv, **kwargs):
            if '--write-flash' in argv:
                events.append('program')
                self.assertEqual(argv[1:8], ['-b', 'ypcb003381p1', '-c', 'digilent_hs3',
                                           '--ftdi-serial', '210299BF3824', '--write-flash'])
                self.assertIn('--verify', argv)
                self.assertEqual((tb / 'authorized').read_text(), '0')
                kwargs['stdout'].write('Writing 18735004 bytes to BPI flash at 0x00000000\n')
                count = 64 if fault == 'short_verify' else 18735004
                kwargs['stdout'].write(f'BPI full verification passed: {count} bytes at 0x00000000\n')
                return subprocess.CompletedProcess(argv, 1 if fault == 'program' else 0)
            if argv == ['sudo', '-n', '/usr/local/sbin/ypcb-thunderbolt-cold-cycle']:
                events.append('cycle')
                (tb / 'authorized').write_text('1')
                if fault == 'boot': boot.write_text('other-boot')
                if fault == 'post_identity': (tb / 'unique_id').write_text('other')
                return subprocess.CompletedProcess(argv, 1 if fault == 'cycle' else 0)
            self.assertEqual(argv, [sys.executable, config['lifecycle_probe']])
            events.append('probe')
            endpoint = pci / '0000:42:00.0'; endpoint.mkdir(exist_ok=True)
            for key, value in {'vendor': '0x10ee', 'device': '0x0480',
                               'subsystem_vendor': '0x10ee', 'subsystem_device': '0xabcd'}.items():
                (endpoint / key).write_text('0x0000' if fault == key else value)
            if fault != 'bar': (endpoint / 'resource0').write_bytes(bytes(4096))
            kwargs['stdout'].write(json.dumps({'classification': 'pcie_ready', 'actions': []}))
            return subprocess.CompletedProcess(argv, 0)
        if fault == 'isolated': (tb / 'authorized').write_text('1')
        if fault == 'recheck':
            original = backend.isolation
            def isolation():
                result = original()
                (tb / 'authorized').write_text('1')
                return result
            backend.isolation = isolation
        return config, backend, events, command

    def test_real_backend_orders_gates_and_never_opens_mmio(self):
        """Skipping isolation/full verify/identity gates or entering MMIO fails."""
        module = self.load()
        faults = (None, 'isolated', 'recheck', 'program', 'short_verify', 'cycle',
                  'boot', 'post_identity', 'vendor', 'device', 'subsystem_vendor',
                  'subsystem_device', 'bar')
        for fault in faults:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config, backend, events, command = self.fixture(module, root, fault)
                output = root / 'receipt.json'
                with patch.object(module.core.subprocess, 'run', side_effect=command), \
                     patch.object(module.core.HardwareBackend, 'open', side_effect=AssertionError('MMIO forbidden')):
                    result = module.run_gate(config, backend, output)
                receipt = json.loads(output.read_text())
                if fault is None:
                    self.assertEqual(result, 0)
                    self.assertEqual(receipt['status'], 'PASS')
                    self.assertEqual(events, ['program', 'cycle', 'probe'])
                    self.assertFalse(receipt['mmio_accessed'])
                    self.assertEqual(receipt['lifecycle']['bdf'], '0000:42:00.0')
                else:
                    self.assertNotEqual(result, 0)
                    self.assertEqual(receipt['status'], 'FAIL')
                    if fault in ('isolated', 'recheck'): self.assertEqual(events, [])
                    if fault in ('program', 'short_verify'): self.assertEqual(events, ['program'])
                    if fault in ('cycle', 'boot', 'post_identity'): self.assertEqual(events, ['program', 'cycle'])
                saved = output.read_bytes()
                self.assertNotEqual(module.run_gate(config, backend, output), 0)
                self.assertEqual(output.read_bytes(), saved)

    def test_late_ready_cannot_pass_fixed_deadline(self):
        """A probe returning ready after the deadline must not qualify."""
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            config, backend, events, command = self.fixture(module, Path(temporary), None)
            backend.probe_deadline = 90
            with patch.object(module.core.time, 'monotonic', side_effect=[89, 91]), \
                 patch.object(module.core.subprocess, 'run', side_effect=command):
                with self.assertRaisesRegex(RuntimeError, 'deadline'):
                    backend.command('probe-0', [sys.executable, config['lifecycle_probe']], 15)

    def test_cli_rejects_replay_arguments_and_persists_bad_manifest(self):
        """Smoke CLI must not expose replay controls or bypass authentication."""
        self.load()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'receipt.json'
            argv = [sys.executable, str(SCRIPT), '--manifest', str(MANIFEST),
                    '--manifest-sha256', '0' * 64, '--receipt', str(output)]
            result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(output.read_text())['status'], 'FAIL')
            for argument in ('--image', '--replay', '--package', '--program-mode', '--lifecycle-timeout'):
                result = subprocess.run([*argv, argument, 'arbitrary'], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)

    def test_identity_validation_must_finish_within_deadline(self):
        """A fast ready classifier must not hide late endpoint/BAR validation."""
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            config, backend, events, command = self.fixture(module, Path(temporary), None)
            clock = [0]
            original = Path.stat
            def delayed_bar_stat(path, *args, **kwargs):
                result = original(path, *args, **kwargs)
                if path.name == 'resource0': clock[0] = 91
                return result
            with patch.object(module.core.subprocess, 'run', side_effect=command), \
                 patch.object(module.core.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(Path, 'stat', delayed_bar_stat):
                backend.program()
                with self.assertRaisesRegex(RuntimeError, 'deadline'):
                    backend.lifecycle()


if __name__ == '__main__': unittest.main()
