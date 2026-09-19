# SPDX-License-Identifier: MIT

# Proven YPCB two-byte-lane UberDDR3 profile.
for name, mhz in [
    ("controller_clk", 83.333333),
    ("clk25_raw", 83.333333),
    ("clk100_raw", 333.333333),
    ("clk100_90_raw", 333.333333),
    ("ddr3_clk", 333.333333),
    ("ddr3_clk_90", 333.333333),
    ("clk200_raw", 200.0),
    ("ref_clk", 200.0),
    ("rowstream_ddr3.controller_clk", 83.333333),
    ("rowstream_ddr3.clk25_raw", 83.333333),
    ("rowstream_ddr3.clk100_raw", 333.333333),
    ("rowstream_ddr3.clk100_90_raw", 333.333333),
    ("rowstream_ddr3.ddr3_clk", 333.333333),
    ("rowstream_ddr3.ddr3_clk_90", 333.333333),
    ("rowstream_ddr3.clk200_raw", 200.0),
    ("rowstream_ddr3.ref_clk", 200.0),
    ("impl.rowstream_ddr3.controller_clk", 83.333333),
    ("impl.rowstream_ddr3.clk25_raw", 83.333333),
    ("impl.rowstream_ddr3.clk100_raw", 333.333333),
    ("impl.rowstream_ddr3.clk100_90_raw", 333.333333),
    ("impl.rowstream_ddr3.ddr3_clk", 333.333333),
    ("impl.rowstream_ddr3.ddr3_clk_90", 333.333333),
    ("impl.rowstream_ddr3.clk200_raw", 200.0),
    ("impl.rowstream_ddr3.ref_clk", 200.0),
    # The PCIe+DDR isolated boundary uses a different instance name from the
    # rowstream wrapper; keep its internal clocks under the same fixed contract.
    ("isolated_ddr3.controller_clk", 83.333333),
    ("isolated_ddr3.clk25_raw", 83.333333),
    ("isolated_ddr3.clk100_raw", 333.333333),
    ("isolated_ddr3.clk100_90_raw", 333.333333),
    ("isolated_ddr3.ddr3_clk", 333.333333),
    ("isolated_ddr3.ddr3_clk_90", 333.333333),
    ("isolated_ddr3.clk200_raw", 200.0),
    ("isolated_ddr3.ref_clk", 200.0),
    ("pcie_user_clk", 62.5),
    ("impl.pcie_user_clk", 62.5),
    ("pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i.userclk1", 62.5),
    ("impl.pcie_7x_top_aximm_i.pcie_7x_i.in_module_mmcm.pipe_clock_i.userclk1", 62.5),
]:
    ctx.addClock(name, mhz)
