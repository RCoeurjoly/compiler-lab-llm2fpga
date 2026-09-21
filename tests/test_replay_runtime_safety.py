"""Disk exhaustion and import-shadowing controls; no hardware is accessed."""
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RuntimeSafetyTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('safe_replay', ROOT / 'scripts/pipeline/run_compiler_ddr3_trace_replay.py')
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)

    def test_public_failure_survives_enospc_after_worker_pass(self):
        """A full disk during PASS publication must not lose the public receipt."""
        self.assertTrue(hasattr(self.runner, 'EvidenceReserve'))
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp) / 'receipt.json'
            worker = Path(str(public) + '.worker.json')
            script = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\"}}')"
            reserve = self.runner.EvidenceReserve(public, create=True)
            self.assertEqual(sum(p.stat().st_size for p in reserve.directory.iterdir()), 8 << 20)
            self.assertTrue(all(p.stat().st_blocks * 512 >= 1 << 20 for p in reserve.directory.iterdir()))
            original = self.runner.os.fsync
            injected = []
            def fsync(fd):
                if self.runner.os.readlink(f'/proc/self/fd/{fd}').endswith('.tmp') and not injected:
                    self.assertFalse((reserve.directory / 'parent-final').exists())
                    self.assertTrue((reserve.directory / 'parent-emergency').exists())
                    injected.append(True)
                    raise OSError(errno.ENOSPC, 'injected terminal fsync full')
                return original(fd)
            try:
                with reserve.protect(worker=False), patch.object(self.runner.os, 'fsync', side_effect=fsync):
                    self.assertEqual(self.runner.supervise([sys.executable, '-c', script], public, 5), 1)
                receipt = json.loads(public.read_text())
                self.assertEqual(receipt['status'], 'FAIL')
                self.assertIn('ENOSPC', receipt['error'])
                self.assertTrue(injected)
                self.assertFalse((reserve.directory / 'parent-emergency').exists())
                self.assertFalse(list(Path(tmp).glob('*.tmp')))
            finally:
                reserve.close()

    def test_disk_admission_repeated_snapshots_and_allocation_failure(self):
        """Low space/failed allocation cannot admit; many replay snapshots stay bounded."""
        self.assertTrue(hasattr(self.runner, 'EvidenceReserve'))
        with tempfile.TemporaryDirectory() as tmp:
            public = Path(tmp) / 'receipt.json'
            with patch.object(shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100 << 20, 40 << 20, 63 << 20)):
                with self.assertRaisesRegex(RuntimeError, 'headroom'):
                    self.runner.EvidenceReserve(public, create=True)
            with patch.object(self.runner.os, 'posix_fallocate', side_effect=OSError(errno.ENOSPC, 'full')):
                with self.assertRaises(OSError): self.runner.EvidenceReserve(public, create=True)
            self.assertFalse(Path(str(public) + '.reserve').exists())
            reserve = self.runner.EvidenceReserve(public, create=True)
            try:
                receipt = {'checkpoint_path': str(public) + '.snapshot.json', 'status': 'FAIL'}
                with reserve.protect(worker=True):
                    for i in range(100):
                        receipt['progress'] = i
                        self.runner.checkpoint(receipt)
                    self.assertEqual(json.loads(Path(receipt['checkpoint_path']).read_text())['progress'], 99)
                    self.assertTrue((reserve.directory / 'worker-final').exists())
                    receipt['oversized'] = 'x' * (256 << 10)
                    with self.assertRaisesRegex(RuntimeError, 'bound'): self.runner.checkpoint(receipt)
                    self.runner.atomic_receipt(public, receipt)
                self.assertEqual(json.loads(public.read_text())['status'], 'FAIL')
                self.assertEqual(json.loads(public.read_text())['stage'], 'evidence_bound')
            finally:
                reserve.close()

    def test_subprocess_log_is_bounded_before_it_can_exhaust_disk(self):
        """Unbounded stdout must terminate the child, not fill the filesystem."""
        with tempfile.TemporaryDirectory() as tmp:
            backend = self.runner.HardwareBackend({'log_prefix': str(Path(tmp) / 'receipt')})
            code, output = backend.command('controlled', [sys.executable, '-c', 'import os; os.write(1,b"x"*(2<<20))'], 5)
            self.assertNotEqual(code, 0)
            self.assertLessEqual(len(output), 1 << 20)

    def test_terminal_open_write_and_link_failures_use_emergency_capacity(self):
        """ENOSPC before write or at no-overwrite link must also preserve FAIL."""
        for location in ('open', 'write', 'link'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as tmp:
                public = Path(tmp) / 'receipt.json'
                worker = Path(str(public) + '.worker.json')
                script = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\"}}')"
                reserve = self.runner.EvidenceReserve(public, create=True)
                owner, name = {'open': (self.runner.tempfile, 'mkstemp'),
                               'write': (self.runner.json, 'dump'),
                               'link': (self.runner.os, 'link')}[location]
                original = getattr(owner, name)
                calls = []
                def once(*args, **kwargs):
                    calls.append(1)
                    if len(calls) == 1: raise OSError(errno.ENOSPC, 'injected ' + location)
                    return original(*args, **kwargs)
                try:
                    with reserve.protect(worker=False), patch.object(owner, name, side_effect=once):
                        self.assertEqual(self.runner.supervise([sys.executable, '-c', script], public, 5), 1)
                    result = json.loads(public.read_text())
                    self.assertEqual(result['status'], 'FAIL')
                    self.assertIn('ENOSPC', result['error'])
                    self.assertFalse(list(Path(tmp).glob('*.tmp')))
                finally: reserve.close()

    def test_total_log_budget_and_low_disk_stop_before_external_action(self):
        """Per-file limits cannot be bypassed with many logs or low-space programming."""
        with tempfile.TemporaryDirectory() as tmp:
            backend = self.runner.HardwareBackend({'log_prefix': str(Path(tmp) / 'receipt'),
                'program_mode': 'bpi', 'programmer': '/never/invoke',
                'bpi_verification': 'full-readback-v1', 'artifacts': {'bitstream': {'path': '/unused'}}})
            with patch.object(self.runner, 'MAX_TOTAL_LOG_BYTES', 128):
                code, output = backend.command('controlled', [sys.executable, '-c', 'import os; os.write(1,b"x"*256)'], 5)
                self.assertNotEqual(code, 0)
                self.assertLessEqual(len(output), 128)
                with self.assertRaisesRegex(RuntimeError, 'total command log bound'):
                    backend.command('never', ['/never/invoke'], 5)
            with patch.object(backend, 'isolation', return_value={'authorized': '0'}), \
                 patch.object(shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100, 90, 10)), \
                 patch.object(backend, 'command', side_effect=lambda *a: self.fail('low disk allowed external command')):
                with self.assertRaisesRegex(RuntimeError, 'headroom'): backend.program()

    def test_probe_ignores_pythonpath_site_and_tools_dependency_shadowing(self):
        """The authenticated dependency, not an ambient tools package, must execute."""
        self.assertTrue(hasattr(self.runner.HardwareBackend, 'probe_command'))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'untrusted-executed'
            tools = root / 'tools'
            tools.mkdir()
            (tools / '__init__.py').write_text('')
            bad = f'from pathlib import Path; Path({str(marker)!r}).write_text("bad")\nVALUE="untrusted"\n'
            (tools / 'ypcb_pcie_power.py').write_text(bad)
            (root / 'ypcb_pcie_power.py').write_text(bad)
            (root / 'sitecustomize.py').write_text(bad)
            dependency = root / 'pinned_dependency.py'
            dependency.write_text('VALUE="authenticated"\n')
            probe = root / 'probe.py'
            probe.write_text('from tools.ypcb_pcie_power import VALUE\nimport ypcb_pcie_power\nassert VALUE == ypcb_pcie_power.VALUE\nprint(VALUE)\n')
            paths = {'controller_python': Path('/usr/bin/python3'), 'lifecycle_probe': probe,
                     'lifecycle_dependency': dependency}
            artifacts = {key: {'path': str(path), 'bytes': path.stat().st_size,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for key, path in paths.items()}
            backend = self.runner.HardwareBackend({'artifacts': artifacts})
            argv = backend.probe_command()
            environment = {**os.environ, 'PYTHONPATH': str(root), 'PYTHONUSERBASE': str(root)}
            unsafe = subprocess.run([sys.executable, str(probe)], cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(unsafe.stdout.strip(), 'untrusted')
            self.assertTrue(marker.exists(), 'control must reproduce inherited dependency selection')
            marker.unlink()
            result = subprocess.run(argv, cwd=root, env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'authenticated')
            self.assertFalse(marker.exists())
            dependency.write_text(bad)
            result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())


if __name__ == '__main__': unittest.main()
