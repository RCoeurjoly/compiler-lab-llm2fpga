"""Execute wrapper copies with controlled external commands; never touch hardware."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'scripts/host/ypcb'


class PinnedWrapperTest(unittest.TestCase):
    def test_programming_isolation_installer_is_narrow_and_validates_sudoers(self):
        installer = SOURCES / 'install-programming-isolation'
        self.assertTrue(installer.exists(), 'missing one-time isolation installer')
        text = installer.read_text()
        self.assertIn('/usr/local/libexec/ypcb_thunderbolt_isolate.py', text)
        self.assertIn('/usr/local/sbin/ypcb-thunderbolt-isolate-for-programming', text)
        self.assertIn('/etc/sudoers.d/ypcb-thunderbolt-isolate', text)
        self.assertIn('/usr/sbin/visudo -cf', text)
        self.assertNotIn('NOPASSWD: ALL', text)
        result = subprocess.run(['/bin/bash', '-n', str(installer)], capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_tapo_fixed_runtime_exact_order_and_fail_closed(self):
        """A dynamic dependency resolver, wrong timing, or ignored off error is unsafe."""
        source = SOURCES / 'ypcb-tapo-cycle'
        self.assertTrue(source.exists(), 'missing installable no-Nix Tapo wrapper')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); log = root / 'commands'
            helper = root / 'python'
            helper.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$EVENTS"\n[[ "$*" != *"--state off"* || "${FAIL_OFF:-0}" != 1 ]]\n')
            helper.chmod(0o755)
            for name, body in {'id': 'echo 1000', 'sleep': 'echo "sleep $*" >> "$EVENTS"'}.items():
                path = root / name; path.write_text('#!/bin/bash\n' + body + '\n'); path.chmod(0o755)
            credentials = root / 'empty.env'; credentials.write_text('')
            wrapper = root / 'wrapper'
            wrapper.write_text(source.read_text().replace(
                '/home/roland/.local/share/ypcb-tapo-runtime/venv/bin/python', str(helper)).replace(
                '/home/roland/.config/task6-pcie/tapo.env', str(credentials)))
            env = {**os.environ, 'PATH': str(root) + ':/usr/bin:/bin', 'EVENTS': str(log)}
            result = subprocess.run(['/bin/bash', str(wrapper)], env=env, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            common = '-I -B /usr/local/libexec/ypcb_tapo_p115_power.py --backend tapo --host 192.168.1.136 --env-file ' + str(credentials)
            self.assertEqual(log.read_text().splitlines(), [common + ' --state off --expect-state off',
                'sleep 10', common + ' --state on --expect-state on', 'sleep 45'])
            log.unlink()
            result = subprocess.run(['/bin/bash', str(wrapper)], env={**env, 'FAIL_OFF': '1'}, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(log.read_text().splitlines()), 1)
            log.unlink()
            self.assertNotEqual(subprocess.run(['/bin/bash', str(wrapper), 'extra'], env=env,
                                              capture_output=True, timeout=5).returncode, 0)
            self.assertFalse(log.exists())

    def test_root_wrapper_uses_system_python_and_rejects_arguments(self):
        """Root controller startup must not invoke a dependency resolver."""
        source = SOURCES / 'ypcb-thunderbolt-cold-cycle'
        self.assertTrue(source.exists(), 'missing installable stdlib controller wrapper')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); helper = root / 'python'
            helper.write_text('#!/bin/bash\nprintf "%s\\n" "$*"\n'); helper.chmod(0o755)
            wrapper = root / 'wrapper'
            wrapper.write_text(source.read_text().replace('/usr/bin/python3', str(helper)))
            result = subprocess.run(['/bin/bash', str(wrapper)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), '-I -B /usr/local/libexec/ypcb_thunderbolt_deferred_auth.py cold-cycle')
            result = subprocess.run(['/bin/bash', str(wrapper), 'extra'], capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(result.stdout)
