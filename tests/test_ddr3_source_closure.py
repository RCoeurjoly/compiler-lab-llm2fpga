import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pipeline" / "materialize_ddr3_source_closure.py"


def _load_module():
    if not SCRIPT_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("materialize_ddr3_source_closure", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


closure = _load_module()


EXPECTED_PATHS = [
    "testbench/models/IDELAYCTRL_model.v",
    "testbench/models/IDELAYE2_model.v",
    "testbench/models/IOBUF_DCIEN_model.v",
    "testbench/models/IOBUF_model.v",
    "testbench/models/IOBUFDS_DCIEN_model.v",
    "testbench/models/IOBUFDS_model.v",
    "testbench/models/ISERDESE2_model.v",
    "testbench/models/OBUFDS_model.v",
    "testbench/models/ODELAYE2_model.v",
    "testbench/models/OSERDESE2_model.v",
    "testbench/models/OBUF_model.v",
    "rtl/ddr3_controller.v",
    "rtl/ddr3_phy.v",
    "rtl/ddr3_top.v",
    "example_demo/ypcb_00338_1p1/clk_wiz.v",
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.v",
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.xdc",
    "testbench/sim_defines.vh",
    "testbench/8192Mb_ddr3_parameters.vh",
    "testbench/ddr3.sv",
    "testbench/ddr3_module.sv",
    "testbench/ddr3_dimm_micron_sim.sv",
    "testbench/xsim/glbl.v",
]

COMPILE_ORDER = [
    "testbench/models/IDELAYCTRL_model.v",
    "testbench/models/IDELAYE2_model.v",
    "testbench/models/IOBUF_DCIEN_model.v",
    "testbench/models/IOBUF_model.v",
    "testbench/models/IOBUFDS_DCIEN_model.v",
    "testbench/models/IOBUFDS_model.v",
    "testbench/models/ISERDESE2_model.v",
    "testbench/models/OBUFDS_model.v",
    "testbench/models/ODELAYE2_model.v",
    "testbench/models/OSERDESE2_model.v",
    "testbench/models/OBUF_model.v",
    "rtl/ddr3_controller.v",
    "rtl/ddr3_phy.v",
    "rtl/ddr3_top.v",
    "example_demo/ypcb_00338_1p1/clk_wiz.v",
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.v",
    "testbench/ddr3.sv",
    "testbench/ddr3_module.sv",
    "testbench/ddr3_dimm_micron_sim.sv",
    "testbench/xsim/glbl.v",
]

SUPPORT_PATHS = [
    "example_demo/ypcb_00338_1p1/ypcb_00338_1p1_ddr3.xdc",
    "testbench/sim_defines.vh",
    "testbench/8192Mb_ddr3_parameters.vh",
]


class Ddr3SourceClosureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(closure, "DDR3 source closure materializer must exist")
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "UberDDR3"
        for ordinal, logical_path in enumerate(EXPECTED_PATHS):
            path = self.root / logical_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"source {ordinal}: {logical_path}\n".encode("utf-8"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_manifest_is_deterministic_and_has_the_pinned_compile_closure(self) -> None:
        first = closure.build_manifest(self.root)
        second = closure.build_manifest(self.root)

        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "uberddr3-source-closure-v1")
        self.assertEqual(
            first["uberddr3_revision"], "4a51b9671347130759c9980d6756918f084e2124"
        )
        self.assertEqual([row["logical_path"] for row in first["sources"]], EXPECTED_PATHS)
        self.assertEqual([row["ordinal"] for row in first["sources"]], list(range(23)))
        self.assertEqual(first["include_paths"], ["testbench"])
        self.assertEqual(
            first["macros"],
            {
                "MAX_MEM": "",
                "DUAL_RANK": "",
                "SODIMM": "",
                "den8192Mb": "",
                "sg125": "",
                "x8": "",
            },
        )
        self.assertEqual(first["compile_order"], COMPILE_ORDER)
        self.assertEqual(first["support_paths"], SUPPORT_PATHS)
        self.assertFalse(any(path.endswith((".vh", ".xdc")) for path in first["compile_order"]))
        controller = first["sources"][11]
        self.assertEqual(controller["bytes"], len(b"source 11: rtl/ddr3_controller.v\n"))
        self.assertEqual(
            controller["sha256"],
            hashlib.sha256(b"source 11: rtl/ddr3_controller.v\n").hexdigest(),
        )

        rendered = closure.render_manifest(first)
        self.assertEqual(rendered, closure.render_manifest(second))
        self.assertEqual(json.loads(rendered), first)

    def test_verify_rejects_a_missing_selected_file(self) -> None:
        manifest = closure.build_manifest(self.root)
        (self.root / "rtl/ddr3_phy.v").unlink()

        with self.assertRaisesRegex(ValueError, "rtl/ddr3_phy.v"):
            closure.verify_manifest(self.root, manifest)

    def test_verify_rejects_a_hash_mismatched_selected_file(self) -> None:
        manifest = closure.build_manifest(self.root)
        path = self.root / "testbench/ddr3.sv"
        path.write_bytes(b"x" * len(path.read_bytes()))

        with self.assertRaisesRegex(ValueError, "testbench/ddr3.sv.*SHA-256"):
            closure.verify_manifest(self.root, manifest)


if __name__ == "__main__":
    unittest.main()
