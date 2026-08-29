// Minimal execution probe for a Calyx LayerNorm model.
// Build this with Verilator's generated Vmain model and --public-flat-rw.
//
// The four memories are the @main arguments in order: input, gamma, beta,
// output.  This is deliberately a diagnostic fixture (not a TinyStories
// equivalence test): it uses the authenticated alternating +/-1 Q16.16
// vector and reports whether the generated model completes and preserves it.
#include "Vmain.h"
#include "Vmain___024root.h"
#include "verilated.h"

#include <cstdint>
#include <iostream>

static void tick(Vmain& model) {
  model.clk = 0;
  model.eval();
  model.clk = 1;
  model.eval();
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  Vmain model;
  auto* root = model.rootp;
  for (unsigned i = 0; i < 64; ++i) {
    const std::uint32_t input = (i & 1U) ? 0xffff0000U : 0x00010000U;
    root->main__DOT__mem_0__DOT__mem[i] = input;
    root->main__DOT__mem_1__DOT__mem[i] = 0x00010000U;
    root->main__DOT__mem_2__DOT__mem[i] = 0U;
    root->main__DOT__mem_3__DOT__mem[i] = 0U;
  }

  model.reset = 1;
  model.go = 0;
  for (unsigned i = 0; i < 4; ++i) tick(model);
  model.reset = 0;
  model.go = 1;
  tick(model);
  model.go = 0;

  unsigned cycles = 0;
  while (!model.done && cycles < 200000) {
    tick(model);
    ++cycles;
  }
  bool match = model.done;
  for (unsigned i = 0; i < 64; ++i) {
    const std::uint32_t expected = (i & 1U) ? 0xffff0000U : 0x00010000U;
    match = match && (root->main__DOT__mem_3__DOT__mem[i] == expected);
  }
  std::cout << "{\"status\":\"" << (match ? "ok" : "mismatch")
            << "\",\"done\":" << (model.done ? "true" : "false")
            << ",\"cycles\":" << cycles << "}\n";
  return match ? 0 : 1;
}
