#!/usr/bin/env python3
"""Execute the authenticated full-model Calyx/SV with source-only preloads.

Snapshots are read-only observations. The simulator receives no oracle values,
expected logits, hidden states, or generated-token inputs. Its only file inputs
are the immutable package tensors and the frozen initial prompt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import selectors
import signal
import shutil
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "tinystories-1m-model-sv-execution-v1"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lowerer = load_module(ROOT / "scripts/pipeline/lower_fixed_point_model_to_calyx.py", "model_sv_lowerer")


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_record(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def check_artifact(artifact):
    if artifact != lowerer.generate_model_kernel():
        raise ValueError("artifact_authority_mismatch")


def generate_harness(artifact):
    check_artifact(artifact)
    sources = []
    for name, record in artifact.provenance["source_memories"].items():
        sources.append(f'  preload(root->main__DOT__{name}__DOT__mem, directory + "/source-{name}.bin");')
    return r'''// Compiler-generated source-only model harness. No expected values.
#include "Vmain.h"
#include "Vmain___024root.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <set>

template<class Memory> static void preload(Memory& memory, const std::string& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("missing source: " + path);
  for (auto& word : memory.m_storage) {
    std::uint64_t value = 0;
    for (unsigned byte = 0; byte < 8; ++byte) {
      int ch = input.get();
      if (ch < 0) throw std::runtime_error("short source: " + path);
      value |= std::uint64_t(static_cast<unsigned char>(ch)) << (byte * 8);
    }
    word = value;
  }
  if (input.get() != -1) throw std::runtime_error("oversized source: " + path);
}

struct Observe {
  Vmain& model;
  Vmain___024root* root;
  std::string directory;
  unsigned run = 0;
  std::uint64_t cycles = 0;
  std::set<std::string> seen;
  bool active = false;

  template<class Memory> void snapshot(const Memory& memory, const std::string& boundary,
      unsigned step, unsigned offset, unsigned rows, unsigned columns, unsigned stride) {
    std::string key = std::to_string(run) + "-" + std::to_string(step) + "-" + boundary;
    if (!seen.insert(key).second) return;
    std::string file = key + ".bin";
    std::ofstream output(directory + "/" + file, std::ios::binary);
    for (unsigned row = 0; row < rows; ++row)
      for (unsigned col = 0; col < columns; ++col) {
        std::uint64_t value = memory[offset + row * stride + col];
        for (unsigned byte = 0; byte < 8; ++byte) output.put((value >> (byte * 8)) & 255);
      }
    output.close();
    if (!output) throw std::runtime_error("snapshot write failed");
    std::cout << "{\"event\":\"boundary\",\"run\":" << run << ",\"step\":" << step
      << ",\"boundary\":\"" << boundary << "\",\"file\":\"" << file
      << "\",\"cycles\":" << cycles << "}" << std::endl;
  }

  void tick() {
    model.clk = 0; model.eval();
    bool embedding = active && root->main__DOT__model_embedding_write_en && root->main__DOT__model_embedding_content_en
      && (root->main__DOT__model_embedding_addr0 % 512 == 511);
    unsigned embedding_step = root->main__DOT__model_embedding_addr0 / 512;
    bool block = active && root->main__DOT__model_block_outputs_write_en && root->main__DOT__model_block_outputs_content_en
      && (root->main__DOT__model_block_outputs_addr0 % 512 == 511);
    unsigned block_slot = root->main__DOT__model_block_outputs_addr0 / 512;
    bool ln = active && root->main__DOT__model_final_ln_write_en && root->main__DOT__model_final_ln_content_en
      && (root->main__DOT__model_final_ln_addr0 % 512 == 511);
    unsigned ln_step = root->main__DOT__model_final_ln_addr0 / 512;
    unsigned logit_step = root->main__DOT__model_logits_addr0 / 524288;
    unsigned logit_row = (root->main__DOT__model_logits_addr0 % 524288) / 65536;
    bool logits = active && root->main__DOT__model_logits_write_en && root->main__DOT__model_logits_content_en
      && (root->main__DOT__model_logits_addr0 % 65536 == 50256) && logit_row == 3 + logit_step;
    bool selected = active && root->main__DOT__selected_tokens_write_en && root->main__DOT__selected_tokens_content_en;
    unsigned selected_step = root->main__DOT__selected_tokens_addr0;
    model.clk = 1; model.eval(); ++cycles;
    if (embedding) {
      snapshot(root->main__DOT__model_token_embedding__DOT__mem, "embedding.token", embedding_step, embedding_step * 512, 4 + embedding_step, 64, 64);
      snapshot(root->main__DOT__model_position_embedding__DOT__mem, "embedding.position", embedding_step, embedding_step * 512, 4 + embedding_step, 64, 64);
      snapshot(root->main__DOT__model_embedding__DOT__mem, "embedding.sum", embedding_step, embedding_step * 512, 4 + embedding_step, 64, 64);
    }
    if (block) snapshot(root->main__DOT__model_block_outputs__DOT__mem, "block." + std::to_string(block_slot % 8), block_slot / 8, block_slot * 512, 4 + block_slot / 8, 64, 64);
    if (ln) snapshot(root->main__DOT__model_final_ln__DOT__mem, "final_ln", ln_step, ln_step * 512, 4 + ln_step, 64, 64);
    if (logits) {
      snapshot(root->main__DOT__model_logits__DOT__mem, "lm_head.full_context_logits", logit_step, logit_step * 524288, 4 + logit_step, 50257, 65536);
      snapshot(root->main__DOT__model_logits__DOT__mem, "lm_head.last_logits", logit_step, logit_step * 524288 + (3 + logit_step) * 65536, 1, 50257, 65536);
    }
    if (selected) {
      std::string key = std::to_string(run) + "-" + std::to_string(selected_step) + "-selected";
      if (seen.insert(key).second) {
        std::cout << "{\"event\":\"selected\",\"run\":" << run << ",\"step\":" << selected_step
          << ",\"token\":" << root->main__DOT__selected_tokens__DOT__mem[selected_step]
          << ",\"context\":[";
        for (unsigned i = 0; i < 5 + selected_step; ++i) {
          if (i) std::cout << ',';
          std::cout << root->main__DOT__context_tokens__DOT__mem[i];
        }
        std::cout << "],\"cycles\":" << cycles << "}" << std::endl;
      }
    }
  }
};

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  if (argc != 2) return 2;
  std::string directory = argv[1];
  Vmain model;
  auto* root = model.rootp;
PRELOADS
  Observe observer{model, root, directory};
  for (unsigned run = 0; run < 2; ++run) {
    observer.run = run; observer.cycles = 0; observer.active = false;
    model.reset = 1; model.start = 0; model.valid = 0;
    for (unsigned i = 0; i < 3; ++i) observer.tick();
    bool reset_isolated = !model.done;
    model.reset = 0; model.valid = 1;
    for (unsigned i = 0; i < 3; ++i) observer.tick();
    bool idle_isolated = !model.done && root->main__DOT__model_context_length_out == 0;
    model.start = 1; model.valid = 0;
    for (unsigned i = 0; i < 4; ++i) observer.tick();
    bool invalid_isolated = !model.done && root->main__DOT__model_context_length_out == 0;
    if (!(reset_isolated && idle_isolated && invalid_isolated)) return 3;
    std::cout << "{\"event\":\"isolation\",\"run\":" << run
      << ",\"reset\":true,\"idle\":true,\"invalid\":true}" << std::endl;
    observer.active = true; observer.cycles = 0; model.valid = 1;
    while (!model.done && observer.cycles < 2000000000ULL) observer.tick();
    if (!model.done) return 4;
    std::cout << "{\"event\":\"complete\",\"run\":" << run
      << ",\"cycles\":" << observer.cycles << "}" << std::endl;
    observer.active = false; model.start = 0; model.valid = 0;
    observer.tick(); observer.tick();
  }
  return 0;
}
'''.replace("PRELOADS", "\n".join(sources))


def expected_boundaries(oracle):
    result = {}
    for step in oracle["steps"]:
        index = step["step_index"]
        for name in ("token", "position", "sum"):
            result[index, "embedding." + name] = step["embedding"][name]
        for block in step["transformer_blocks"]:
            result[index, "block." + str(block["block_index"])] = block["output"]
        result[index, "final_ln"] = step["final_layer_norm"]["output"]
        for name in ("full_context_logits", "last_logits"):
            result[index, "lm_head." + name] = step["lm_head"][name]
    return result


def generate_visibility_config(artifact):
    """Expose only preloaded/observed arrays and actual testbench control reads.

    See https://verilator.org/guide/latest/exe_verilator.html#cmdoption-public-flat-rw
    Global public visibility disables useful signal optimization. This config
    affects only the simulator; the generated Futil and SV are not rewritten.
    """
    harness = generate_harness(artifact)
    wires = sorted({name for name in re.findall(r"root->main__DOT__(\w+)", harness) if "__DOT__" not in name} | {"model_layer_out"})
    return '\n'.join([
        '`verilator_config',
        'public_flat_rw -module "seq_mem_d1" -var "mem" @(posedge clk)',
        *[f'public_flat_rd -module "main" -var "{name}"' for name in wires],
        '',
    ])


def check_boundary(event, directory, oracle):
    import numpy as np
    expected = expected_boundaries(oracle).get((event["step"], event["boundary"]))
    if expected is None:
        raise ValueError("unexpected_boundary")
    path = directory / event["file"]
    if path.parent.resolve() != directory.resolve():
        raise ValueError("snapshot_path_escape")
    data = path.read_bytes()
    raw_hash = hashlib.sha256(data).hexdigest()
    if len(data) != expected["bytes"] or raw_hash != expected["little_endian_int64_sha256"]:
        raise ValueError(f"first_divergence: step={event['step']} boundary={event['boundary']} expected={expected['little_endian_int64_sha256']} observed={raw_hash} bytes={len(data)}")
    values = np.frombuffer(data, dtype="<i8").reshape(expected["shape"]).tolist()
    tensor_hash = canonical({"shape": expected["shape"], "dtype": expected["dtype"], "values": values})
    if tensor_hash != expected["sha256"]:
        raise ValueError("semantic_tensor_hash_mismatch")
    return {"step": event["step"], "boundary": event["boundary"], "shape": expected["shape"], "sha256": tensor_hash, "little_endian_int64_sha256": raw_hash, "cycles": event["cycles"]}


def compare_diagnostic_words(path, expected, shape):
    import numpy as np
    observed = np.frombuffer(path.read_bytes(), dtype="<i8")
    authority = np.asarray(expected, dtype="<i8").reshape(-1)
    if observed.shape != authority.shape:
        raise ValueError("diagnostic_memory_shape_mismatch: " + str(path))
    different = np.flatnonzero(observed != authority)
    first = int(different[0]) if len(different) else None
    return {
        "matches": not len(different), "mismatches": len(different),
        "expected_sha256": hashlib.sha256(authority.tobytes()).hexdigest(),
        "observed_sha256": hashlib.sha256(observed.tobytes()).hexdigest(),
        "first_mismatch": None if first is None else {
            "index": first, "coordinate": [int(x) for x in np.unravel_index(first, shape)],
            "expected": int(authority[first]), "observed": int(observed[first]),
        },
    }


def block0_diagnostic_contract():
    block, attention, mlp = lowerer._dependencies()
    fixtures = block._checked_fixtures(
        ROOT / "artifacts/reference/tinystories-1m-fixed-point-block-composition-slice.json",
        ROOT / "artifacts/reference/tinystories-1m-fixed-point-attention-crossing-slice.json",
        ROOT / "artifacts/reference/tinystories-1m-fixed-point-mlp-crossing-slice.json",
    )
    sources, computed, _ = block._memory_contracts(attention, mlp)
    records = {}
    for name in dict.fromkeys(["block_input_q16_16", *sources, *computed]):
        record = block._record_for(name, *fixtures)
        count = len(block._flatten(record["values"]))
        # The full-model score slots are [8 rows,16 heads,8 keys]. The
        # independent fixture is [4 rows,16 heads,4 keys]; gather the real keys
        # rather than mistaking zero-padded slots for another semantic tensor.
        sparse = name in {"attention_score_q8", "attention_delta_q8", "attention_exp_q1_20"}
        records[name] = {"record": record, "source": name in sources,
            "rows": 64 if sparse else 1, "columns": 4 if sparse else count,
            "stride": 8 if sparse else count, "signed8": name.endswith("codes_i8")}
    return records


def generate_diagnostic_harness(artifact):
    text = generate_harness(artifact)
    records = block0_diagnostic_contract()
    text = text.replace('#include <cstdint>', '#include <cstdint>\n#include <cstdlib>')
    text = text.replace("unsigned rows, unsigned columns, unsigned stride) {", "unsigned rows, unsigned columns, unsigned stride, bool signed8 = false) {")
    text = text.replace("std::uint64_t value = memory[offset + row * stride + col];", "std::uint64_t value = memory[offset + row * stride + col];\n        if (signed8) value = static_cast<std::int64_t>(static_cast<std::int8_t>(value));")

    def dump(name):
        r = records[name]
        return f'      snapshot(root->main__DOT__{name}__DOT__mem, "diagnostic.{name}", 0, 0, {r["rows"]}, {r["columns"]}, {r["stride"]}, {str(r["signed8"]).lower()});'

    before = [dump(name) for name, record in records.items() if record["source"]]
    after = [dump(name) for name, record in records.items() if not record["source"]]
    text = text.replace("    if (embedding) {", "    if (embedding && embedding_step == 0) {\n" + "\n".join(before) + "\n    }\n    if (embedding) {")
    anchor = '    if (ln) snapshot(root->main__DOT__model_final_ln__DOT__mem'
    diagnostic = """    if (block && block_slot == 0) {
AFTER
      std::cout << "{\\\"event\\\":\\\"diagnostic_complete\\\",\\\"layer\\\":"
        << unsigned(root->main__DOT__model_layer_out) << ",\\\"cycles\\\":" << cycles << "}" << std::endl;
      std::exit(0);
    }
