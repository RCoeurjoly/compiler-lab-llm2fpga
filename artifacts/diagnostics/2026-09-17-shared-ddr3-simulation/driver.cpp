#include "Vcompiler_ddr3_cpp_wrapper.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>

static void tick(Vcompiler_ddr3_cpp_wrapper& top) {
    top.clk = 0; top.eval();
    top.clk = 1; top.eval();
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    const uint64_t limit = argc > 1 ? std::strtoull(argv[1], nullptr, 10) : 300000000ULL;
    Vcompiler_ddr3_cpp_wrapper top;
    top.reset = 1; top.start = 0; top.valid = 0;
    top.prompt_0 = 7454; top.prompt_1 = 2402; top.prompt_2 = 257; top.prompt_3 = 640;
    for (int i = 0; i < 3; ++i) tick(top);
    top.reset = 0; top.start = 1; top.valid = 1;
    for (uint64_t cycle = 1; cycle <= limit; ++cycle) {
        tick(top);
        if (cycle % 1000000ULL == 0 || top.done) {
            std::printf("cycles=%llu done=%u token=%u requests=%llu responses=%llu\n",
                (unsigned long long)cycle, top.done, top.token_id,
                (unsigned long long)top.wb_req_count, (unsigned long long)top.wb_rsp_count);
            std::fflush(stdout);
        }
        if (top.wb_rsp_count > top.wb_req_count || top.wb_req_count - top.wb_rsp_count > 1) {
            std::fprintf(stderr, "FAIL: single-outstanding request/response accounting\n");
            return 3;
        }
        if (top.done) {
            const auto token_at_done = top.token_id;
            for (int i = 1; i <= 2; ++i) {
                tick(top);
                std::printf("post_done_cycle=%d token=%u\n", i, top.token_id);
            }
            std::printf("%s: token at completion=%u expected=11\n",
                token_at_done == 11 ? "PASS" : "FAIL", token_at_done);
            return token_at_done == 11 ? 0 : 2;
        }
    }
    std::fprintf(stderr, "TIMEOUT: no completion within %llu cycles\n", (unsigned long long)limit);
    return 1;
}
