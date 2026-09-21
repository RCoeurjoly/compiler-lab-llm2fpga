#include "bpiFlash.hpp"
#include <cassert>
#include <iostream>
#include <string>
int main() {
    Jtag jtag;
    jtag.image.resize(9002);
    for (size_t i = 0; i < jtag.image.size(); ++i) jtag.image[i] = (i * 13 + 7) & 255;
    auto expected = jtag.image;
    BPIFlash flash(&jtag, -1);
    assert(flash.verify(2, expected.data() + 2, 8999));
    assert(jtag.reads == 4500); // includes the odd terminal byte, past two chunks
    for (int address : {2, 66, 4096, 8999, 9000}) {
        jtag.image[address] ^= 1;
        bool failed = false;
        try { flash.verify(2, expected.data() + 2, 8999); }
        catch (const std::runtime_error &e) {
            failed = std::string(e.what()).find("expected") != std::string::npos &&
                     std::string(e.what()).find("actual") != std::string::npos;
        }
        assert(failed);
        jtag.image[address] ^= 1;
    }
    jtag.fail_address = 8194;
    bool failed = false;
    try { flash.verify(2, expected.data() + 2, 8999); }
    catch (const std::runtime_error &) { failed = true; }
    assert(failed);
    jtag.fail_address = -1;
    jtag.image[0] ^= 1;
    assert(!flash.write(0, expected.data(), 64)); // old first-32 check must fail
    std::cout << "all full BPI verification controls passed\n";
}
