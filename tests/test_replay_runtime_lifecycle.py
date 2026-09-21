"""Runtime tooling authentication controls; no hardware or external commands."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'scripts/pipeline/run_compiler_ddr3_trace_replay.py'
NAMES = ('runner', 'cold_cycle_wrapper', 'cold_cycle_controller', 'lifecycle_probe',
         'lifecycle_dependency', 'tapo_wrapper', 'tapo_power_script',
         'controller_python', 'tapo_python')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(root):
    paths = {name: root / name for name in NAMES}
    for name, path in paths.items():
        path.write_text('controlled ' + name)
    runtime = root / 'venv'
    runtime.mkdir()
    (runtime / 'package.py').write_bytes(b'package')
    (runtime / 'python').symlink_to(paths['tapo_python'])
    rows = [['package.py', 7, hashlib.sha256(b'package').hexdigest()],
            ['python', 'symlink', str(paths['tapo_python'])]]
    document = {'schema': 'pcie-runtime-lifecycle-manifest-v1',
                'runtime_tree': {'path': str(runtime), 'entries': 2,
                                 'sha256': hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()},
                'artifacts': {name: {'path': str(path), 'bytes': path.stat().st_size,
                                     'sha256': sha(path)} for name, path in paths.items()}}
    manifest = root / 'runtime.json'
    manifest.write_text(json.dumps(document))
    return paths, runtime, document, manifest


class RuntimeLifecycleTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('runtime_replay', RUNNER)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)

    def test_reviewed_manifest_authenticates_current_install_without_changing_history(self):
        """The real manifest must pin the current no-Nix install, not the old wrapper."""
        manifest = ROOT / 'artifacts/reference/pcie-runtime-lifecycle-manifest.json'
        self.assertTrue(manifest.exists(), 'new runtime-only manifest must be retained for review')
        actual = self.runner.authenticate_runtime_lifecycle(manifest, sha(manifest))
        self.assertEqual(actual['cold_cycle_wrapper']['sha256'],
                         'fd5204da90cb9df14efe64421062d2309dcaed08517397b8866ea410d1c0ed0f')
        self.assertEqual(actual['cold_cycle_controller']['sha256'],
                         'a188e99a87233e8591c67d9d6f2c82e243004e262253686ade7e018ec8f39095')
        self.assertEqual(sha(ROOT / 'artifacts/reference/compiler-ddr3-trace-replay-bitstream.json'),
                         '9ffb546ff379ba3461a8819768250d8f93054dd046eb610c5f6be3ad820a76b7')
        self.assertEqual(sha(ROOT / 'artifacts/reference/pcie-smoke-lifecycle-manifest.json'),
                         'ac77b9f83e5d46a26db787df090267350506a8f4711892059b420decfaf4fc48')

    def test_runtime_supersedes_only_executables_not_historical_build_evidence(self):
        """Reading obsolete installed-wrapper hashes must not block current tooling."""
        self.assertTrue(hasattr(self.runner, 'bind_runtime_lifecycle'),
                        'runner needs a separate authenticated runtime contract')
        with tempfile.TemporaryDirectory() as tmp:
            paths, runtime, document, manifest = fixture(Path(tmp))
            build = {name: {'path': '/historical/' + name, 'bytes': 1, 'sha256': '0' * 64}
                     for name in ('runner', 'cold_cycle_wrapper', 'cold_cycle_controller',
                                  'lifecycle_probe', 'lifecycle_dependency', 'bitstream', 'netlist', 'source')}
            before = copy.deepcopy(build)
            with patch.object(self.runner, 'LIFECYCLE_PATHS', paths), \
                 patch.object(self.runner, 'LIFECYCLE_RUNTIME_ROOT', runtime):
                actual = self.runner.bind_runtime_lifecycle(build, manifest, sha(manifest))
            self.assertEqual(build, before)
            for name in ('bitstream', 'netlist', 'source'):
                self.assertEqual(actual[name], before[name])
            for name in NAMES:
                self.assertEqual(actual[name], document['artifacts'][name])
            self.assertEqual(actual['runtime_manifest']['sha256'], sha(manifest))
            self.assertIn('runtime:package.py', actual)

    def test_manifest_installed_files_and_complete_runtime_tree_fail_closed(self):
        """Skipping a hash, path, size, required entry or tree check must fail."""
        self.assertTrue(hasattr(self.runner, 'authenticate_runtime_lifecycle'))
        faults = ('manifest_hash', 'schema', 'missing', 'extra', 'path', 'size',
                  'wrapper', 'controller', 'unreadable', 'tree_missing', 'tree_extra',
                  'tree_content', 'tree_symlink', 'tree_path', 'tree_entries')
        for fault in faults:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp:
                paths, runtime, doc, manifest = fixture(Path(tmp))
                if fault == 'schema': doc['schema'] = 'wrong'
                if fault == 'missing': del doc['artifacts']['cold_cycle_controller']
                if fault == 'extra': doc['artifacts']['bitstream'] = doc['artifacts']['runner']
                if fault == 'path': doc['artifacts']['cold_cycle_wrapper']['path'] = str(paths['runner'])
                if fault == 'size': doc['artifacts']['cold_cycle_controller']['bytes'] += 1
                if fault == 'wrapper': paths['cold_cycle_wrapper'].write_text('tampered')
                if fault == 'controller': paths['cold_cycle_controller'].write_text('tampered')
                if fault == 'unreadable':
                    paths['cold_cycle_controller'].unlink()
                    paths['cold_cycle_controller'].mkdir()
                if fault == 'tree_missing': (runtime / 'package.py').unlink()
                if fault == 'tree_extra': (runtime / 'extra.py').write_text('extra')
                if fault == 'tree_content': (runtime / 'package.py').write_text('changed')
                if fault == 'tree_symlink':
                    (runtime / 'python').unlink()
                    (runtime / 'python').symlink_to(paths['runner'])
                if fault == 'tree_path': doc['runtime_tree']['path'] = str(runtime.parent)
                if fault == 'tree_entries': doc['runtime_tree']['entries'] = 99
                manifest.write_text(json.dumps(doc))
                expected = '0' * 64 if fault == 'manifest_hash' else sha(manifest)
                with patch.object(self.runner, 'LIFECYCLE_PATHS', paths), \
                     patch.object(self.runner, 'LIFECYCLE_RUNTIME_ROOT', runtime):
                    with self.assertRaises((ValueError, OSError)):
                        self.runner.authenticate_runtime_lifecycle(manifest, expected)

    def test_parent_and_worker_require_runtime_authentication_before_execution(self):
        """Both CLI roles must reject changed runtime before supervisor/backend."""
        self.assertTrue(hasattr(self.runner, 'bind_runtime_lifecycle'))
        for worker in (False, True):
            with self.subTest(worker=worker), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                paths, runtime, doc, manifest = fixture(root)
                expected = sha(manifest)
                paths['cold_cycle_wrapper'].write_text('changed after review')
                output = root / 'receipt.json'
                argv = [str(RUNNER), '--package', str(ROOT / 'artifacts/reference/tinystories-1m-compiler-ddr3-trace-replay.json'),
                        '--bitstream-receipt', str(ROOT / 'artifacts/reference/compiler-ddr3-trace-replay-bitstream.json'),
                        '--image', '/unused-image', '--receipt', str(output),
                        '--lifecycle-manifest', str(manifest), '--lifecycle-manifest-sha256', expected]
                if worker: argv.append('--worker')
                def forbidden(*args, **kwargs):
                    self.fail('execution boundary reached before runtime authentication')
                with patch.object(sys, 'argv', argv), \
                     patch.object(self.runner, 'LIFECYCLE_PATHS', paths), \
                     patch.object(self.runner, 'LIFECYCLE_RUNTIME_ROOT', runtime), \
                     patch.object(self.runner, 'supervise', side_effect=forbidden), \
                     patch.object(self.runner, 'HardwareBackend', side_effect=forbidden):
                    self.assertEqual(self.runner.main(), 1)
                receipt = Path(str(output) + '.worker.json') if worker else output
                result = json.loads(receipt.read_text())
                self.assertEqual(result['status'], 'FAIL')
                self.assertIn('cold_cycle_wrapper', result['error'])

    def test_changed_runtime_is_rejected_immediately_before_cold_cycle(self):
        """A tool changed during long BPI verification cannot reach cold-cycle."""
        with tempfile.TemporaryDirectory() as tmp:
            paths, runtime, doc, manifest = fixture(Path(tmp))
            config = {'artifacts': {'runtime_manifest': {'path': str(manifest), 'sha256': sha(manifest)}}}
            backend = self.runner.HardwareBackend(config)
            backend.verified = True
            paths['cold_cycle_controller'].write_text('changed during programming')
            events = []
            def command(*args, **kwargs):
                events.append('cold-cycle')
                self.fail('unsafe cold-cycle command reached before runtime reauthentication')
            # External sysfs and actual process execution are replaced; auth is real.
            with patch.object(backend, 'isolation', return_value={'authorized': '0'}), \
                 patch.object(backend, 'command', side_effect=command), \
                 patch.object(self.runner, 'LIFECYCLE_PATHS', paths, create=True), \
                 patch.object(self.runner, 'LIFECYCLE_RUNTIME_ROOT', runtime, create=True):
                with self.assertRaisesRegex(ValueError, 'cold_cycle_controller'):
                    backend.lifecycle()
            self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
