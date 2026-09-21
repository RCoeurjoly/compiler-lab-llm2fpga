import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "compose_mapped", ROOT / "scripts/pipeline/compose_mapped_yosys_json.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def design(*, boundary_ports=None, include_primitive=True, include_top=True):
    boundary_ports = boundary_ports or {
        "clk": {"direction": "input", "bits": [1]},
        "done": {"direction": "output", "bits": [2]},
    }
    modules = {"adapter": {"ports": boundary_ports, "cells": {}}}
    if include_top:
        modules["top"] = {
            "ports": {},
            "cells": {"accelerator": {"type": "adapter", "connections": {}}},
        }
    if include_primitive:
        modules["LUT5"] = {"ports": {}, "cells": {}}
    return {"creator": "test", "modules": modules}


class ComposeMappedJsonTest(unittest.TestCase):
    def test_replaces_stub_and_preserves_explicit_primitive_collision(self):
        platform = design()
        compiler = design(include_top=False)
        compiler["modules"]["LUT5"] = {"ports": {"O": {"direction": "output", "bits": [1]}}, "cells": {}}
        result, receipt = MODULE.compose(
            platform, compiler, top="top", boundary="adapter", platform_wins={"LUT5"}
        )
        self.assertEqual(result["modules"]["adapter"], compiler["modules"]["adapter"])
        self.assertEqual(result["modules"]["LUT5"], platform["modules"]["LUT5"])
        self.assertEqual(receipt["replaced_modules"], ["adapter"])
        self.assertEqual(receipt["collisions"], ["LUT5", "adapter"])


    def test_rejects_unlisted_collision(self):
        with self.assertRaisesRegex(ValueError, "platform-wins"):
            MODULE.compose(design(), design(include_top=False), top="top", boundary="adapter", platform_wins=set())


    def test_rejects_boundary_abi_mismatch(self):
        compiler = design(include_top=False)
        compiler["modules"]["adapter"]["ports"]["extra"] = {"direction": "input", "bits": [4]}
        with self.assertRaisesRegex(ValueError, "port signature"):
            MODULE.compose(design(), compiler, top="top", boundary="adapter", platform_wins={"LUT5"})


if __name__ == "__main__":
    unittest.main()
