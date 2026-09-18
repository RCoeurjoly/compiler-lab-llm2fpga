#include "Vcommand_integration_wrapper.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <memory>
#include <fstream>
#include <vector>
#include <string>
#include <stdexcept>

int main(int argc, char **argv) {
  try {
  auto context = std::make_unique<VerilatedContext>();
  context->commandArgs(argc, argv);
  auto dut = std::make_unique<Vcommand_integration_wrapper>(context.get());
  auto tick = [&]() {
    dut->clk = 0; dut->eval(); context->timeInc(1);
    dut->clk = 1; dut->eval(); context->timeInc(1);
    dut->clk = 0; dut->eval();
  };
  std::string model_path;
  bool load_only = false, corrupt_write = false;
  for (int i=1; i<argc; ++i) {
    std::string arg(argv[i]);
    if (arg.rfind("+MODEL_BIN=", 0) == 0) model_path = arg.substr(11);
    if (arg == "--load-only") load_only = true;
    if (arg == "--corrupt-write") corrupt_write = true;
  }
  std::ifstream file(model_path, std::ios::binary);
  std::vector<unsigned char> image((std::istreambuf_iterator<char>(file)), {});
  if (!file || image.size() != 4136720) {
    std::fprintf(stderr, "expected authenticated 4136720-byte MODEL_BIN\n"); return 2;
  }
  dut->host_cyc = 0; dut->host_stb = 0; dut->host_we = 0; dut->host_addr = 0;
  for (int i=0; i<4; ++i) dut->host_write_data[i] = 0;
  dut->reset = 1; dut->clear = 0; dut->start = 0;
  dut->prompt_valid = 0; dut->prompt_token = 0; dut->token_ready = 0;
  for (int i=0; i<4; ++i) tick();
  dut->reset = 0;
  auto transaction = [&](uint32_t line, bool write) {
    dut->host_addr = line; dut->host_we = write;
    dut->host_cyc = 1; dut->host_stb = 1;
    bool accepted = false;
    for (int wait=0; wait<100; ++wait) {
      dut->eval();
      bool take = !dut->host_stall;
      tick();
      if (take) { accepted = true; break; }
    }
    if (!accepted) throw std::runtime_error("host acceptance timeout");
    dut->host_stb = 0;
    dut->eval();
    for (int wait=0; !dut->host_ack && wait<100; ++wait) tick();
    if (!dut->host_ack || dut->host_err) throw std::runtime_error("host response failed");
    if (!write) {
      for (unsigned word=0; word<4; ++word) {
        uint32_t expected = 0;
        for (unsigned byte=0; byte<4; ++byte)
          expected |= uint32_t(image[line*16+word*4+byte]) << (byte*8);
        if (dut->host_read_data[word] != expected) {
          std::fprintf(stderr, "load readback mismatch line=%u word=%u\n", line, word);
          throw std::runtime_error("load readback mismatch");
        }
      }
    }
    tick(); // Response consumed while CYC is still held.
    dut->host_cyc = 0;
    tick(); // Let the production owner mux release this cycle.
  };
  for (uint32_t line=0; line<image.size()/16; ++line) {
    for (unsigned word=0; word<4; ++word) {
      uint32_t value = 0;
      for (unsigned byte=0; byte<4; ++byte)
        value |= uint32_t(image[line*16+word*4+byte]) << (byte*8);
      dut->host_write_data[word] = value;
    }
    if (corrupt_write && line == 17) dut->host_write_data[0] ^= 1;
    transaction(line, true);
  }
  for (uint32_t line=0; line<image.size()/16; ++line) transaction(line, false);
  std::printf("PASS: owner-mux full-image write/readback bytes=%zu\n", image.size());
  std::fflush(stdout);
  if (load_only) { dut->final(); return 0; }
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
      std::printf("PASS: loaded-image owner-mux/compiler first token=11 cycles=%llu requests=%llu responses=%llu\n",
        (unsigned long long)(cycle+1), (unsigned long long)dut->requests,
        (unsigned long long)dut->responses);
      dut->final(); return 0;
    }
  }
  std::fprintf(stderr,"cycle bound exceeded\n"); return 3;
  } catch (const std::exception &error) {
    std::fprintf(stderr, "FAIL: %s\n", error.what()); return 2;
  }
}
