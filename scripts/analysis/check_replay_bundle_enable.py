"""Fail closed if response inputs reach any of the 160 replay bundle enables.

Accepts either proc/opt elaboration JSON or synth_xilinx JSON, including the
flattened board top. Sequential Q boundaries terminate combinational tracing.
"""
import argparse
import json
from pathlib import Path


def check_bundle_enable(design):
    candidates = [(name, module) for name, module in design["modules"].items()
                  if any(n.endswith("active_expected") for n in module["netnames"])]
    assert len(candidates) == 1, "expected exactly one replay-containing module"
    name, module = candidates[0]
    nets = module["netnames"]
    expected_name, = [n for n in nets if n.endswith("active_expected")]
    prefix = expected_name.removesuffix("active_expected")
    bundle = nets[prefix + "active_address"]["bits"] + nets[expected_name]["bits"]
    assert len(bundle) == len(set(bundle)) == 160, "request bundle must contain 160 distinct bits"
    forbidden = set()
    board = name == "compiler_ddr3_trace_replay_top" and prefix == "replay_bridge.csr.replay."
    for signal in ("wb_rdata", "wb_ack", "wb_err"):
        # Board ABC folds ACK/local ERR into LUTs and drops these intermediate
        # names. The strict control-only leaf whitelist below replaces them;
        # never silently omit a missing source in the standalone-core check.
        if board and signal != "wb_rdata" and prefix + signal not in nets:
            continue
        forbidden.update(b for b in nets[prefix + signal]["bits"] if isinstance(b, int))
    # ABC can remove this named intermediate; input ports remain mandatory.
    if prefix + "response" in nets:
        forbidden.update(nets[prefix + "response"]["bits"])
    allowed_leaves = None
    if board:
        allowed_names = [prefix + signal for signal in
                         ("state", "active", "sealed", "fifo_level", "expected_count",
                          "pushed_count", "calib_complete")]
        allowed_names += ["replay_bridge.csr." + signal for signal in
                          ("awaddr", "wdata", "wstrb", "staged_mask", "s_axi_bvalid",
                           "aw_pending", "w_pending", "transport_reset")]
        allowed_names += ["replay_bridge.abort_sync"]
        allowed_leaves = {bit for n in allowed_names for bit in nets[n]["bits"]
                          if isinstance(bit, int)}
        # Also prohibit the unqualified controller return, before owner muxes.
        forbidden.update(nets["rowstream_ddr3.memory_wb_data"]["bits"])
        forbidden.update(nets["replay_bridge.wb_err"]["bits"])
    drivers = {}
    for cell_name, cell in module["cells"].items():
        for port, direction in cell["port_directions"].items():
            if direction == "output":
                for bit in cell["connections"][port]:
                    if isinstance(bit, int):
                        assert bit not in drivers, f"multiple drivers: {bit}"
                        drivers[bit] = (cell_name, cell, port)

    def sequential(cell):
        kind = cell["type"]
        return kind.startswith(("FD", "$dff", "$sdff", "$adff", "$_DFF"))

    enables = set()
    for bit in bundle:
        assert bit in drivers, f"undriven bundle bit {bit}"
        cell_name, cell, port = drivers[bit]
        assert sequential(cell) and port == "Q", f"non-register bundle driver: {cell_name}"
        enable_port, = [p for p in ("CE", "EN", "E") if p in cell["connections"]]
        enables.update(cell["connections"][enable_port])
    assert len(enables) == 1, "address and expected data must share one load enable"
    pending = list(enables)
    visited = set()
    leaves = set()
    while pending:
        bit = pending.pop()
        if not isinstance(bit, int) or bit in visited:
            continue
        visited.add(bit)
        assert bit not in forbidden, f"response-dependent bundle enable at bit {bit}"
        if bit not in drivers:
            leaves.add(bit)
            continue
        _, cell, _ = drivers[bit]
        if sequential(cell):
            leaves.add(bit)
            continue
        assert not cell["type"].startswith(("RAM", "$mem")), "unexpected memory in enable cone"
        for port, direction in cell["port_directions"].items():
            if direction == "input":
                pending.extend(cell["connections"][port])
    if allowed_leaves is not None:
        assert leaves <= allowed_leaves, f"non-control bundle-enable leaves: {sorted(leaves - allowed_leaves)}"
    return {"module": name, "bundle_bits": len(bundle), "enable_bits": sorted(enables),
            "combinational_cone_bits": len(visited), "leaf_bits": len(leaves),
            "control_only_board_leaves": board, "response_independent": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_bundle_enable(json.loads(args.netlist.read_text())), sort_keys=True))


if __name__ == "__main__":
    main()
