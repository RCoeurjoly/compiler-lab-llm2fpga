import sys
sys.path.insert(0, '/home/roland/LLM2FPGA/scripts/task6')
from read_jtag_debug_ftdi_bitbang import FtdiMpsseJtag
from read_jtag_debug_xvc import reset_tap, shift_ir, clock_tms

c = FtdiMpsseJtag('210299BF3824', 0x0403, 0x6014, 1_000_000, 7)
reset_tap(c); shift_ir(c, 6, 6)
def x(cmd):
    clock_tms(c, [1, 0, 0])
    bits = c.shift([0] * 63 + [1], [(cmd >> i) & 1 for i in range(64)])
    clock_tms(c, [1, 0])
    return sum((b & 1) << i for i, b in enumerate(bits))
for p in (0x0123456789abcdef, 0xaaaaaaaaaaaaaaaa, 0x5555555555555555):
    command_response = x(0x7000000000000000 | (p & ((1 << 60) - 1)))
    status_response = x(0x3000000000000000)
    print(f'command_response={command_response:016x} status_response={status_response:016x}')
c.close()
