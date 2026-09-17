#include "Vcommand_integration_wrapper.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <memory>

int main(int argc, char **argv) {
  auto context = std::make_unique<VerilatedContext>();
  context->commandArgs(argc, argv);
  auto dut = std::make_unique<Vcommand_integration_wrapper>(context.get());
  auto tick = [&]() {
    dut->clk = 0; dut->eval(); context->timeInc(1);
    dut->clk = 1; dut->eval(); context->timeInc(1);
    dut->clk = 0; dut->eval();
  };
  dut->reset = 1; dut->clear = 0; dut->start = 0;
  dut->prompt_valid = 0; dut->prompt_token = 0; dut->token_ready = 0;
  for (int i=0; i<4; ++i) tick();
  dut->reset = 0;
  for (uint16_t token : {7454, 2402, 257, 640}) {
    dut->eval();
    if (!dut->prompt_ready) { std::fprintf(stderr,"prompt not ready\n"); return 2; }
    dut->prompt_token = token; dut->prompt_valid = 1; tick();
    dut->prompt_valid = 0; tick();
  }
  if (dut->prompt_ready) { std::fprintf(stderr,"fifth prompt accepted\n"); return 2; }
  dut->start = 1; tick(); dut->start = 0;
  for (uint64_t cycle=0; cycle<300000000; ++cycle) {
    tick();
    if (dut->error || dut->request_count != dut->requests) {
      std::fprintf(stderr,"adapter error=%u count=%u requests=%llu\n",
        unsigned(dut->error_code), dut->request_count, (unsigned long long)dut->requests);
      return 2;
    }
    if (cycle % 1000000 == 0) {
      std::printf("cycle=%llu requests=%llu responses=%llu valid=%u token=%u\n",
        (unsigned long long)cycle, (unsigned long long)dut->requests,
        (unsigned long long)dut->responses, unsigned(dut->token_valid), unsigned(dut->token_id));
      std::fflush(stdout);
    }
    if (dut->token_valid) {
      if (dut->token_id != 11 || dut->requests != dut->responses || !dut->requests) {
        std::fprintf(stderr,"wrong token or unfinished memory transaction\n"); return 2;
      }
      for (int i=0; i<5; ++i) {
        tick();
        if (!dut->token_valid || dut->token_id != 11 || !dut->busy) {
          std::fprintf(stderr,"token lost under backpressure\n"); return 2;
        }
      }
      dut->token_ready = 1; tick();
      if (dut->token_valid || dut->busy) {
        std::fprintf(stderr,"token handshake did not retire\n"); return 2;
      }
      std::printf("PASS: actual command adapter/compiler first token=11 cycles=%llu requests=%llu responses=%llu\n",
        (unsigned long long)(cycle+1), (unsigned long long)dut->requests,
        (unsigned long long)dut->responses);
      dut->final(); return 0;
    }
  }
  std::fprintf(stderr,"cycle bound exceeded\n"); return 3;
}
