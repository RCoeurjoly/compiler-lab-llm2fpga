#include "jtag.hpp"
#include <string>
#define private public
#include "bpiFlash.hpp"
#undef private
#include <algorithm>
#include <iostream>
#include <stdexcept>
static void require(bool pass, const char *message) {
    if (!pass) throw std::runtime_error(message);
}
// Literal addresses independently derived from datasheet Table 3, x16 words.
static const uint32_t bases[] = {
    0x0000000, 0x0400000, 0x0800000, 0x0c00000,
    0x1000000, 0x1400000, 0x1800000, 0x1c00000
};
static bool contains(const Jtag &j, uint32_t address, uint16_t command) {
    return std::find(j.commands.begin(), j.commands.end(),
                     std::make_pair(address, command)) != j.commands.end();
}
int main(int argc, char **argv) {
    require(argc == 2, "select partition-address regression");
    try {
        std::string mode(argv[1]);
        if (mode == "read_cross" || mode == "read_start") {
            for (unsigned p = mode == "read_cross" ? 1 : 0; p < 8; ++p) {
                Jtag j;
                BPIFlash flash(&j, 0);
                uint8_t expected[4] = {};
                uint32_t address = bases[p]*2 - (mode == "read_cross" ? 2 : 0);
                require(flash.verify(address, expected, 4), "partition array read failed");
                require(contains(j, bases[p], 0xff), "READ_ARRAY misses requested partition");
                if (mode == "read_cross")
                    require(contains(j, bases[p]-1, 0xff), "READ_ARRAY misses starting partition");
            }
        } else if (mode == "program_cross") {
            for (unsigned p = 1; p < 8; ++p) {
                Jtag j;
                BPIFlash flash(&j, 0);
                flash._has_burst = true;
                uint8_t data[64];
                for (unsigned i = 0; i < 64; ++i) data[i] = (i*13 + 7) & 255;
                require(flash.write(bases[p]*2 - 32, data, 64), "cross-partition program failed");
                require(flash.verify(bases[p]*2 - 32, data, 64), "cross-partition data mismatch");
                require(!j.status_mode[p-1] && !j.status_mode[p], "both written partitions must return to array mode");
            }
        } else if (mode == "erase" || mode == "errors" || mode == "program" || mode == "program_errors") {
            for (unsigned p = 0; p < 8; ++p) {
                Jtag j;
                BPIFlash flash(&j, 0);
                uint32_t address = bases[p];
                if (mode == "erase") {
                    j.statuses = {0x0001, 0x0000, 0x0080};
                    require(flash.erase_block(address*2), "erase did not wait for global ready");
                    require(j.statuses.empty(), "SR7 ignored: returned before ready");
                    require(j.status_reads == std::vector<uint32_t>({address,address,address}),
                            "READ_STATUS polls wrong operation address");
                    require(!j.status_mode[p], "erase completion leaves addressed partition in status mode");
                    require(contains(j,address,0x70) && contains(j,address,0xff),
                            "erase completion commands address partition zero");
                } else if (mode == "errors") {
                    for (uint16_t error : {0x0090, 0x00a0, 0x0088}) {
                        j.commands.clear(); j.status_reads.clear();
                        j.statuses = {error};
                        require(!flash.erase_block(address*2), "ready error was reported successful");
                        require(j.status_reads == std::vector<uint32_t>({address}),
                                "error status read wrong partition");
                        require(contains(j,address,0x50), "CLEAR_STATUS clears wrong partition");
                    }
                } else if (mode == "program_errors") {
                    for (uint16_t error : {0x0090, 0x00a0, 0x0088}) {
                        j.commands.clear(); j.status_reads.clear();
                        j.statuses = {0x0080, error}; // erase passes, buffered program fails
                        uint8_t data[64] = {};
                        require(!flash.write(address*2, data, 64), "program status error ignored");
                        require(j.statuses.empty(), "program completion status not consumed");
                        require(j.commands.back() == std::make_pair(address, uint16_t(0x50)),
                                "program error cleanup wrong address or operation continued");
                    }
                } else {
                    for (bool burst : {false,true}) {
                        j.commands.clear(); j.status_reads.clear();
                        uint8_t data[64];
                        for (unsigned i = 0; i < 64; ++i) data[i] = (i*13 + 7) & 255;
                        flash._has_burst = burst;
                        require(flash.write(address*2, data, sizeof(data)), "nonzero-partition program failed");
                        require(flash.verify(address*2, data, sizeof(data)), "program byte ordering/data failed");
                        require(!j.status_mode[p], "program completion leaves addressed partition status mode");
                        require(contains(j,address,0x50) && contains(j,address,0x70),
                                "program status commands hardcode partition zero");
                        for (auto command : j.commands)
                            if (command.second == 0x50 || command.second == 0x70 || command.second == 0xff)
                                require(command.first == address, "program mode command targets wrong partition");
                    }
                }
            }
        } else { throw std::runtime_error("unknown regression mode"); }
        std::cout << "partition-address control passed: " << mode << '\n';
    } catch (const std::exception &error) {
        std::cerr << "partition-address production break: " << error.what() << '\n';
        return 1;
    }
}
