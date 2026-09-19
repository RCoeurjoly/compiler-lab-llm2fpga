"""Canonical Yosys JSON proof must ignore paths and reject circuit changes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.analysis.canonicalize_yosys_json import NetlistMismatch, compare_netlists


class CanonicalizeYosysJsonTest(unittest.TestCase):
    def fixture(self, directory, root):
        root.mkdir()
        source = root / "design.sv"
        source.write_text("module top(input a, output y); assign y = a; endmodule\n")
        script = root / "run.ys"
        script.write_text(f"read_verilog -sv {source}\n")
        src = f"{source}:1.1-1.61"
        design = {
            "creator": "pinned-yosys",
            "modules": {
                "top": {
                    "attributes": {"src": src},
                    "parameter_default_values": {"WIDTH": "0001"},
                    "ports": {
                        "a": {"direction": "input", "bits": [2]},
                        "y": {"direction": "output", "bits": [3]},
                    },
                    "cells": {
                        f"$flatten.$not${source}:1$1": {
                            "hide_name": 1,
                            "type": "LUT1",
                            "parameters": {"INIT": "10"},
                            "attributes": {"src": src, "module_src": src},
                            "port_directions": {"I0": "input", "O": "output"},
                            "connections": {"I0": [2], "O": [3]},
                        }
                    },
                    "memories": {
                        "state": {"hide_name": 0, "attributes": {"src": src},
                                  "width": 1, "size": 2, "start_offset": 0}
                    },
                    "netnames": {
                        f"$not${source}:1$1_Y": {
                            "hide_name": 1, "bits": [3], "attributes": {"src": src}
                        }
                    },
                }
            },
        }
        netlist = root / "netlist.json"
        netlist.write_text(json.dumps(design, indent=2) + "\n")
        return source, script, netlist, design

    def test_physical_source_paths_are_the_only_normalized_content(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            _, left_script, left_netlist, _ = self.fixture(directory, directory / "left")
            _, right_script, right_netlist, _ = self.fixture(directory, directory / "right")
            proof = compare_netlists(left_netlist, left_script, right_netlist, right_script)
            self.assertEqual(proof["source_count"], 1)
            self.assertTrue(proof["canonical_equal"])
            self.assertEqual(proof["canonical_sha256"]["left"], proof["canonical_sha256"]["right"])
            self.assertGreater(proof["difference_classes"]["source_path_values"], 0)
            self.assertGreater(proof["difference_classes"]["source_path_keys"], 0)
            self.assertEqual(proof["difference_classes"]["unexplained"], 0)

    def test_source_byte_mutation_is_rejected_before_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            _, left_script, left_netlist, _ = self.fixture(directory, directory / "left")
            right_source, right_script, right_netlist, _ = self.fixture(directory, directory / "right")
            right_source.write_text("module top(input a, output y); assign y = !a; endmodule\n")
            with self.assertRaisesRegex(NetlistMismatch, "source SHA-256 sequence"):
                compare_netlists(left_netlist, left_script, right_netlist, right_script)

    def test_every_semantic_json_class_mutation_is_rejected(self):
        mutations = {
            "module_parameter": lambda d: d["modules"]["top"]["parameter_default_values"].update(WIDTH="0010"),
            "port_direction": lambda d: d["modules"]["top"]["ports"]["a"].update(direction="output"),
            "port_bits": lambda d: d["modules"]["top"]["ports"]["y"].update(bits=[4]),
            "cell_type": lambda d: d["modules"]["top"]["cells"][next(iter(d["modules"]["top"]["cells"]))].update(type="LUT2"),
            "cell_parameter": lambda d: d["modules"]["top"]["cells"][next(iter(d["modules"]["top"]["cells"]))]["parameters"].update(INIT="01"),
            "cell_port_direction": lambda d: d["modules"]["top"]["cells"][next(iter(d["modules"]["top"]["cells"]))]["port_directions"].update(I0="output"),
            "cell_connection": lambda d: d["modules"]["top"]["cells"][next(iter(d["modules"]["top"]["cells"]))]["connections"].update(O=[4]),
            "memory": lambda d: d["modules"]["top"]["memories"]["state"].update(size=3),
            "netname_bits": lambda d: d["modules"]["top"]["netnames"][next(iter(d["modules"]["top"]["netnames"]))].update(bits=[4]),
            "netname_name": lambda d: d["modules"]["top"]["netnames"].update(extra={"hide_name": 0, "bits": [3], "attributes": {}}),
        }
        for name, mutation in mutations.items():
            with self.subTest(mutation=name), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                _, left_script, left_netlist, _ = self.fixture(directory, directory / "left")
                _, right_script, right_netlist, right_design = self.fixture(directory, directory / "right")
                changed = copy.deepcopy(right_design)
                mutation(changed)
                right_netlist.write_text(json.dumps(changed, indent=2) + "\n")
                with self.assertRaisesRegex(NetlistMismatch, "canonical netlists differ"):
                    compare_netlists(left_netlist, left_script, right_netlist, right_script)


if __name__ == "__main__":
    unittest.main()
