#!/usr/bin/env python3
"""Run the audit-free TinyStories-1M generated RTL from source tensors only."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


production = load(ROOT / "scripts/pipeline/lower_fixed_point_model_bram_production.py", "bram_production")
base = production.base


def harness(artifact):
    preloads = "\n".join(
        f'  preload(root->main__DOT__{name}__DOT__mem, directory + "/source-{name}.bin");'
        for name in artifact.provenance["source_memories"]
    )
    return r'''#include "Vmain.h"
#include "Vmain___024root.h"
#include "verilated.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

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

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  if (argc != 2) return 2;
  const std::string directory = argv[1];
  Vmain model;
  auto* root = model.rootp;
  PRELOADS
  std::uint64_t completed[2] = {0, 0};
  std::uint16_t tokens[2][2] = {{0, 0}, {0, 0}};
  for (unsigned run = 0; run < 2; ++run) {
    model.reset = 1; model.start = 0; model.valid = 0;
    for (unsigned i = 0; i < 3; ++i) { model.clk = 0; model.eval(); model.clk = 1; model.eval(); }
    model.reset = 0; model.valid = 1;
    for (unsigned i = 0; i < 3; ++i) { model.clk = 0; model.eval(); model.clk = 1; model.eval(); }
    model.start = 1; model.valid = 0;
    for (unsigned i = 0; i < 4; ++i) { model.clk = 0; model.eval(); model.clk = 1; model.eval(); }
    model.valid = 1;
    while (!model.done && completed[run] < 2000000000ULL) {
      model.clk = 0; model.eval();
      const bool selected = root->main__DOT__selected_tokens_write_en &&
        root->main__DOT__selected_tokens_content_en;
      const unsigned step = root->main__DOT__selected_tokens_addr0;
      model.clk = 1; model.eval(); ++completed[run];
      if ((completed[run] % 100000ULL) == 0)
        std::cout << "{\"event\":\"progress\",\"run\":" << run
          << ",\"cycles\":" << completed[run] << "}" << std::endl;
      if (selected && step < 2) {
        tokens[run][step] = root->main__DOT__selected_tokens__DOT__mem[step];
        std::cout << "{\"event\":\"selected\",\"run\":" << run
          << ",\"step\":" << step << ",\"token\":" << tokens[run][step]
          << ",\"cycles\":" << completed[run] << "}" << std::endl;
      }
    }
    if (!model.done || completed[run] >= 2000000000ULL) return 3;
    std::cout << "{\"event\":\"complete\",\"run\":" << run
      << ",\"cycles\":" << completed[run] << "}" << std::endl;
  }
  if (tokens[0][0] != 11 || tokens[0][1] != 612 || tokens[1][0] != 11 || tokens[1][1] != 612)
    return 4;
  if (completed[0] != completed[1] || tokens[0][0] != tokens[1][0] || tokens[0][1] != tokens[1][1]) return 5;
  return 0;
}
'''.replace("PRELOADS", preloads)


def main():
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/llm2fpga-tinystories-bram-production-sv").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    artifact = production.generate_production_kernel()
    capture = base._load(ROOT / "TinyStories/capture_fixed_point_model_token_step_oracle.py", "production_execution_oracle")
    bundle = capture.exact_adapter.load_successor_exact_model(capture.DEFAULT_CONTRACT, capture.DEFAULT_PACKAGE, capture.DEFAULT_MODEL, capture.DEFAULT_GENERATION)
    for name, tensor in base.materialize_model_sources(artifact, bundle).items():
        (directory / ("source-" + name + ".bin")).write_bytes(tensor.numpy().astype("<i8").tobytes())
    (directory / "model.futil").write_text(artifact.futil)
    install = Path(subprocess.check_output(["nix", "build", "--no-link", "--print-out-paths", ".#calyx"], cwd=ROOT, text=True).strip())
    subprocess.run([str(install / "bin/calyx"), str(directory / "model.futil"), "-l", str(install / "share/calyx"), "-d", "cell-share", "-b", "verilog", "-o", str(directory / "model.sv")], cwd=ROOT, check=True)
    source_names = list(artifact.provenance["source_memories"])
    visibility = ['`verilator_config', 'public_flat_rw -module "seq_mem_d1" -var "mem" @(posedge clk)']
    visibility += [f'public_flat_rd -module "main" -var "{name}"' for name in ("selected_tokens_write_en", "selected_tokens_content_en", "selected_tokens_addr0")]
    (directory / "visibility.vlt").write_text("\n".join(visibility) + "\n")
    (directory / "harness.cpp").write_text(harness(artifact))
    build = directory / "verilator"
    subprocess.run(["verilator", "--cc", "--exe", "--build", "-j", "8", "--top-module", "main", "--Mdir", str(build), "-CFLAGS", "-std=c++17 -O3", "-o", "production_harness", str(directory / "visibility.vlt"), str(directory / "model.sv"), str(directory / "harness.cpp")], cwd=ROOT, check=True)
    result = subprocess.run([str(build / "production_harness"), str(directory)], cwd=ROOT, text=True, capture_output=True, check=True)
    print(result.stdout, end="")
    receipt = {"status": "passed", "futil_sha256": artifact.provenance["futil_sha256"], "sv_sha256": hashlib.sha256((directory / "model.sv").read_bytes()).hexdigest(), "output": result.stdout.splitlines(), "elapsed_seconds": time.time()}
    (directory / "production-execution.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
