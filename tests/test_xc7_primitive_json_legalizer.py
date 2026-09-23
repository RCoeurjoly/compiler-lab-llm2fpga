"""Regression tests for the bounded XC7 primitive JSON legalizer."""

import unittest

from scripts.pipeline.legalize_xc7_primitive_json import legalize


def _cell(primitive, width_a, *, wea, consumed_output=False, read_width_a=None, write_width_b=None):
    connections = {
        "WEA": wea,
        "DIADI": list(range(64)),
        "DIBDI": list(range(64, 128)),
        "DIPADIP": list(range(128, 136)),
        "DIPBDIP": list(range(136, 144)),
        "DOADO": list(range(144, 208)),
        "DOBDO": list(range(208, 272)),
        "DOPADOP": list(range(272, 280)),
        "DOPBDOP": list(range(280, 288)),
    }
    parameters = {"WRITE_WIDTH_A": format(width_a, "032b")}
    result = {
        "type": primitive,
        "parameters": parameters,
        "port_directions": {name: "input" for name in connections},
        "connections": connections,
    }
    if primitive == "RAMB36E1":
        result["parameters"]["WRITE_WIDTH_B"] = format(
            0 if write_width_b is None else write_width_b, "032b"
        )
        result["parameters"]["READ_WIDTH_A"] = format(
            0 if read_width_a is None else read_width_a, "032b"
        )
    if consumed_output:
        result["connections"]["O"] = [connections["DOADO"][32]]
    return result


class Xc7PrimitiveLegalizerTest(unittest.TestCase):
    def test_narrow_ramb18_keeps_logical_lane_and_physical_widths(self):
        document = {"modules": {"m": {"cells": {
            "r": _cell("RAMB18E1", 9, wea=[1, 1, 1, 1]),
        }}}}
        legalize(document)
        cell = document["modules"]["m"]["cells"]["r"]
        self.assertEqual(len(cell["connections"]["WEA"]), 2)
        self.assertEqual(cell["connections"]["WEA"][1], "0")
        self.assertEqual(len(cell["connections"]["DIADI"]), 16)
        self.assertEqual(len(cell["connections"]["DIPADIP"]), 2)
        self.assertEqual(len(cell["connections"]["DOADO"]), 16)
        self.assertEqual(len(cell["connections"]["DOPADOP"]), 2)

    def test_unused_sdp_ramb36_write_side_is_removed(self):
        document = {"modules": {"m": {"cells": {
            "r": _cell("RAMB36E1", 0, wea=[0] * 32),
        }}}}
        legalize(document)
        cell = document["modules"]["m"]["cells"]["r"]
        self.assertNotIn("WEA", cell["connections"])
        self.assertNotIn("WEA", cell["port_directions"])

    def test_full_width_ramb36_address_keeps_extension_bit(self):
        document = {"modules": {"m": {"cells": {
            "r": _cell(
                "RAMB36E1",
                0,
                wea=[],
                read_width_a=72,
                write_width_b=72,
            ),
        }}}}
        cell = document["modules"]["m"]["cells"]["r"]
        cell["connections"]["ADDRARDADDR"] = ["0"] * 15 + ["0", "1"]
        cell["connections"]["ADDRBWRADDR"] = ["0"] * 15 + ["0", "1"]
        legalize(document)
        self.assertEqual(cell["connections"]["ADDRARDADDR"], ["0"] * 15 + ["1"])
        self.assertEqual(cell["connections"]["ADDRBWRADDR"], ["0"] * 15 + ["1"])

    def test_full_width_ramb36_unexpected_address_fails_closed(self):
        document = {"modules": {"m": {"cells": {
            "r": _cell("RAMB36E1", 0, wea=[], read_width_a=72),
        }}}}
        document["modules"]["m"]["cells"]["r"]["connections"]["ADDRARDADDR"] = ["0"] * 15 + ["1", "1"]
        with self.assertRaisesRegex(ValueError, "unexpected ADDRARDADDR"):
            legalize(document)

    def test_consumed_output_lane_is_never_trimmed(self):
        document = {"modules": {"m": {"cells": {
            "r": _cell("RAMB36E1", 36, wea=[1, 1, 1, 1], consumed_output=True),
        }}}}
        with self.assertRaisesRegex(ValueError, "consumed output lanes"):
            legalize(document)


if __name__ == "__main__":
    unittest.main()
