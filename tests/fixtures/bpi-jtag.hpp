#pragma once
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>
class Jtag {
public:
    std::vector<uint8_t> image;
    uint32_t reads = 0;
    int fail_address = -1;
    bool status_mode = false;
    static uint8_t reverse(uint8_t b) {
        uint8_t r = 0;
        for (int i = 0; i < 8; ++i) r |= ((b >> i) & 1) << (7 - i);
        return r;
    }
    int shiftIR(uint8_t *, uint8_t *, int) { return 0; }
    int shiftDR(const uint8_t *tx, uint8_t *rx, int bits) {
        uint64_t p = 0;
        for (int i = 0; i < 6; ++i) p |= uint64_t(tx[i]) << (i * 8);
        uint32_t addr = ((p >> 5) & 0x1ffffff) * 2;
        if (!rx) {
            uint16_t data = (p >> 30) & 0xffff;
            if (data == 0x70) status_mode = true;
            if (data == 0xff) status_mode = false;
            return 0;
        }
        if (int(addr) == fail_address) throw std::runtime_error("transport read failed");
        ++reads;
        uint16_t word = status_mode ? 0x80 :
            (uint16_t(reverse(image.at(addr))) << 8) |
            reverse(addr + 1 < image.size() ? image[addr + 1] : 0xff);
        std::memset(rx, 0, (bits + 7) / 8);
        for (int i = 0; i < 16; ++i) rx[(51+i)/8] |= ((word >> i) & 1) << ((51+i)%8);
        return 0;
    }
    void flush() {}
};
