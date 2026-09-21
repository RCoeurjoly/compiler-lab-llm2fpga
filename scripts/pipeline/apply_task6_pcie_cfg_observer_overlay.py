#!/usr/bin/env python3
"""Fail-closed passive PCIe configuration observer source overlay."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = Path(__file__).with_name("task6_pcie_cfg_observer_overlay_pins.json")
PCIE_PATH = "pcie/src/pcie_7x.v"
TOP_PATH = "pcie/src/aximm-minimal/pcie_7x_top_aximm.v"
STATUS_PATH = "llm2fpga/fpga/rtl/task6_pcie_jtag_status_shift.v"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(data: bytes, before: bytes, after: bytes, label: str) -> bytes:
    if data.count(before) != 1:
        raise ValueError(f"observer overlay anchor is not unique: {label}")
    return data.replace(before, after)


def test_fixture() -> dict[str, bytes]:
    pins = json.loads(PINS.read_text())
    result = {}
    for name, row in pins["files"].items():
        source = Path(row["source"])
        if not source.is_absolute():
            source = ROOT / source
        result[name] = source.read_bytes()
    return result


def _pcie(data: bytes) -> bytes:
    data = replace_once(data,
        b"\toutput   [2:0]                             cfg_function_number,\n",
        b"\toutput   [2:0]                             cfg_function_number,\n"
        b"\toutput                                     cfg_transaction,\n"
        b"\toutput                                     cfg_transaction_type,\n",
        "pcie ports")
    data = replace_once(data,
        b"    .cfg_transaction                            ( ),\n"
        b"    .cfg_transaction_addr                       ( ),\n"
        b"    .cfg_transaction_type                       ( ),\n",
        b"    .cfg_transaction                            (cfg_transaction),\n"
        b"    .cfg_transaction_addr                       ( ),\n"
        b"    .cfg_transaction_type                       (cfg_transaction_type),\n",
        "hard-block observation ports")
    return data


def _top(data: bytes) -> bytes:
    data = replace_once(data,
        b"  wire [5:0] tx_buf_av;\n",
        b"  wire [5:0] tx_buf_av;\n"
        b"  wire cfg_transaction;\n"
        b"  wire cfg_transaction_type;\n",
        "top observer wires")
    marker = b"\n//*/"
    if data.count(marker) < 1:
        raise ValueError("observer active-core boundary identity mismatch")
    active, inactive = data.split(marker, 1)
    active = replace_once(active,
        b"  .cfg_function_number                       ( cfg_function_number ),\n",
        b"  .cfg_function_number                       ( cfg_function_number ),\n"
        b"  .cfg_transaction                           ( cfg_transaction ),\n"
        b"  .cfg_transaction_type                      ( cfg_transaction_type ),\n",
        "core observer connections")
    active = replace_once(active,
        b"  .cfg_pcie_link_state_i(cfg_pcie_link_state),\n",
        b"  .cfg_pcie_link_state_i(cfg_pcie_link_state),\n"
        b"  .cfg_transaction_i(cfg_transaction),\n"
        b"  .cfg_transaction_type_i(cfg_transaction_type),\n",
        "status observer connections")
    active = replace_once(active,
        b"  .cfg_transaction_type_i(cfg_transaction_type),\n",
        b"  .cfg_transaction_type_i(cfg_transaction_type),\n"
        b"  .bar_araddr_i(s_axi_araddr),\n"
        b"  .bar_arvalid_i(s_axi_arvalid),\n"
        b"  .bar_arready_i(s_axi_arready),\n"
        b"  .bar_rdata_i(s_axi_rdata),\n"
        b"  .bar_rvalid_i(s_axi_rvalid),\n"
        b"  .bar_rready_i(s_axi_rready),\n",
        "BAR observer connections")
    return active + marker + inactive


def _status(data: bytes) -> bytes:
    data = replace_once(data, b"    input  wire [2:0]  cfg_pcie_link_state_i,\n",
        b"    input  wire [2:0]  cfg_pcie_link_state_i,\n"
        b"    input  wire        cfg_transaction_i,\n"
        b"    input  wire        cfg_transaction_type_i,\n",
        "status observer ports")
    data = replace_once(data, b"    input  wire        cfg_transaction_type_i,\n",
        b"    input  wire        cfg_transaction_type_i,\n"
        b"    input  wire [31:0] bar_araddr_i,\n"
        b"    input  wire        bar_arvalid_i,\n"
        b"    input  wire        bar_arready_i,\n"
        b"    input  wire [31:0] bar_rdata_i,\n"
        b"    input  wire        bar_rvalid_i,\n"
        b"    input  wire        bar_rready_i,\n",
        "BAR observer ports")
    data = replace_once(data, b"    localparam [7:0] VERSION = 8'd2;\n",
        b"    localparam [7:0] VERSION = 8'd4;\n",
        "status version")
    data = replace_once(data,
        b"        if (user_lnk_up_i)\n"
        b"            link_up_seen_count_q <= link_up_seen_count_q + 32'd1;\n"
        b"        if (user_reset_i)\n"
        b"            user_reset_seen_count_q <= user_reset_seen_count_q + 32'd1;\n",
        b"        // Version 3 reuses the existing diagnostic counters without\n"
        b"        // adding timing-sensitive state: total at bit 360, writes at 328.\n"
        b"        if (cfg_transaction_i)\n"
        b"            link_up_seen_count_q <= link_up_seen_count_q + 32'd1;\n"
        b"        if (cfg_transaction_i && cfg_transaction_type_i)\n"
        b"            user_reset_seen_count_q <= user_reset_seen_count_q + 32'd1;\n",
        "repurposed configuration counters")
    data = replace_once(data,
        b"            if (tx_live) begin\n"
        b"                tx_beat_count_q <= tx_beat_count_q + 32'd1;\n"
        b"                if (tx_sof)\n"
        b"                    tx_packet_count_q <= tx_packet_count_q + 32'd1;\n"
        b"                if (s_axis_tx_tlast_i) begin\n"
        b"                    tx_eof_count_q <= tx_eof_count_q + 32'd1;\n"
        b"                    tx_in_packet_q <= 1'b0;\n"
        b"                end else begin\n"
        b"                    tx_in_packet_q <= 1'b1;\n"
        b"                end\n"
        b"                if (!first_tx_seen_q) begin\n"
        b"                    first_tx_seen_q <= 1'b1;\n"
        b"                    first_tx_data_q <= s_axis_tx_tdata_i;\n"
        b"                end\n"
        b"            end\n",
        b"            // Version 4 reuses existing TX diagnostic state for the\n"
        b"            // AXI-Lite read boundary; it adds no counter or shift state.\n"
        b"            if (bar_arvalid_i)\n"
        b"                tx_beat_count_q <= tx_beat_count_q + 32'd1;\n"
        b"            if (bar_arvalid_i && bar_arready_i) begin\n"
        b"                tx_packet_count_q <= tx_packet_count_q + 32'd1;\n"
        b"                first_tx_data_q[31:0] <= bar_araddr_i;\n"
        b"            end\n"
        b"            if (bar_rvalid_i) begin\n"
        b"                tx_eof_count_q <= tx_eof_count_q + 32'd1;\n"
        b"                first_tx_data_q[63:32] <= bar_rdata_i;\n"
        b"            end\n",
        "repurposed BAR counters")
    data = replace_once(data,
        b"                13'd0\n"
        b"            };\n",
        b"                9'd0,\n"
        b"                (bar_rvalid_i && bar_rready_i), bar_rvalid_i,\n"
        b"                (bar_arvalid_i && bar_arready_i), bar_arvalid_i\n"
        b"            };\n",
        "BAR sticky events")
    return data


def transform_sources(sources: dict[str, bytes]) -> dict[str, bytes]:
    pins = json.loads(PINS.read_text())
    if set(sources) != set(pins["files"]):
        raise ValueError("observer input identity set mismatch")
    for name, row in pins["files"].items():
        if digest(sources[name]) != row["input_sha256"]:
            raise ValueError(f"observer input hash mismatch: {name}")
    outputs = {
        PCIE_PATH: _pcie(sources[PCIE_PATH]),
        TOP_PATH: _top(sources[TOP_PATH]),
        STATUS_PATH: _status(sources[STATUS_PATH]),
    }
    for name, row in pins["files"].items():
        expected = row.get("output_sha256")
        if expected and digest(outputs[name]) != expected:
            raise ValueError(f"observer output hash mismatch: {name}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", type=Path, required=True)
    args = parser.parse_args()
    sources = {name: (args.closure / name).read_bytes()
               for name in json.loads(PINS.read_text())["files"]}
    for name, data in transform_sources(sources).items():
        (args.closure / name).write_bytes(data)
    (args.closure / "pcie-cfg-observer-overlay.json").write_bytes(PINS.read_bytes())


if __name__ == "__main__":
    main()
