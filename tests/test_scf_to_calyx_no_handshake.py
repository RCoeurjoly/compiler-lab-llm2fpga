import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "scf_to_calyx_no_handshake.sh"


class ScfToCalyxNoHandshakeTest(unittest.TestCase):
    def write_fake_circt(self, directory: Path, body: str) -> Path:
        tool = directory / "fake-circt-opt"
        tool.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        tool.chmod(0o755)
        return tool

    def run_wrapper(self, tool_body: str) -> tuple[dict[str, object], Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        input_mlir = root / "input.mlir"
        output_dir = root / "out"
        input_mlir.write_text(
            "module { func.func @main() { return } }\n", encoding="utf-8"
        )
        tool = self.write_fake_circt(root, tool_body)
        result = subprocess.run(
            ["bash", str(SCRIPT), str(tool), str(input_mlir), str(output_dir)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return (
            json.loads((output_dir / "manifest.json").read_text(encoding="utf-8")),
            output_dir,
        )

    def test_rejects_zero_exit_error_diagnostic_and_partial_file(self) -> None:
        manifest, output_dir = self.run_wrapper(
            """
output=""
for ((index=1; index <= $#; index++)); do
  if [[ "${!index}" == "-o" ]]; then
    next=$((index + 1))
    output="${!next}"
  fi
done
printf 'error: Unhandled operation during BuildOpGroups()\\n' >&2
printf 'calyx.component @partial() {}\\n' > "$output"
exit 0
"""
        )

        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["exit_code"], 0)
        self.assertTrue(manifest["diagnostic_error"])
        self.assertTrue(manifest["partial_output_discarded"])
        self.assertFalse((output_dir / "model.calyx.mlir").exists())
        self.assertIn(
            "Unhandled operation",
            (output_dir / "lower-scf-to-calyx.log").read_text(encoding="utf-8"),
        )

    def test_accepts_clean_zero_exit_nonempty_output(self) -> None:
        manifest, output_dir = self.run_wrapper(
            """
output=""
for ((index=1; index <= $#; index++)); do
  if [[ "${!index}" == "-o" ]]; then
    next=$((index + 1))
    output="${!next}"
  fi
done
printf 'calyx.component @main() {}\\n' > "$output"
exit 0
"""
        )

        self.assertEqual(
            manifest,
            {"stage": "calyx", "status": "ok", "artifact": "model.calyx.mlir"},
        )
        self.assertTrue((output_dir / "model.calyx.mlir").is_file())


if __name__ == "__main__":
    unittest.main()
