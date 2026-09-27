"""Execute the generated checker against a controlled model-port fixture.

This tests checker acceptance/rejection, not TinyStories computation.
"""
import subprocess
import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.pipeline import run_bram_production_sv as production_runner

harness = production_runner.harness

MODEL = r'''
#pragma once
#include <cstdint>
struct Vmain___024root {
  bool main__DOT__selected_tokens_write_en = false;
  bool main__DOT__selected_tokens_content_en = false;
  unsigned main__DOT__selected_tokens_addr0 = 0;
  uint16_t main__DOT__selected_tokens__DOT__mem[2] = {0,0};
  bool main__DOT__context_tokens_write_en = false;
  bool main__DOT__context_tokens_content_en = false;
  unsigned main__DOT__context_tokens_addr0 = 0;
  uint16_t main__DOT__context_tokens_write_data = 0;
  uint16_t main__DOT__context_tokens__DOT__mem[20] = {};
};
struct Vmain {
  Vmain___024root root;
  Vmain___024root* rootp = &root;
  unsigned clk=0, reset=0, start=0, valid=0, done=0, cycles=0;
  unsigned prompt_0=0, prompt_1=0, prompt_2=0, prompt_3=0;
  unsigned token_index=0, token_id=0;
  void eval() {
    if (clk) {
      if (reset) { cycles=0; done=0; root={}; }
      else {
        if (valid && !start) {
          root.main__DOT__context_tokens__DOT__mem[0] = prompt_0;
          root.main__DOT__context_tokens__DOT__mem[1] = prompt_1;
          root.main__DOT__context_tokens__DOT__mem[2] = prompt_2;
          root.main__DOT__context_tokens__DOT__mem[3] = prompt_3;
        }
        if (root.main__DOT__selected_tokens_write_en)
          root.main__DOT__selected_tokens__DOT__mem[root.main__DOT__selected_tokens_addr0] =
            root.main__DOT__selected_tokens_addr0 ? 612 : 11;
        if (root.main__DOT__context_tokens_write_en)
          root.main__DOT__context_tokens__DOT__mem[root.main__DOT__context_tokens_addr0] =
            root.main__DOT__context_tokens_write_data;
        ++cycles;
      }
    }
    done = cycles >= 30;
    root.main__DOT__selected_tokens_write_en =
      !MISSING && (cycles == 12 || (EXTRA && cycles == 20));
    root.main__DOT__selected_tokens_content_en = root.main__DOT__selected_tokens_write_en;
    root.main__DOT__selected_tokens_addr0 = cycles == 20;
    root.main__DOT__context_tokens_write_en = root.main__DOT__selected_tokens_write_en;
    root.main__DOT__context_tokens_content_en = root.main__DOT__selected_tokens_content_en;
    root.main__DOT__context_tokens_addr0 = 4 + root.main__DOT__selected_tokens_addr0;
    root.main__DOT__context_tokens_write_data =
      BAD_FEEDBACK && root.main__DOT__selected_tokens_addr0 ? 99 :
      (root.main__DOT__selected_tokens_addr0 ? 612 : 11);
    token_id = BAD_PORT ? 99 : root.main__DOT__selected_tokens__DOT__mem[token_index];
  }
};
'''


