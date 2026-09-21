#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <deque>
#include <map>
#include <stdexcept>
#include <utility>
#include <vector>
// MT28GU512: eight independently selected 64-Mbit / 8-MiB partitions.
// Only the external JTAG/flash boundary is modeled; production BPI methods run.
class Jtag {
public:
    std::array<bool, 8> status_mode{{true, true, true, true, true, true, true, true}};
    std::deque<uint16_t> statuses;
    std::vector<std::pair<uint32_t, uint16_t>> commands;
    std::vector<uint32_t> status_reads;
    std::map<uint32_t, uint16_t> words;
    bool expect_count = false;
    uint32_t remaining = 0;
    static uint64_t unpack(const uint8_t *bytes, unsigned start, unsigned count) {
        uint64_t value = 0;
        for (unsigned i = 0; i < count; ++i)
            value |= uint64_t((bytes[(start+i)/8] >> ((start+i)%8)) & 1) << i;
        return value;
    }
    void write_word(uint32_t address, uint16_t value) {
        if (expect_count) { remaining = uint32_t(value) + 1; expect_count = false; return; }
        if (remaining) { words[address] = value; --remaining; return; }
        commands.emplace_back(address, value);
        auto partition = address / 0x400000;
        if (value == 0x70 || value == 0x50 || value == 0xe9 || value == 0x20)
            status_mode.at(partition) = true;
        if (value == 0xff) status_mode.at(partition) = false;
        if (value == 0xe9) expect_count = true;
    }
    int shiftIR(uint8_t *, uint8_t *, int) { return 0; }
    int shiftDR(const uint8_t *tx, uint8_t *rx, int bits) {
        uint32_t address = unpack(tx, 5, 25);
        unsigned command = unpack(tx, 1, 4);
        if (!rx) {
            if (command == 4) {
                unsigned count = unpack(tx, 30, 16);
                for (unsigned i = 0; i < count; ++i)
                    write_word(address + i, unpack(tx, 46 + 37*i, 16));
            } else { write_word(address, unpack(tx, 30, 16)); }
            return 0;
        }
        uint16_t value;
        if (status_mode.at(address / 0x400000)) {
            status_reads.push_back(address);
            value = statuses.empty() ? 0x0080 : statuses.front();
            if (!statuses.empty()) statuses.pop_front();
        } else { value = words[address]; }
        std::memset(rx, 0, (bits + 7) / 8);
        for (int i = 0; i < 16; ++i)
            rx[(51+i)/8] |= ((value >> i) & 1) << ((51+i)%8);
        return 0;
    }
    void flush() {}
};
