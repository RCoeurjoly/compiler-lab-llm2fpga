import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-commit"
INSTALLER = ROOT / "scripts" / "agent" / "install_git_hooks.sh"


class GitHygieneHookTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Git Hygiene Test"],
            cwd=self.repo,
            check=True,
        )

        hooks = self.repo / ".githooks"
        scripts = self.repo / "scripts" / "agent"
        hooks.mkdir()
        scripts.mkdir(parents=True)
        shutil.copy2(HOOK, hooks / "pre-commit")
        shutil.copy2(INSTALLER, scripts / "install_git_hooks.sh")
        os.chmod(hooks / "pre-commit", 0o755)
        os.chmod(scripts / "install_git_hooks.sh", 0o755)
        subprocess.run(["git", "add", ".githooks", "scripts"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "commit", "--no-verify", "-qm", "install hook fixtures"],
            cwd=self.repo,
            check=True,
        )
        subprocess.run([str(scripts / "install_git_hooks.sh")], cwd=self.repo, check=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def write(self, relative_path: str, contents: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def commit(self):
        return subprocess.run(
            ["git", "commit", "-m", "test commit"],
            cwd=self.repo,
            text=True,
            capture_output=True,
        )

    def test_commit_succeeds_when_all_changes_are_staged(self):
        self.write("tracked.txt", "staged\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)

        result = self.commit()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_commit_rejects_untracked_files(self):
        self.write("tracked.txt", "staged\n")
        self.write("forgotten.txt", "untracked\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)

        result = self.commit()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("untracked files remain", result.stderr)

    def test_commit_rejects_unstaged_changes(self):
        self.write("tracked.txt", "initial\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        self.assertEqual(self.commit().returncode, 0)
        self.write("tracked.txt", "unstaged\n")
        self.write("staged.txt", "staged\n")
        subprocess.run(["git", "add", "staged.txt"], cwd=self.repo, check=True)

        result = self.commit()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unstaged changes remain", result.stderr)

    def test_ignored_files_do_not_block_commit(self):
        self.write(".gitignore", "build/\n")
        self.write("tracked.txt", "staged\n")
        self.write("build/generated.bin", "ignored\n")
        subprocess.run(
            ["git", "add", ".gitignore", "tracked.txt"], cwd=self.repo, check=True
        )

        result = self.commit()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_installer_configures_repository_hooks_path(self):
        configured = subprocess.run(
            ["git", "config", "--local", "--get", "core.hooksPath"],
            cwd=self.repo,
            check=True,
            text=True,
            capture_output=True,
        )

        self.assertEqual(configured.stdout.strip(), ".githooks")


if __name__ == "__main__":
    unittest.main()