""".replace("AFTER", "\n".join(after))
    text = text.replace(anchor, diagnostic + anchor)
    return text


def run_block0_diagnostic(reuse_directory, *, timeout=1800):
    """Observe the existing compiled RTL; rebuild only the C++ test harness."""
    reuse_directory = reuse_directory.resolve()
    artifact = lowerer.generate_model_kernel()
    if (reuse_directory / "model.futil").read_text() != artifact.futil:
        raise ValueError("diagnostic_futil_authority_mismatch")
    compiled = json.loads((ROOT / "artifacts/reference/tinystories-1m-model-orchestrator-compile-evidence.json").read_text())
    if file_record(reuse_directory / "model.sv")["sha256"] != compiled["verilog_sha256"]:
        raise ValueError("diagnostic_sv_authority_mismatch")
    directory = reuse_directory / "block0-diagnostic"
    directory.mkdir(exist_ok=True)
    execution = Execution(directory, timeout)
    for name in artifact.provenance["source_memories"]:
        shutil.copyfile(reuse_directory / ("source-" + name + ".bin"), directory / ("source-" + name + ".bin"))
    harness = directory / "diagnostic.cpp"
    harness.write_text(generate_diagnostic_harness(artifact))
    build = reuse_directory / "verilator"
    # Use the exact already compiled model archive, avoiding a second costly
    # Verilator/C++ compile while adding read-only testbench observations.
    runtime = Path("/nix/store/7mil9l34vfbvmh0cm6wvbdapwv77bz9v-verilator-5.022/share/verilator/include")
    executable = directory / "diagnostic_harness"
    archive = build / "Vmain__ALL.a"
    execution.stage("diagnostic_harness_build", ["g++", "-std=c++17", "-O2", "-I" + str(build), "-I" + str(runtime), "-I" + str(runtime / "vltstd"), str(harness), str(archive), str(build / "verilated.o"), str(build / "verilated_dpi.o"), str(build / "verilated_threads.o"), "-pthread", "-latomic", "-o", str(executable)])
    execution.stage("diagnostic_execution", [str(executable), str(directory)])
    records = block0_diagnostic_contract()
    comparisons = []
    for name, entry in records.items():
        result = compare_diagnostic_words(directory / ("0-0-diagnostic." + name + ".bin"), entry["record"]["values"], entry["record"]["shape"])
        comparisons.append({"memory": name, "source": entry["source"], **result})
    events = [json.loads(line) for line in (directory / "diagnostic_execution.log").read_text().splitlines() if line.startswith("{")]
    completion = [event for event in events if event["event"] == "diagnostic_complete"]
    if len(completion) != 1 or completion[0]["layer"] != 0:
        raise ValueError("diagnostic_block_selection_mismatch")
    report = {"status": "localized_mismatch" if any(not x["matches"] for x in comparisons) else "all_block0_memories_match", "futil_sha256": artifact.provenance["futil_sha256"], "sv_sha256": compiled["verilog_sha256"], "compiled_rtl_archive": file_record(archive), "harness": file_record(harness), "comparisons": comparisons, "completion": completion[0], "elapsed_seconds": time.monotonic() - execution.started, "stages": execution.stages, "rtl_modified": False, "full_model_verified": False}
    report["artifact_sha256"] = canonical(report)
    (directory / "diagnostic.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


class Execution:
    def __init__(self, directory, timeout):
        if not 0 < timeout <= 7200:
            raise ValueError("timeout must be in (0, 7200]")
        self.directory = directory
        self.started = time.monotonic()
        self.deadline = self.started + timeout
        self.timeout = timeout
        self.stages = []

    def remaining(self):
        return max(0.001, self.deadline - time.monotonic())

    def stop(self, process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)

    def stage(self, name, command, callback=None):
        begin = time.monotonic()
        output_path = self.directory / (name + ".log")
        with output_path.open("w") as output:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True, bufsize=1)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            try:
                while selector.get_map():
                    if time.monotonic() >= self.deadline:
                        raise ValueError("deadline_exceeded: " + name)
                    for key, _ in selector.select(min(self.remaining(), 1)):
                        line = key.fileobj.readline()
                        if not line:
                            selector.unregister(key.fileobj)
                            continue
                        output.write(line)
                        output.flush()
                        if callback is not None and line.startswith("{"):
                            callback(json.loads(line))
                code = process.wait(timeout=self.remaining())
                if code:
                    raise ValueError(f"stage_failed: {name} exit={code}: {output_path.read_text()[-6000:]}")
            except BaseException:
                self.stop(process)
                raise
            finally:
                selector.close()
                process.stdout.close()
        self.stages.append({"stage": name, "command": command, "elapsed_seconds": time.monotonic() - begin, "log": file_record(output_path)})
        return output_path.read_text()


def validate_execution_receipt(receipt, *, verify_artifacts=True):
    artifact = lowerer.generate_model_kernel()
    oracle = json.loads(lowerer.ORACLE.read_text())
    unsigned = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    if receipt.get("receipt_sha256") != canonical(unsigned):
        raise ValueError("receipt_hash_mismatch")
    if receipt.get("schema") != SCHEMA or receipt.get("status") != "passed":
        raise ValueError("execution_not_passed")
    if receipt["futil_sha256"] != artifact.provenance["futil_sha256"] or receipt["oracle_sha256"] != oracle["artifact_sha256"]:
        raise ValueError("receipt_authority_mismatch")
    if receipt["runner_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("runner_source_mismatch")
    execution = receipt["execution"]
    if execution["host_intermediate_preload"] or execution["host_second_token_preload"] or execution["host_preload_memories"] != sorted(artifact.provenance["source_memories"]):
        raise ValueError("host_preload_contract")
    if execution["selected_tokens"] != [s["selected_token"]["value"] for s in oracle["steps"]] or execution["complete_decode_runs"] != 2:
        raise ValueError("decode_contract")
    expected = expected_boundaries(oracle)
    observed = {(x["step"], x["boundary"]): x for x in receipt["boundaries"]}
    if set(observed) != set(expected) or len(observed) != len(receipt["boundaries"]):
        raise ValueError("boundary_coverage")
    for key, record in observed.items():
        for field in ("sha256", "little_endian_int64_sha256", "shape"):
            if record[field] != expected[key][field]:
                raise ValueError("boundary_authority_mismatch")
    if not receipt["reset"]["restart_reproduced_all_boundaries"] or receipt["execution"]["cycles"][0] != receipt["execution"]["cycles"][1]:
        raise ValueError("restart_determinism")
    if not 0 < receipt["timebox"]["elapsed_seconds"] <= receipt["timebox"]["timeout_seconds"] <= 7200:
        raise ValueError("timebox_contract")
    if verify_artifacts:
        for record in receipt["generated_artifacts"].values():
            if file_record(Path(record["path"])) != record:
                raise ValueError("generated_artifact_mismatch")
        if receipt["generated_artifacts"]["futil"]["sha256"] != artifact.provenance["futil_sha256"]:
            raise ValueError("same_futil_mismatch")
    return receipt


def run_model_sv(directory: Path, *, timeout=7200):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    execution = Execution(directory, timeout)
    artifact = lowerer.generate_model_kernel()
    oracle = json.loads(lowerer.ORACLE.read_text())
    stage = "materialize_sources"
    try:
        capture = lowerer._load(ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py", "model_execution_oracle")
        bundle = capture.exact_adapter.load_successor_exact_model(capture.DEFAULT_CONTRACT, capture.DEFAULT_PACKAGE, capture.DEFAULT_MODEL, capture.DEFAULT_GENERATION)
        sources = lowerer.materialize_model_sources(artifact, bundle)
        source_records = {}
        for name, tensor in sources.items():
            path = directory / ("source-" + name + ".bin")
            path.write_bytes(tensor.numpy().astype("<i8").tobytes())
            source_records[name] = file_record(path)
        del sources, bundle
        futil = directory / "model.futil"
        sv = directory / "model.sv"
        harness = directory / "harness.cpp"
        futil.write_text(artifact.futil)
        harness.write_text(generate_harness(artifact))
        stage = "calyx_resolution"
        install = Path(execution.stage(stage, ["nix", "build", "--no-link", "--print-out-paths", ".#calyx"]).strip().splitlines()[-1])
        common = [str(install / "bin/calyx"), str(futil), "-l", str(install / "share/calyx"), "-d", "cell-share"]
        stage = "calyx_simulation"
        execution.stage(stage, [*common, "-b", "verilog", "-o", str(sv)])
        stage = "verilator_build"
        build = directory / "verilator"
        executable = build / "model_harness"
        visibility = directory / "visibility.vlt"
        visibility.write_text(generate_visibility_config(artifact))
        sv_before_visibility = file_record(sv)
        execution.stage(stage, ["verilator", "--cc", "--exe", "--build", "-j", "4", "--top-module", "main", "--Mdir", str(build), "-CFLAGS", "-std=c++17", "-MAKEFLAGS", "OPT_SLOW=-O0", "-o", executable.name, str(visibility), str(sv), str(harness)])
        if file_record(sv) != sv_before_visibility or futil.read_text() != artifact.futil:
            raise ValueError("simulator_visibility_changed_generated_rtl")
        observations = {0: [], 1: []}
        tokens = {0: [], 1: []}
        isolation = {}
        cycles = {}
        next_boundary = {0: 0, 1: 0}
        boundary_order = list(expected_boundaries(oracle))

        def accept(event):
            run = event["run"]
            if run not in observations:
                raise ValueError("unexpected_decode_run")
            if event["event"] == "boundary":
                key = event["step"], event["boundary"]
                if next_boundary[run] >= len(boundary_order) or key != boundary_order[next_boundary[run]]:
                    raise ValueError("out_of_order_boundary: " + str(key))
                record = check_boundary(event, directory, oracle)
                observations[run].append(record)
                next_boundary[run] += 1
                print(json.dumps({"status": "boundary_matched", "run": run, **record}), flush=True)
            elif event["event"] == "selected":
                step = event["step"]
                expected = oracle["steps"][step]
                if step != len(tokens[run]) or event["token"] != expected["selected_token"]["value"] or event["context"] != expected["context_tokens"] + [event["token"]]:
                    raise ValueError("hardware_feedback_mismatch: " + str(event))
                tokens[run].append(event["token"])
            elif event["event"] == "isolation":
                if run in isolation or any(event[x] is not True for x in ("reset", "idle", "invalid")):
                    raise ValueError("isolation_mismatch")
                isolation[run] = event
            elif event["event"] == "complete":
                if run in cycles or next_boundary[run] != len(boundary_order) or len(tokens[run]) != 2:
                    raise ValueError("incomplete_decode")
                cycles[run] = event["cycles"]
            else:
                raise ValueError("unexpected_simulator_event")

        stage = "generated_sv_execution"
        execution.stage(stage, [str(executable), str(directory)], accept)
        if set(cycles) != {0, 1} or set(isolation) != {0, 1} or observations[0] != observations[1] or tokens[0] != tokens[1] or cycles[0] != cycles[1]:
            raise ValueError("reset_restart_not_deterministic")
        receipt = {
            "schema": SCHEMA, "status": "passed", "oracle_sha256": oracle["artifact_sha256"],
            "futil_sha256": artifact.provenance["futil_sha256"], "provenance_sha256": artifact.provenance["artifact_sha256"],
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "execution": {"complete_decode_runs": 2, "generated_main_count": 1, "simulator_processes": 1,
                "selected_tokens": tokens[0], "cycles": [cycles[0], cycles[1]],
                "host_preload_memories": sorted(source_records), "host_intermediate_preload": False, "host_second_token_preload": False,
                "feedback": "selected_tokens -> context_tokens[4] -> second_step_embedding"},
            "boundaries": observations[0], "reset": {"initial": isolation[0], "restart": isolation[1], "restart_reproduced_all_boundaries": True},
            "source_artifacts": source_records,
            "generated_artifacts": {"futil": file_record(futil), "sv": file_record(sv), "harness": file_record(harness), "visibility": file_record(visibility), "executable": file_record(executable), "execution_log": file_record(directory / "generated_sv_execution.log")},
            "timebox": {"timeout_seconds": timeout, "elapsed_seconds": time.monotonic() - execution.started},
            "stages": execution.stages,
            "claims": {"exact_two_token_generated_sv": True, "board_execution": False, "synthesis_verified": False},
        }
        receipt["receipt_sha256"] = canonical(receipt)
        validate_execution_receipt(receipt)
        (directory / "execution-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        return receipt
    except Exception as error:
        failure = {"status": "failed", "stage": stage, "diagnostic": str(error), "futil_sha256": artifact.provenance["futil_sha256"], "oracle_sha256": oracle["artifact_sha256"], "elapsed_seconds": time.monotonic() - execution.started, "timeout_seconds": timeout, "execution_verified": False, "stages": execution.stages}
        failure["artifact_sha256"] = canonical(failure)
        (directory / "failure.json").write_text(json.dumps(failure, sort_keys=True, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("/tmp/llm2fpga-tinystories-model-sv-v1"))
    parser.add_argument("--receipt", type=Path, default=ROOT / "artifacts/reference/tinystories-1m-model-sv-execution-receipt.json")
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--diagnose-block0", action="store_true", help="reuse exact compiled model and observe internal block-0 memories only")
    args = parser.parse_args()
    if args.diagnose_block0:
        report = run_block0_diagnostic(args.directory, timeout=min(args.timeout, 1800))
        print(json.dumps({"status": report["status"], "first_mismatch": next((x for x in report["comparisons"] if not x["matches"]), None)}))
        return
    receipt = run_model_sv(args.directory, timeout=args.timeout)
    args.receipt.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "passed", "receipt_sha256": receipt["receipt_sha256"], "tokens": receipt["execution"]["selected_tokens"], "cycles": receipt["execution"]["cycles"]}))


if __name__ == "__main__":
    main()
