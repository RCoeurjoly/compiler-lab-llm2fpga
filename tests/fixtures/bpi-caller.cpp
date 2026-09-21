#include <cstdint>
#include <stdexcept>
#include <string>
void printInfo(const std::string &) {}
struct ConfigBitstreamParser {
    uint8_t data[9001] = {};
    const uint8_t *getData() { return data; }
    int getLength() { return sizeof(data) * 8; }
};
struct BPIFlash {
    unsigned length = 0, address = 0;
    bool fail = false;
    bool detect() { return true; }
    bool write(unsigned, const uint8_t *, unsigned) { return true; }
    bool verify(unsigned addr, const uint8_t *, unsigned len) {
        address = addr; length = len;
        if (fail) throw std::runtime_error("read/mismatch failure");
        return true;
    }
};
struct Xilinx {
    bool _verify = true;
    BPIFlash *_bpi_flash;
    bool load_bpi_bridge() { return false; }
    void program_bpi(ConfigBitstreamParser *, unsigned);
};
// METHOD
int main() {
    BPIFlash flash;
    Xilinx x{true, &flash};
    ConfigBitstreamParser bit;
    x.program_bpi(&bit, 128);
    if (flash.length != 9001 || flash.address != 128) return 1;
    flash.fail = true;
    bool threw = false;
    try { x.program_bpi(&bit, 0); } catch (const std::runtime_error &) { threw = true; }
    if (!threw) return 2;
    x._verify = false;
    flash.length = 0;
    x.program_bpi(&bit, 0);
    if (flash.length != 0) return 3;
}
