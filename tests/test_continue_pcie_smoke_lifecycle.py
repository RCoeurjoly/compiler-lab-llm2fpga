"""No hardware: authenticate retained evidence and control only subprocess/sysfs."""
import copy
import errno
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import shutil
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/pipeline/continue_pcie_smoke_lifecycle.py'


class ContinuationTest(unittest.TestCase):
    def test_fixed_runtime_rejects_changed_package_and_uninstalled_wrappers(self):
        """A changed executable/package or old dynamic wrapper must prevent a cycle."""
        module = self.load(installed=True)
        self.assertTrue(hasattr(module, 'authenticate_runtime'), 'missing fixed-runtime authentication')
        with tempfile.TemporaryDirectory() as temporary:
            obsolete = Path(temporary) / 'dynamic-wrapper'
            obsolete.write_text('#!/bin/bash\nexec nix shell nixpkgs#python3\n')
            with patch.object(module, 'INSTALLED_WRAPPERS', {
                'cold_cycle_wrapper': obsolete,
                'tapo_wrapper': ROOT / 'scripts/host/ypcb/ypcb-tapo-cycle',
            }), self.assertRaisesRegex(ValueError, 'cold_cycle_wrapper'):
                module.authenticate_runtime()
        sources = ROOT / 'scripts/host/ypcb'
        with patch.object(module, 'INSTALLED_WRAPPERS', {
            'cold_cycle_wrapper': sources / 'ypcb-thunderbolt-cold-cycle',
            'tapo_wrapper': sources / 'ypcb-tapo-cycle',
        }):
            artifacts = module.authenticate_runtime()
            self.assertEqual(artifacts['tapo_python']['sha256'],
                             'e50d468e8b0adfb05733f5b87b3cff34829c4a8c1aea50c865aa8bdfe4bb150f')
            with tempfile.TemporaryDirectory() as temporary:
                bad = Path(temporary) / 'venv'; bad.mkdir()
                (bad / 'package.py').write_text('mutated')
                with patch.object(module, 'RUNTIME_ROOT', bad), self.assertRaises(ValueError):
                    module.authenticate_runtime()

    def test_runtime_change_after_authentication_prevents_cycle(self):
        """Removing the immediate runtime recheck would permit changed power code."""
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, backend, events, clock, command = self.fixture(module, root, None)
            changed = root / 'changed-wrapper'; changed.write_text('exit 0\n')
            with patch.dict(module.INSTALLED_WRAPPERS, tapo_wrapper=changed), \
                 patch.object(module.core.subprocess, 'run', side_effect=command), \
                 patch.object(module, 'admit_disk', return_value={}):
                with self.assertRaisesRegex(ValueError, 'tapo_wrapper'):
                    backend.lifecycle()
            self.assertEqual(events, [])

    def load(self, *, installed=False):
        self.assertTrue(SCRIPT.exists(), 'missing evidence-bound lifecycle-only continuation')
        spec = importlib.util.spec_from_file_location('smoke_continuation', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not installed and hasattr(module, 'INSTALLED_WRAPPERS'):
            # Only the external installation paths are substituted; real wrapper
            # bytes, complete retained runtime and all authentication stay real.
            module.INSTALLED_WRAPPERS = {
                'cold_cycle_wrapper': ROOT / 'scripts/host/ypcb/ypcb-thunderbolt-cold-cycle',
                'tapo_wrapper': ROOT / 'scripts/host/ypcb/ypcb-tapo-cycle',
            }
        return module

    def test_wrong_self_hash_fails_before_worker_and_is_recorded(self):
        """A caller's reviewed hash must authenticate this code, not only dependencies."""
        with tempfile.TemporaryDirectory() as temporary:
            for worker in (False, True):
                output = Path(temporary) / ('worker.json' if worker else 'parent.json')
                command = [sys.executable, str(SCRIPT), '--receipt', str(output),
                           '--expected-sha256', '0' * 64]
                if worker: command.append('--worker')
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                receipt = json.loads(Path(str(output) + '.worker.json' if worker else output).read_text())
                self.assertEqual(receipt['status'], 'FAIL')
                self.assertIn('self hash', receipt['error'])
                self.assertEqual(receipt['continuation_runner']['sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())

    def test_exact_evidence_and_snapshot_binding_reject_mutation(self):
        """A replaced prior program/cycle/snapshot must not authorize a cycle."""
        module = self.load()
        config = module.authenticate(hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(config['continuation_runner']['sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(config['boot_id'], '265bb206-073e-4921-8b66-5053084a5874')
        self.assertEqual(config['artifacts']['bitstream']['sha256'],
                         '276442d6348b330b55b8e8bde55e5a409456abfc869be014d767eb3a53ee7bab')
        for name in module.EVIDENCE:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                evidence = copy.deepcopy(module.EVIDENCE)
                target = Path(temporary) / 'altered'
                target.write_bytes(Path(evidence[name]['path']).read_bytes() + b'\nmutation')
                evidence[name]['path'] = str(target)
                with patch.object(module, 'EVIDENCE', evidence), self.assertRaises(ValueError):
                    module.authenticate(hashlib.sha256(SCRIPT.read_bytes()).hexdigest())

    def test_log_contract_rejects_partial_verify_or_completed_cycle(self):
        """A sampled verify, duplicate marker or completed cycle invalidates resumption."""
        module = self.load()
        program = Path(module.EVIDENCE['prior_program_log']['path']).read_text()
        cold = Path(module.EVIDENCE['prior_cold_cycle_log']['path']).read_text()
        module.validate_logs(program, cold)
        for changed_program, changed_cold in (
            (program.replace('passed: 18735004', 'passed: 64'), cold),
            (program + '\nBPI full verification passed: 18735004 bytes at 0x00000000\n', cold),
            (program + '\nFAILED\n', cold),
            (program, cold + '\nevent=power_cycle_completed\n'),
            (program, cold.replace('event=cleanup_authorized', 'event=cleanup_failed')),
            (program, cold.replace('disk I/O error', 'different error')),
        ):
            with self.subTest(program=changed_program[-100:], cold=changed_cold[-100:]), \
                 self.assertRaises(ValueError):
                module.validate_logs(changed_program, changed_cold)

    def fixture(self, module, root, fault):
        config = module.authenticate(hashlib.sha256(SCRIPT.read_bytes()).hexdigest()); config['log_prefix'] = str(root / 'run')
        backend = module.ContinuationBackend(config)
        tb = root / 'tb' / '1-1'; tb.mkdir(parents=True)
        for key, value in {'device_name': 'Helios 5S', 'authorized': '1',
                           'unique_id': 'c4148780-0010-1ed9-ffff-ffffffffffff'}.items():
            (tb / key).write_text(value)
        pci = root / 'pci'; pci.mkdir()
        endpoint = pci / '0000:42:00.0'; endpoint.mkdir()
        for key, value in {'vendor': '0x10ee', 'device': '0x0480', 'subsystem_vendor': '0x10ee',
                           'subsystem_device': '0xabcd', 'class': '0x058000',
                           'current_link_speed': '2.5 GT/s PCIe', 'current_link_width': '1'}.items():
            (endpoint / key).write_text(value)
        (endpoint / 'resource').write_text('0x74000000 0x74000fff 0x40200\n')
        (endpoint / 'resource0').write_bytes(bytes(4096))
        (endpoint / 'config').write_bytes(bytes(4) + struct.pack('<H', 2))
        boot = root / 'boot'; boot.write_text(config['boot_id'])
        backend.thunderbolt_root = tb.parent; backend.pci_root = pci; backend.boot_id_path = boot
        if fault == 'boot_before': boot.write_text('other')
        if fault == 'authorized_before': (tb / 'authorized').write_text('0')
        if fault == 'uuid_before': (tb / 'unique_id').write_text('other')
        if fault == 'endpoint_before': (endpoint / 'vendor').write_text('0x0000')
        if fault == 'subsystem_before': (endpoint / 'subsystem_device').write_text('0x0000')
        if fault == 'class_before': (endpoint / 'class').write_text('0x000000')
        if fault == 'bar_before': (endpoint / 'resource').write_text('0x75000000 0x75000fff 0x40200\n')
        if fault == 'command_before': (endpoint / 'config').write_bytes(bytes(6))
        if fault == 'link_before': (endpoint / 'current_link_width').write_text('0')
        events=[]; clock=[0]
        def command(argv, **kwargs):
            if argv == ['sudo', '-n', '/usr/local/sbin/ypcb-thunderbolt-cold-cycle']:
                events.append('cycle')
                if fault == 'boot_after': boot.write_text('other')
                if fault == 'authorized_after': (tb / 'authorized').write_text('0')
                if fault == 'subsystem_after': (endpoint / 'subsystem_device').write_text('0x0000')
                if fault == 'bar_after': (endpoint / 'resource0').write_bytes(bytes(8))
                return subprocess.CompletedProcess(argv, 1 if fault == 'cycle' else 0)
            self.assertEqual(argv, [sys.executable, config['lifecycle_probe']])
            events.append('probe')
            output={'classification':'missing_endpoint' if fault == 'not_ready' else 'pcie_ready',
                    'actions':['rescan'] if fault == 'actions' else []}
            kwargs['stdout'].write('not-json' if fault == 'malformed' else json.dumps(output))
            if fault == 'late': clock[0]=91
            return subprocess.CompletedProcess(argv, 0)
        return config,backend,events,clock,command

    def test_order_live_preconditions_single_cycle_and_no_program_or_mmio(self):
        """Wrong live state must prevent cycle; later failures cannot retry/program."""
        module=self.load()
        faults=(None,'boot_before','authorized_before','uuid_before','endpoint_before',
                'subsystem_before','class_before','bar_before','command_before','link_before',
                'cycle','boot_after','authorized_after','subsystem_after','bar_after',
                'not_ready','actions','malformed','late')
        for fault in faults:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                config,backend,events,clock,command=self.fixture(module,root,fault)
                output=root/'receipt.json'
                with patch.object(module.core.subprocess,'run',side_effect=command), \
                     patch.object(module, 'admit_disk', return_value={'minimum_free_bytes': 2 << 30}), \
                     patch.object(module.core.time,'monotonic',side_effect=lambda:clock[0]), \
                     patch.object(module.core.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,91)):
                    status=module.run_gate(config,backend,output)
                receipt=json.loads(output.read_text())
                self.assertEqual(status,0 if fault is None else 1)
                self.assertEqual(receipt['status'],'PASS' if fault is None else 'FAIL')
                self.assertFalse(receipt['mmio_accessed'])
                if fault is None:
                    self.assertEqual(events,['cycle','probe'])
                    with self.assertRaises(RuntimeError): backend.lifecycle()
                elif fault.endswith('_before'): self.assertEqual(events,[])
                else: self.assertEqual(events.count('cycle'),1)
                saved=output.read_bytes()
                self.assertEqual(module.run_gate(config,backend,output),1)
                self.assertEqual(output.read_bytes(),saved)
                with self.assertRaises(RuntimeError):
                    backend.command('program',['openFPGALoader','--write-flash'],1)

    def test_cli_has_no_program_or_evidence_override_paths(self):
        """No caller flag can select programming, another image or another prior run."""
        self.load()
        with tempfile.TemporaryDirectory() as temporary:
            for flag in ('--program','--program-mode','--image','--model','--replay','--manifest','--program-log'):
                result=subprocess.run([sys.executable,str(SCRIPT),'--receipt',str(Path(temporary)/'receipt.json'),
                                       flag,'untrusted'],capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,2)

    def test_low_disk_admission_prevents_the_only_hardware_command(self):
        """Below 64MiB cannot admit the pre-materialized runtime's only operation."""
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, backend, events, clock, command = self.fixture(module, root, None)
            with patch.object(shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(10 << 30, 9 << 30, 63 << 20)), \
                 patch.object(module.core.subprocess, 'run', side_effect=command):
                self.assertEqual(module.run_gate(config, backend, root / 'receipt.json'), 1)
            self.assertEqual(events, [])
            self.assertIn('disk', json.loads((root / 'receipt.json').read_text())['error'])

    def test_reserved_snapshots_and_worker_failure_survive_enospc(self):
        """Real allocated evidence slots must remain until publication, not be sparse."""
        module = self.load()
        self.assertTrue(hasattr(module, 'EvidenceReserve'), 'missing protected evidence capacity')
        for location in ('checkpoint', 'command'):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config, backend, events, clock, command = self.fixture(module, root, None)
                public = root / 'final.json'; worker = Path(str(public) + '.worker.json')
                enough = shutil._ntuple_diskusage(10 << 30, 2 << 30, 8 << 30)
                with patch.object(shutil, 'disk_usage', return_value=enough):
                    reserve = module.EvidenceReserve(public, create=True)
                    self.assertEqual(sum(p.stat().st_size for p in reserve.directory.iterdir()), 8 << 20)
                    self.assertTrue(all(p.stat().st_blocks * 512 >= 1 << 20 for p in reserve.directory.iterdir()))
                    original_checkpoint = module.BASE_CHECKPOINT
                    def checkpoint(receipt):
                        if location == 'checkpoint': raise OSError(errno.ENOSPC, 'injected checkpoint full')
                        return original_checkpoint(receipt)
                    def execute(argv, **kwargs):
                        if location == 'command': raise OSError(errno.ENOSPC, 'injected command log full')
                        return command(argv, **kwargs)
                    try:
                        with reserve.protect(worker=True, identity=config['continuation_runner']), \
                             patch.object(module, 'BASE_CHECKPOINT', side_effect=checkpoint), \
                             patch.object(module.core.subprocess, 'run', side_effect=execute):
                            self.assertEqual(module.run_gate(config, backend, worker), 1)
                        receipt = json.loads(worker.read_text())
                        self.assertEqual(receipt['status'], 'FAIL')
                        self.assertIn('injected', receipt['error'])
                        self.assertTrue((reserve.directory / 'parent-final').exists())
                        self.assertFalse((reserve.directory / 'worker-final').exists())
                    finally: reserve.close()
                self.assertFalse(reserve.directory.exists())

    def test_supervisor_final_enospc_releases_emergency_before_retry(self):
        """An ENOSPC terminal write must produce immutable FAIL, never lose the run."""
        module = self.load()
        self.assertTrue(hasattr(module, 'EvidenceReserve'), 'missing terminal evidence reserve')
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary) / 'receipt.json'
            worker = Path(str(public) + '.worker.json')
            script = f"from pathlib import Path; Path({str(worker)!r}).write_text('{{\"status\":\"PASS\"}}')"
            enough = shutil._ntuple_diskusage(10 << 30, 2 << 30, 8 << 30)
            with patch.object(shutil, 'disk_usage', return_value=enough):
                reserve = module.EvidenceReserve(public, create=True)
                original = module.BASE_ATOMIC
                attempts = []
                injected = [False]
                original_fsync = module.os.fsync
                def fsync(fd):
                    path = module.os.readlink(f'/proc/self/fd/{fd}')
                    if path.endswith('.tmp') and not injected[0]:
                        injected[0] = True
                        raise OSError(errno.ENOSPC, 'injected actual receipt fsync full')
                    return original_fsync(fd)
                def publish(path, receipt):
                    self.assertFalse((reserve.directory / 'parent-final').exists())
                    attempts.append(receipt['status'])
                    if len(attempts) == 1:
                        self.assertTrue((reserve.directory / 'parent-emergency').exists())
                    else:
                        self.assertFalse((reserve.directory / 'parent-emergency').exists())
                    return original(path, receipt)
                try:
                    with reserve.protect(worker=False, identity=module.runner_identity()), \
                         patch.object(module, 'BASE_ATOMIC', side_effect=publish), \
                         patch.object(module.os, 'fsync', side_effect=fsync):
                        self.assertEqual(module.core.supervise([sys.executable, '-c', script], public, 5), 1)
                    receipt = json.loads(public.read_text())
                    self.assertEqual(attempts, ['PASS', 'FAIL'])
                    self.assertTrue(injected[0])
                    self.assertFalse(list(Path(temporary).glob('*.tmp')))
                    self.assertEqual(receipt['status'], 'FAIL')
                    self.assertIn('ENOSPC', receipt['error'])
                    self.assertEqual(receipt['continuation_runner']['sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
                finally: reserve.close()
            self.assertFalse(reserve.directory.exists())

    def test_reserve_allocation_failure_cleans_only_owned_capacity(self):
        """Failed fallocate cannot leave a partial reservation or authorize hardware."""
        module = self.load()
        self.assertTrue(hasattr(module, 'EvidenceReserve'), 'missing fail-closed reservation allocation')
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary) / 'receipt.json'
            enough = shutil._ntuple_diskusage(10 << 30, 2 << 30, 8 << 30)
            with patch.object(shutil, 'disk_usage', return_value=enough), \
                 patch.object(module.os, 'posix_fallocate', side_effect=OSError(errno.ENOSPC, 'injected allocation full')):
                with self.assertRaises(OSError): module.EvidenceReserve(public, create=True)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_supervisor_preserves_rejected_worker_hash_and_records_own_hash(self):
        """A worker self-hash rejection must not be overwritten by the parent hash."""
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            public = Path(temporary) / 'receipt.json'
            worker = Path(str(public) + '.worker.json')
            rejected = {'status': 'FAIL', 'continuation_runner': {'sha256': 'f' * 64}, 'error': 'worker self hash mismatch'}
            script = f'from pathlib import Path; Path({str(worker)!r}).write_text({json.dumps(rejected)!r}); raise SystemExit(1)'
            with patch.object(shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(10 << 30, 2 << 30, 8 << 30)):
                reserve = module.EvidenceReserve(public, create=True)
                try:
                    with reserve.protect(worker=False, identity=module.runner_identity()):
                        self.assertEqual(module.core.supervise([sys.executable, '-c', script], public, 5), 1)
                    receipt = json.loads(public.read_text())
                    self.assertEqual(receipt['continuation_runner']['sha256'], 'f' * 64)
                    self.assertEqual(receipt['continuation_runners']['parent']['sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
                finally: reserve.close()


if __name__ == '__main__': unittest.main()
