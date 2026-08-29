// Execute the small external-memory Calyx fixture.
//
// This is a backend plumbing probe, not a TinyStories or LayerNorm
// equivalence test.  It initializes the four generated seq_mem_d1 instances
// through Verilator's public hierarchy, starts the component, and checks the
// affine result.  The two-phase read/write schedule is intentional: seq_mem
// has one-cycle read latency, so computing and writing in the read group
// would consume stale data.
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
  for (unsigned i = 0; i < 4; ++i) {
    root->main__DOT__in_mem__DOT__mem[i] = 10 + i;
    root->main__DOT__gamma__DOT__mem[i] = 100 + i;
    root->main__DOT__beta__DOT__mem[i] = 1000 + i;
    root->main__DOT__out_mem__DOT__mem[i] = 0;
  }

  model.reset = 1;
  model.go = 0;
  for (unsigned i = 0; i < 3; ++i) tick(model);
  model.reset = 0;
  model.go = 1;

  unsigned cycles = 0;
  while (!model.done && cycles < 100) {
    tick(model);
    ++cycles;
  }
  bool match = model.done;
  for (unsigned i = 0; i < 4; ++i) {
    const std::uint32_t expected = 1110 + 3 * i;
    match = match && (root->main__DOT__out_mem__DOT__mem[i] == expected);
  }
  std::cout << "{\"status\":\"" << (match ? "ok" : "mismatch")
            << "\",\"done\":" << (model.done ? "true" : "false")
            << ",\"cycles\":" << cycles << "}\n";
  return match ? 0 : 1;
}
