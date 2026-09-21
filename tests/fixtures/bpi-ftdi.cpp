#include <cstdint>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using std::string;
int read_result = 4, write_result = 4;
std::vector<int> reads;
unsigned read_index = 0;
unsigned payload_index = 0;
unsigned char *payload_base = nullptr;
int ftdi_write_data(void *, const unsigned char *, int) { return write_result; }
int ftdi_read_data(void *, unsigned char *buffer, int remaining) {
    int n = read_index < reads.size() ? reads[read_index++] : read_result;
    if (buffer != payload_base + payload_index || remaining != int(4 - payload_index))
        throw std::runtime_error("incorrect receive pointer/remaining count");
    if (n > 0 && n <= remaining)
        for (int i = 0; i < n; ++i) buffer[i] = 0x41 + payload_index++;
    return n;
}
const char *ftdi_get_error_string(void *) { return "controlled transport failure"; }
void printError(const string &) {}
const int SEND_IMMEDIATE = 0;
class FTDIpp_MPSSE {
public:
    int _num = 4;
    unsigned char _buffer[8] = {};
    void *_ftdi = nullptr;
    int mpsse_store(int) { return 0; }
    int mpsse_write();
    int mpsse_read(unsigned char *, int);
};
// METHODS
int main() {
    for (int rc : {-1, 0, 3}) {
        FTDIpp_MPSSE io;
        write_result = rc;
        bool threw = false;
        try { io.mpsse_write(); } catch (const std::runtime_error &) { threw = true; }
        if (!threw) return 1;
    }
    write_result = 4;
    FTDIpp_MPSSE partial;
    reads = {0, 1, 0, 2, 1};
    read_index = 0;
    unsigned char full[4] = {};
    payload_base = full; payload_index = 0;
    if (partial.mpsse_read(full, 4) != 4 || read_index != 5) return 4;
    if (std::vector<unsigned char>(full, full + 4) != std::vector<unsigned char>{0x41,0x42,0x43,0x44}) return 5;
    // Fifteen zero reads are allowed on each side of positive progress:
    // progress must reset the consecutive-stall budget, not merely count bytes.
    FTDIpp_MPSSE resumed;
    reads.assign(15, 0); reads.push_back(1);
    reads.insert(reads.end(), 15, 0); reads.push_back(3);
    read_index = 0; payload_index = 0;
    if (resumed.mpsse_read(full, 4) != 4 || read_index != 32) return 6;
    if (std::vector<unsigned char>(full, full + 4) != std::vector<unsigned char>{0x41,0x42,0x43,0x44}) return 7;
    reads.clear();
    write_result = 4;
    for (int rc : {-1, 0}) {
        FTDIpp_MPSSE io;
        read_result = rc;
        bool threw = false;
        unsigned char data[4] = {};
        payload_base = data; payload_index = 0;
        try { io.mpsse_read(data, 4); } catch (const std::runtime_error &) { threw = true; }
        if (!threw) return 2;
    }
    FTDIpp_MPSSE io;
    read_result = 4;
    unsigned char data[4] = {};
    payload_base = data; payload_index = 0;
    if (io.mpsse_read(data, 4) != 4) return 3;
    if (std::vector<unsigned char>(data, data + 4) != std::vector<unsigned char>{0x41,0x42,0x43,0x44}) return 8;
}
