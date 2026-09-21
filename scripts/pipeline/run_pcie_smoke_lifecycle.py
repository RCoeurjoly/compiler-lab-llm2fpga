"""Authenticated known-good smoke BPI/lifecycle comparison; never accesses MMIO.

Requires pre-existing exact Helios isolation. This program cannot isolate,
rescan, reset, or recover the device. PASS means PCIe presence only, not DDR3,
compiler replay, or inference acceptance. Hardware use requires separate review.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


TRUSTED = {
    'bitstream': '276442d6348b330b55b8e8bde55e5a409456abfc869be014d767eb3a53ee7bab',
    'backend': 'e3f5d0494cffb4c9b9c22efec05597ab254f4abc11755a111e74e7e41c68ef7f',
    'programmer': '8686c42aabac9d720f128741d3f6fe27de8b8b9e5615f02c3d1450d78b759740',
    'programmer_bridge': 'c8f3e306cbd789926284ec221769c426473b724ad349ccd42c620a35b1ec9ec2',
    'programmer_nix': '78e98de1be5a4837cb1bfdb6bfc0cf063065725d0eb20b7746d0c64969da4f9c',
    'programmer_bpi_bridge_patch': '0a5218abb83de98f40c27d8cd80e3e3ef56346064345a52825b192158e7b3b47',
    'programmer_full_verify_patch': '9633bc2fcddadf633e66114e0077248104a0a386eadeae1fba7edaa2770d24f7',
    'lifecycle_probe': '25a8e0fb244958e39b4854dcc4f38b2a570d818dbb90f75cc3ea01d8ac9949a6',
    'lifecycle_dependency': '3f6a844bb7c25383ab1c5c574f3b1ef54c740ce3f315b9155804609ef7c2ea25',
    'cold_cycle_wrapper': '2870b3ef5def65a7d8ede7e1a45cfb7503e093719d5366fe407cb47ebd545f4c',
    'cold_cycle_controller': 'a188e99a87233e8591c67d9d6f2c82e243004e262253686ade7e018ec8f39095',
}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


BACKEND = Path(__file__).resolve().with_name('run_compiler_ddr3_trace_replay.py')
if digest(BACKEND) != TRUSTED['backend']:
    raise RuntimeError('reviewed lifecycle backend changed; refusing import')
spec = importlib.util.spec_from_file_location('reviewed_replay_backend', BACKEND)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def authenticate(path, expected_hash):
    path = Path(path)
    if digest(path) != expected_hash:
        raise ValueError('smoke manifest hash mismatch')
    manifest = json.loads(path.read_text())
    if (manifest.get('schema') != 'pcie-smoke-lifecycle-manifest-v1'
            or manifest.get('payload_bytes') != 18735004
            or manifest.get('programmer_commit') != '3ae5e5e4a5f055d12f6079616cb1ec1d67bf30f1'):
        raise ValueError('wrong smoke manifest contract')
    artifacts = manifest['artifacts']
    if set(artifacts) != set(TRUSTED) | {'harness'}:
        raise ValueError('unexpected or missing smoke artifact')
    for name, artifact in artifacts.items():
        expected = TRUSTED.get(name, digest(__file__))
        if artifact['sha256'] != expected:
            raise ValueError(name + ' is not the reviewed artifact')
        target = Path(artifact['path'])
        if target.stat().st_size != artifact['bytes'] or digest(target) != expected:
            raise ValueError(name + ' artifact hash/size mismatch')
    if artifacts['bitstream']['bytes'] != 18735152:
        raise ValueError('wrong complete smoke bitstream length')
    for name, target in {'backend': BACKEND, 'harness': Path(__file__),
                         'cold_cycle_wrapper': Path('/usr/local/sbin/ypcb-thunderbolt-cold-cycle'),
                         'cold_cycle_controller': Path('/usr/local/libexec/ypcb_thunderbolt_deferred_auth.py'),
                         'lifecycle_probe': Path('/usr/local/libexec/ypcb_pcie_recover.py'),
                         'lifecycle_dependency': Path('/usr/local/libexec/ypcb_pcie_power.py')}.items():
        if Path(artifacts[name]['path']).resolve() != target.resolve():
            raise ValueError(name + ' does not authenticate the executed path')
    artifacts = dict(artifacts)
    artifacts['manifest'] = {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': expected_hash}
    return {'artifacts': artifacts, 'program_mode': 'bpi', 'program_timeout': 21600,
            'bpi_verification': 'full-readback-v1', 'bitstream_payload_bytes': 18735004,
            'lifecycle_timeout': 90, 'programmer': artifacts['programmer']['path'],
            'lifecycle_probe': artifacts['lifecycle_probe']['path']}


class SmokeBackend(core.HardwareBackend):
    """Reviewed hardware gates with a hard 90-second classification deadline."""
    probe_deadline = None

    def command(self, label, argv, timeout):
        if label.startswith('probe-'):
            now = core.time.monotonic()
            if self.probe_deadline is None:
                self.probe_deadline = now + 90
            remaining = self.probe_deadline - now
            if remaining <= 0:
                raise RuntimeError('smoke lifecycle deadline expired')
            result = super().command(label, argv, min(timeout, remaining))
            if core.time.monotonic() >= self.probe_deadline:
                raise RuntimeError('smoke lifecycle deadline expired during probe')
            return result
        return super().command(label, argv, timeout)

    def open(self):
        raise RuntimeError('smoke lifecycle harness forbids MMIO')

    def lifecycle(self):
        result = super().lifecycle()
        if self.probe_deadline is None or core.time.monotonic() >= self.probe_deadline:
            raise RuntimeError('smoke lifecycle deadline expired during identity validation')
        return result


def run_gate(config, backend, output):
    if Path(output).exists():
        return 1
    receipt = {'schema': 'pcie-smoke-lifecycle-result-v1', 'status': 'FAIL',
               'scope': 'known-good smoke enumeration comparison only; no MMIO/DDR/replay/inference',
               'mmio_accessed': False, 'stage': 'authentication',
               'checkpoint_path': str(output) + '.snapshot.json', 'backend': backend.evidence}
    started = core.time.monotonic()
    try:
        core.checkpoint(receipt)
        for name, artifact in config['artifacts'].items():
            path = Path(artifact['path'])
            if path.stat().st_size != artifact['bytes'] or digest(path) != artifact['sha256']:
                raise ValueError(name + ' changed after manifest authentication')
        receipt['artifacts'] = config['artifacts']
        receipt['stage'] = 'isolation'
        core.checkpoint(receipt)
        receipt['isolation'] = backend.isolation()
        receipt['stage'] = 'program'
        core.checkpoint(receipt)
        receipt['program'] = backend.program()  # Rechecks exact isolation here.
        receipt['stage'] = 'lifecycle'
        core.checkpoint(receipt)
        receipt['lifecycle'] = backend.lifecycle()
        if receipt['lifecycle']['classification'] != 'pcie_ready':
            raise RuntimeError('smoke endpoint not ready')
        receipt.update(status='PASS', stage='complete')
    except Exception as error:
        receipt['error'] = str(error)
    receipt['elapsed_seconds'] = core.time.monotonic() - started
    core.atomic_receipt(output, receipt)
    return 0 if receipt['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.receipt.exists():
        return 1
    target = Path(str(args.receipt) + '.worker.json') if args.worker else args.receipt
    if target.exists():
        return 1
    try:
        config = authenticate(args.manifest, args.manifest_sha256)
        config['log_prefix'] = str(args.receipt)
        if not args.worker:
            if any(args.receipt.parent.glob(args.receipt.name + '.*')):
                raise ValueError('receipt/log prefix already used; choose a fresh path')
            return core.supervise([sys.executable, str(Path(__file__).resolve()),
                                   *sys.argv[1:], '--worker'], args.receipt, 22320)
        return run_gate(config, SmokeBackend(config), target)
    except Exception as error:
        core.atomic_receipt(target, {'schema': 'pcie-smoke-lifecycle-result-v1',
                                    'status': 'FAIL', 'stage': 'preflight', 'error': str(error)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
