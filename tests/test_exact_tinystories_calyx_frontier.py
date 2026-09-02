#!/usr/bin/env python3
"""Mutation and replay tests for the exact TinyStories Calyx receipt."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/pipeline/verify_exact_tinystories_calyx_frontier.py"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _binding(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"path": path.name, "bytes": len(data), "sha256": _sha256(data)}


def _signed(value: dict[str, object]) -> dict[str, object]:
    unsigned = {key: item for key, item in value.items() if key != "sha256"}
    value["sha256"] = _sha256(_canonical_json(unsigned))
    return value


def _load_verifier():
    spec = importlib.util.spec_from_file_location("exact_calyx_frontier", VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExactTinyStoriesCalyxFrontierTest(unittest.TestCase):
    """The production changes named by these tests would weaken provenance."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_verifier()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="exact-calyx-frontier-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.predecessor = self.root / "predecessor"
        self.predecessor.mkdir()
        self.input = self.predecessor / "pre-calyx.mlir"
        self.input.write_text(
            "module { func.func @main() { return } }\n", encoding="utf-8"
        )
        self.receipt_path = self.predecessor / "pre-calyx-legality.json"
        receipt = _signed(
            {
                "first_locations": {},
                "parser_validation": {"identity_status": "verified"},
                "prohibited_ops": {},
                "scanner_diagnostics": [],
                "schema_version": 3,
                "status": "ok",
            }
        )
        self.receipt_path.write_bytes(_canonical_json(receipt) + b"\n")
        self.input_sha256 = _sha256(self.input.read_bytes())
        self.receipt_self_sha256 = str(receipt["sha256"])
        (self.predecessor / "manifest.json").write_bytes(
            _canonical_json(
                {
                    "calyx_authorized": True,
                    "preparation": {
                        "output": {
                            "path": "pre-calyx.mlir",
                            "bytes": self.input.stat().st_size,
                            "sha256": self.input_sha256,
                        },
                        "legality": {
                            "path": "pre-calyx-legality.json",
                            "receipt_sha256": self.receipt_self_sha256,
                            "sha256": _sha256(self.receipt_path.read_bytes()),
                            "status": "ok",
                        },
                    },
                }
            )
            + b"\n"
        )

        self.mode = self.root / "mode"
        self.mode.write_text("failed\n", encoding="utf-8")
        self.tool = self.root / "fake-circt-opt"
        self.tool.write_text(
            r"""#!/usr/bin/env python3
from pathlib import Path
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("fake-circt-opt 1.0")
    sys.exit(0)
output = Path(args[args.index("-o") + 1])
if "--lower-scf-to-calyx=top-level-function=main" not in args:
    if str(output) != "/dev/null":
        output.write_bytes(Path(args[0]).read_bytes())
    sys.exit(0)
mode = Path(__file__).with_name("mode").read_text().strip()
output.write_text("calyx.component @main() {}\n", encoding="utf-8")
sys.stdout.write(f"note: wrote {output}\n")
if mode == "failed":
    sys.stderr.write("error: stable compiler frontier\n")
    sys.exit(1)
sys.exit(0)
""",
            encoding="utf-8",
        )
        self.tool.chmod(0o755)
        self.tool_sha256 = _sha256(self.tool.read_bytes())

        old_prepared = self.module.EXPECTED_PREPARED_SHA256
        old_receipt = self.module.EXPECTED_RECEIPT_SELF_SHA256
        old_tool_path = self.module.EXPECTED_CIRCT_OPT_PATH
        old_tool = self.module.EXPECTED_CIRCT_OPT_SHA256
        self.module.EXPECTED_PREPARED_SHA256 = self.input_sha256
        self.module.EXPECTED_RECEIPT_SELF_SHA256 = self.receipt_self_sha256
        self.module.EXPECTED_CIRCT_OPT_PATH = str(self.tool)
        self.module.EXPECTED_CIRCT_OPT_SHA256 = self.tool_sha256
        self.addCleanup(
            lambda: setattr(self.module, "EXPECTED_PREPARED_SHA256", old_prepared)
        )
        self.addCleanup(
            lambda: setattr(self.module, "EXPECTED_RECEIPT_SELF_SHA256", old_receipt)
        )
        self.addCleanup(
            lambda: setattr(self.module, "EXPECTED_CIRCT_OPT_PATH", old_tool_path)
        )
        self.addCleanup(
            lambda: setattr(self.module, "EXPECTED_CIRCT_OPT_SHA256", old_tool)
        )

        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        self.log = self.bundle / "lower-scf-to-calyx.log"
        self.log.write_text(
            f"note: wrote {self.bundle / '.candidate.calyx.mlir'}\n"
            "error: stable compiler frontier\n",
            encoding="utf-8",
        )
        self.partial = self.bundle / "partial.calyx.mlir"
        self.partial.write_text("calyx.component @main() {}\n", encoding="utf-8")
        self.manifest_path = self.bundle / "manifest.json"
        self._write_failed_manifest()

    def _base_manifest(self) -> dict[str, object]:
        return {
            "schema": "tinystories-1m-exact-calyx-stage-v1",
            "stage": "calyx",
            "status": "failed",
            "artifact_accepted": False,
            "first_diagnostic": "error: stable compiler frontier",
            "exit_code": 1,
            "parse_exit_code": 0,
            "command": [
                str(self.tool),
                str(self.input),
                "--lower-scf-to-calyx=top-level-function=main",
                "-o",
                str(self.bundle / ".candidate.calyx.mlir"),
            ],
            "input": _binding(self.input),
            "log": _binding(self.log),
            "circt_opt": {
                **_binding(self.tool),
                "version_exit_code": 0,
                "version": "fake-circt-opt 1.0",
            },
            "derivation": str(self.bundle),
            "artifact": None,
            "partial_artifact": _binding(self.partial),
        }

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        self.manifest_path.write_bytes(_canonical_json(_signed(manifest)) + b"\n")

    def _write_failed_manifest(self) -> None:
        self._write_manifest(self._base_manifest())

    def _mutate_manifest(self, mutator) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        mutator(manifest)
        self._write_manifest(manifest)

    def _timebox_evidence(self) -> dict[str, object]:
        candidate = self.root / ".candidate.calyx.mlir"
        model = self.root / "model.calyx.mlir"
        return {
            "schema": "tinystories-1m-exact-calyx-timebox-evidence-v1",
            "status": "terminated_at_deadline",
            "frontier": "calyx_scalability_frontier",
            "start_time": "2026-09-01T15:46:46+02:00",
            "deadline_time": "2026-09-02T15:46:46+02:00",
            "observed_at": "2026-09-02T15:46:46+02:00",
            "elapsed_wall_seconds": 86400.0,
            "elapsed_cpu_seconds": 90030.0,
            "max_rss_kb": 820000,
            "command": [
                str(self.tool),
                str(self.input),
                "--lower-scf-to-calyx=top-level-function=main",
                "-o",
                str(candidate),
            ],
            "input": _binding(self.input),
            "circt_opt": {
                **_binding(self.tool),
                "version_exit_code": 0,
                "version": "fake-circt-opt 1.0",
            },
            "no_output_observation": {
                "candidate": {"path": str(candidate), "exists": False},
                "model_artifact": {"path": str(model), "exists": False},
            },
            "processes": [
                {
                    "role": "nix",
                    "pid": 2530843,
                    "stat": "Ssl",
                    "elapsed": "24:00:00",
                    "time": "00:00:00",
                    "rss_kb": 38260,
                    "command": "nix build .#tiny-stories-1m-kev-gpt-exact-calyx-frontier -L",
                },
                {
                    "role": "runner",
                    "pid": 2530918,
                    "stat": "S",
                    "elapsed": "24:00:00",
                    "time": "00:00:00",
                    "rss_kb": 19628,
                    "command": "python3 run_exact_tinystories_calyx.py",
                },
                {
                    "role": "circt-opt",
                    "pid": 2530919,
                    "stat": "Rl",
                    "elapsed": "24:00:00",
                    "time": "25:00:30",
                    "rss_kb": 820000,
                    "command": "circt-opt pre-calyx.mlir --lower-scf-to-calyx=top-level-function=main",
                },
            ],
            "termination": {
                "signal": "SIGTERM",
                "target_pids": [2530919, 2530918, 2530843],
                "sent_at": "2026-09-02T15:46:50+02:00",
            },
        }

    def _write_timebox_evidence(self, evidence: dict[str, object]) -> Path:
        path = self.root / "timebox-evidence.json"
        path.write_bytes(_canonical_json(_signed(evidence)) + b"\n")
        return path

    def _point_verifier_at_reproducer_dir(self, path: Path) -> None:
        had_attribute = hasattr(self.module, "DEFAULT_REPRODUCER_DIR")
        old_value = getattr(self.module, "DEFAULT_REPRODUCER_DIR", None)
        self.module.DEFAULT_REPRODUCER_DIR = path

        def restore() -> None:
            if had_attribute:
                self.module.DEFAULT_REPRODUCER_DIR = old_value
            else:
                delattr(self.module, "DEFAULT_REPRODUCER_DIR")

        self.addCleanup(restore)

    def test_accepts_reproduced_compiler_frontier_and_self_hashes_receipt(self) -> None:
        """Rejecting an independently reproduced diagnostic would lose the frontier."""
        result = self.module.verify_bundle(self.bundle, self.predecessor)

        self.assertEqual(result["status"], "compiler_frontier")
        self.assertEqual(result["frontier"], "calyx_frontier")
        self.assertEqual(result["first_diagnostic"], "error: stable compiler frontier")
        unsigned = {key: value for key, value in result.items() if key != "sha256"}
        self.assertEqual(result["sha256"], _sha256(_canonical_json(unsigned)))

    def test_canonical_receipt_ignores_temporary_replay_log_paths(self) -> None:
        """Binding scratch-directory text would make identical replays noncanonical."""
        first = self.module.verify_bundle(self.bundle, self.predecessor)
        second = self.module.verify_bundle(self.bundle, self.predecessor)

        self.assertEqual(first, second)

    def test_failed_receipt_binds_not_practical_minimization_sidecar(self) -> None:
        """Dropping bounded-reducer evidence would understate a verified frontier."""
        repro_dir = self.root / "reproducers" / "tinystories-1m-exact-calyx-frontier"
        repro_dir.mkdir(parents=True)
        self._point_verifier_at_reproducer_dir(repro_dir)
        reducer_log = repro_dir / "mlir-reduce.log"
        reducer_log.write_text("timed out before first full-input interestingness pass\n")
        command = [
            "nix",
            "develop",
            "-c",
            "mlir-reduce",
            "--test=reproducers/tinystories-1m-exact-calyx-frontier/interesting.sh",
            str(self.input),
            "-o",
            "reproducers/tinystories-1m-exact-calyx-frontier/minimal.mlir",
        ]
        sidecar = _signed(
            {
                "schema": "tinystories-1m-exact-calyx-minimization-v1",
                "status": "not_practical",
                "first_diagnostic": "error: stable compiler frontier",
                "command": command,
                "elapsed_seconds": 120.0,
                "full_input": _binding(self.input),
                "reducer_log": _binding(reducer_log),
            }
        )
        (repro_dir / "minimization.json").write_bytes(
            _canonical_json(sidecar) + b"\n"
        )

        result = self.module.verify_bundle(self.bundle, self.predecessor)

        self.assertEqual(result["minimization"], sidecar)

    def test_accepts_replayed_valid_calyx_artifact(self) -> None:
        """Classifying a valid parsed main component as failure would hide success."""
        self.mode.write_text("complete\n", encoding="utf-8")
        self.log.write_bytes(b"")
        manifest = self._base_manifest()
        self.partial.rename(self.bundle / "model.calyx.mlir")
        artifact = self.bundle / "model.calyx.mlir"
        manifest.update(
            {
                "status": "ok",
                "artifact_accepted": True,
                "first_diagnostic": None,
                "exit_code": 0,
                "artifact": _binding(artifact),
                "partial_artifact": None,
                "log": _binding(self.log),
            }
        )
        self._write_manifest(manifest)

        result = self.module.verify_bundle(self.bundle, self.predecessor)

        self.assertEqual(result["status"], "complete")
        self.assertIsNone(result["first_diagnostic"])
        self.assertEqual(result["calyx_artifact"]["sha256"], _sha256(artifact.read_bytes()))

    def test_timebox_receipt_is_scalability_frontier_not_compiler_frontier(self) -> None:
        """Misclassifying a deadline kill as a compiler diagnostic hides scaling."""
        evidence = self._timebox_evidence()
        evidence_path = self._write_timebox_evidence(evidence)

        result = self.module.verify_timebox_evidence(evidence_path, self.predecessor)

        self.assertEqual(result["schema"], "tinystories-1m-exact-calyx-scalability-frontier-v1")
        self.assertEqual(result["status"], "calyx_scalability_frontier")
        self.assertEqual(result["frontier"], "calyx_scalability_frontier")
        self.assertIsNone(result["first_diagnostic"])
        self.assertIsNone(result["replay"])
        self.assertEqual(result["primary"]["evidence"]["self_sha256"], evidence["sha256"])
        self.assertEqual(result["primary"]["evidence"]["sha256"], _sha256(evidence_path.read_bytes()))
        self.assertEqual(result["primary"]["elapsed_wall_seconds"], 86400.0)
        self.assertEqual(result["primary"]["elapsed_cpu_seconds"], 90030.0)
        self.assertEqual(result["primary"]["max_rss_kb"], 820000)
        self.assertEqual(result["primary"]["termination"]["signal"], "SIGTERM")
        self.assertEqual(result["primary"]["no_output_observation"]["candidate"]["exists"], False)
        unsigned = {key: value for key, value in result.items() if key != "sha256"}
        self.assertEqual(result["sha256"], _sha256(_canonical_json(unsigned)))

    def test_rejects_timebox_with_mutated_command(self) -> None:
        """Letting a timebox bind a different pass would break provenance."""
        evidence = self._timebox_evidence()
        evidence["command"][2] = "--canonicalize"
        evidence_path = self._write_timebox_evidence(evidence)

        with self.assertRaisesRegex(ValueError, "timebox command mismatch"):
            self.module.verify_timebox_evidence(evidence_path, self.predecessor)

    def test_rejects_timebox_with_mutated_input_binding(self) -> None:
        """Trusting declared timebox input bytes would permit route substitution."""
        evidence = self._timebox_evidence()
        evidence["input"]["sha256"] = "0" * 64
        evidence_path = self._write_timebox_evidence(evidence)

        with self.assertRaisesRegex(ValueError, "timebox input SHA-256 mismatch"):
            self.module.verify_timebox_evidence(evidence_path, self.predecessor)

    def test_rejects_timebox_with_output_claim(self) -> None:
        """A scalability frontier must not claim a missing compiler artifact."""
        evidence = self._timebox_evidence()
        evidence["no_output_observation"]["candidate"]["exists"] = True
        evidence_path = self._write_timebox_evidence(evidence)

        with self.assertRaisesRegex(ValueError, "timebox candidate output was observed"):
            self.module.verify_timebox_evidence(evidence_path, self.predecessor)

    def test_rejects_timebox_with_invalid_termination_signal(self) -> None:
        """Dropping the real deadline termination signal would weaken the boundary."""
        evidence = self._timebox_evidence()
        evidence["termination"]["signal"] = "SIGUSR1"
        evidence_path = self._write_timebox_evidence(evidence)

        with self.assertRaisesRegex(ValueError, "timebox termination signal mismatch"):
            self.module.verify_timebox_evidence(evidence_path, self.predecessor)

    def test_accepts_timebox_with_externally_observed_termination(self) -> None:
        """Requiring agent-sent time would force a false timestamp for user SIGTERM."""
        evidence = self._timebox_evidence()
        evidence["termination"] = {
            "signal": "SIGTERM",
            "target_pids": [2530919],
            "source": "external_user",
            "observed_gone_at": "2026-09-02T18:24:13+02:00",
        }
        evidence_path = self._write_timebox_evidence(evidence)

        result = self.module.verify_timebox_evidence(evidence_path, self.predecessor)

        self.assertEqual(result["primary"]["termination"]["source"], "external_user")
        self.assertEqual(
            result["primary"]["termination"]["observed_gone_at"],
            "2026-09-02T18:24:13+02:00",
        )

    def test_rejects_mutated_input_hash(self) -> None:
        """Trusting the declared input hash would permit predecessor substitution."""
        self._mutate_manifest(lambda value: value["input"].update(sha256="0" * 64))
        with self.assertRaisesRegex(ValueError, "input SHA-256 mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_predecessor_receipt_hash(self) -> None:
        """Trusting a re-signed predecessor receipt would erase its authorization."""
        receipt = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        receipt["status"] = "blocked"
        self.receipt_path.write_bytes(_canonical_json(_signed(receipt)) + b"\n")
        with self.assertRaisesRegex(ValueError, "predecessor receipt SHA-256 mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_command(self) -> None:
        """Permitting a different pass option would make replay non-equivalent."""
        self._mutate_manifest(
            lambda value: value["command"].__setitem__(2, "--canonicalize")
        )
        with self.assertRaisesRegex(ValueError, "command mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_tool_hash(self) -> None:
        """Trusting a declared executable digest would allow tool substitution."""
        self._mutate_manifest(lambda value: value["circt_opt"].update(sha256="1" * 64))
        with self.assertRaisesRegex(ValueError, "tool SHA-256 mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_log(self) -> None:
        """Ignoring log bytes would permit the first diagnostic to be rewritten."""
        self.log.write_text(
            self.log.read_text(encoding="utf-8").replace("stable", "forged"),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "log SHA-256 mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_candidate_artifact(self) -> None:
        """Ignoring rejected output bytes would permit a different partial candidate."""
        self.partial.write_text("calyx.component @fake() {}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "partial artifact SHA-256 mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_diagnostic(self) -> None:
        """Trusting first_diagnostic without classifying the log would rewrite history."""
        self._mutate_manifest(
            lambda value: value.update(first_diagnostic="error: forged diagnostic")
        )
        with self.assertRaisesRegex(ValueError, "diagnostic differs from log"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_result_status(self) -> None:
        """Changing failure to success must not retain the failed artifact contract."""
        self._mutate_manifest(lambda value: value.update(status="ok"))
        with self.assertRaisesRegex(ValueError, "result status mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_rejects_mutated_receipt_self_hash(self) -> None:
        """A manifest that no longer authenticates itself is not admissible evidence."""
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["sha256"] = "2" * 64
        self.manifest_path.write_bytes(_canonical_json(manifest) + b"\n")
        with self.assertRaisesRegex(ValueError, "receipt self-hash mismatch"):
            self.module.verify_bundle(self.bundle, self.predecessor)

    def test_coherent_forged_manifest_fails_independent_replay(self) -> None:
        """Re-signing every bundle claim must not replace actual backend execution."""
        self.log.write_text("error: coherent forged frontier\n", encoding="utf-8")
        self.partial.write_text("calyx.component @main() { // forged\n}\n", encoding="utf-8")
        manifest = self._base_manifest()
        manifest["first_diagnostic"] = "error: coherent forged frontier"
        manifest["log"] = _binding(self.log)
        manifest["partial_artifact"] = _binding(self.partial)
        self._write_manifest(manifest)

        with self.assertRaisesRegex(ValueError, "replay result differs"):
            self.module.verify_bundle(self.bundle, self.predecessor)


if __name__ == "__main__":
    unittest.main()