class HarnessTest(unittest.TestCase):
    def execute(self, *, bad_port=0, missing=0, extra=0, bad_feedback=0, steps=1):
        artifact = SimpleNamespace(provenance={"source_memories": {}, "schedule": {"generation_steps": steps}})
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "Vmain.h").write_text(MODEL)
            (directory / "Vmain___024root.h").write_text('#include "Vmain.h"\n')
            (directory / "verilated.h").write_text('struct Verilated { static void commandArgs(int, char**) {} };\n')
            (directory / "harness.cpp").write_text(harness(artifact))
            subprocess.run(["g++", "-std=c++17", f"-DBAD_PORT={bad_port}",
                            f"-DMISSING={missing}", f"-DEXTRA={extra}",
                            f"-DBAD_FEEDBACK={bad_feedback}",
                            "harness.cpp", "-o", "check"], cwd=directory, check=True,
                           capture_output=True, timeout=30)
            return subprocess.run([str(directory / "check"), str(directory)],
                                  capture_output=True, text=True, timeout=10)

    def test_accepts_one_committed_token_and_public_port(self):
        result = self.execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_wrong_public_token_port(self):
        self.assertNotEqual(self.execute(bad_port=1).returncode, 0)

    def test_rejects_missing_token_commit(self):
        self.assertNotEqual(self.execute(missing=1).returncode, 0)

    def test_rejects_second_step_in_one_step_execution(self):
        self.assertNotEqual(self.execute(extra=1).returncode, 0)

    def test_accepts_two_tokens_with_hardware_context_feedback(self):
        result = self.execute(extra=1, steps=2)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_reports_first_corrupt_feedback_even_when_output_tokens_match(self):
        result = self.execute(extra=1, steps=2, bad_feedback=1)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"event":"context_mismatch","run":0,"step":1', result.stdout)


class ProductionExecutionReceiptTest(unittest.TestCase):
    def test_preserves_two_exact_runs_and_binds_log_to_receipt(self):
        self.assertTrue(hasattr(production_runner, "run_and_record_harness"))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            executable = directory / "fake-harness"
            executable.write_text("#!/bin/sh\n" + "\n".join((
                "echo '{\"event\":\"selected\",\"run\":0,\"step\":0,\"token\":11,\"cycles\":10}'",
                "echo '{\"event\":\"selected\",\"run\":0,\"step\":1,\"token\":612,\"cycles\":20}'",
                "echo '{\"event\":\"token_port\",\"run\":0,\"step\":0,\"token\":11}'",
                "echo '{\"event\":\"token_port\",\"run\":0,\"step\":1,\"token\":612}'",
                "echo '{\"event\":\"complete\",\"run\":0,\"cycles\":20}'",
                "echo '{\"event\":\"selected\",\"run\":1,\"step\":0,\"token\":11,\"cycles\":10}'",
                "echo '{\"event\":\"selected\",\"run\":1,\"step\":1,\"token\":612,\"cycles\":20}'",
                "echo '{\"event\":\"token_port\",\"run\":1,\"step\":0,\"token\":11}'",
                "echo '{\"event\":\"token_port\",\"run\":1,\"step\":1,\"token\":612}'",
                "echo '{\"event\":\"complete\",\"run\":1,\"cycles\":20}'",
            )) + "\n")
            executable.chmod(0o755)
            receipt = production_runner.run_and_record_harness(executable, directory, generation_steps=2)
            log = (directory / "production-execution.jsonl").read_bytes()
            self.assertEqual(receipt["status"], "passed")
            self.assertEqual(receipt["selected_tokens"], [[11, 612], [11, 612]])
            self.assertEqual(receipt["cycles"], [20, 20])
            self.assertEqual(receipt["log_sha256"], hashlib.sha256(log).hexdigest())
            self.assertEqual(json.loads((directory / "production-execution.json").read_text()), receipt)
            self.assertGreaterEqual(receipt["elapsed_seconds"], 0)
            self.assertLess(receipt["elapsed_seconds"], 10)

    def test_rejects_success_exit_with_missing_token_event_and_preserves_log(self):
        self.assertTrue(hasattr(production_runner, "run_and_record_harness"))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            executable = directory / "fake-harness"
            executable.write_text("#!/bin/sh\necho '{\"event\":\"complete\",\"run\":0,\"cycles\":20}'\n")
            executable.chmod(0o755)
            with self.assertRaises(ValueError):
                production_runner.run_and_record_harness(executable, directory, generation_steps=2)
            self.assertIn('"event":"complete"', (directory / "production-execution.jsonl").read_text())
            self.assertFalse((directory / "production-execution.json").exists())
