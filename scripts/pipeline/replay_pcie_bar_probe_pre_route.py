"""Post-placement, pre-route BAR ARVALID probe using existing USER1 state."""
import hashlib
import json

SOURCE_NET = "bar_arvalid"
REPLACED_NET = "pcie_7x_top_aximm_i.task6_pcie_status_i.tx_live"
EXPECTED_DRIVER = "$abc$270451$auto$blifparse.cc:557:parse_blif$280091:O6"
EXPECTED_USERS = [
    ["$abc$270451$auto$blifparse.cc:557:parse_blif$280423", "A3"],
    ["$abc$270451$auto$blifparse.cc:557:parse_blif$280532", "A2"],
    ["$abc$270451$auto$blifparse.cc:557:parse_blif$281032", "A1"],
    ["$auto$ff.cc:337:slice$177975", "CE"],
    ["$auto$xilinx_dffopt.cc:335:execute$323449", "A3"],
    ["$auto$xilinx_dffopt.cc:335:execute$323655", "A3"],
    ["$auto$xilinx_dffopt.cc:335:execute$324663", "A4"],
    ["$auto$xilinx_dffopt.cc:335:execute$324665", "A4"],
    ["$auto$xilinx_dffopt.cc:335:execute$324667", "A3"],
    ["$auto$xilinx_dffopt.cc:335:execute$324669", "A3"],
    ["$auto$xilinx_dffopt.cc:335:execute$324671", "A4"],
    ["$auto$xilinx_dffopt.cc:335:execute$324673", "A4"],
    ["$auto$xilinx_dffopt.cc:335:execute$324675", "A3"],
    ["$auto$xilinx_dffopt.cc:338:execute$326265", "A3"],
]
EXPECTED_SIGNATURE = "e12810b8261c36b4ffd976bae0e7dcb5c5d11eb6d1e00250871ecc0ff3f13d32"


def signature(users):
    rendered = json.dumps(sorted(users), separators=(",", ":")).encode()
    return hashlib.sha256(rendered).hexdigest()


old = ctx.nets[REPLACED_NET]
source = ctx.nets[SOURCE_NET]
driver = f"{old.driver.cell.name}:{old.driver.port}"
users = sorted([[user.cell.name, user.port] for user in old.users])
if driver != EXPECTED_DRIVER or users != sorted(EXPECTED_USERS) or signature(users) != EXPECTED_SIGNATURE:
    raise RuntimeError("BAR probe packed identity mismatch: " + json.dumps({
        "driver": driver, "users": users, "signature": signature(users)
    }, separators=(",", ":")))
if source.driver.cell is None:
    raise RuntimeError("BAR ARVALID source is undriven")

for cell, port in users:
    ctx.disconnectPort(cell, port)
    ctx.connectPort(SOURCE_NET, cell, port)

if old.users:
    raise RuntimeError("BAR probe left event consumers on replaced net")
print("TASK4_BAR_PROBE_PRE_ROUTE_PASS consumers=14 meaning=USER1_tx_beat_count_is_BAR_ARVALID")
