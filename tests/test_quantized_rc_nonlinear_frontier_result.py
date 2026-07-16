import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "render_quantized_rc_nonlinear_frontier.py"


def load_module():
    spec = importlib.util.spec_from_file_location("nonlinear_frontier", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def route(
    primitive: str,
    operation: str,
    status: str,
    *,
    route_id: str = "direct-circt",
    classification: str = "undetermined",
    comparison: str = "not-run",
) -> dict[str, object]:
    return {
        "route_id": route_id,
        "scope": "primitive",
        "primitive": primitive,
        "documentation_id": "circt-scf-to-calyx",
        "attempt": {"status": status},
        "calyx": {"status": status},
        "census": {
            "float_ops": [operation],
            "integer_tosa_forms": [],
            "representation": "float",
        },
        "semantic_classification": classification,
        "oracle_comparison": {"status": comparison},
    }


class QuantizedRcNonlinearFrontierResultTest(unittest.TestCase):
    def test_renderer_reports_first_standard_route_frontier(self) -> None:
        module = load_module()
        matrix = {
            "schema_version": 1,
            "model_key": "tinystories-w8a8-rc-study-mask9-vocab6-width2",
            "oracle": {
                "case_ids": ["ascending", "descending", "zeros", "alternating"],
                "comparison": {"status": "not-run"},
            },
            "route_documentation": {},
            "routes": [
                route("sqrt", "math.sqrt", "accepted"),
                route("exp", "math.exp", "rejected"),
                route("tanh", "math.tanh", "rejected"),
                route("fpowi-cube", "math.fpowi", "rejected"),
            ],
            "composites": [],
        }
        slices = {"composites": []}
        reference = {
            "results": [
                {"case_id": case_id, "output_codes_i8": [0] * 6, "token_id": 0}
                for case_id in matrix["oracle"]["case_ids"]
            ]
        }

        payload = module.build_result(matrix, slices, reference)
        markdown = module.render_markdown(payload)

        self.assertEqual(payload["status"], "blocked-standard-route-frontier")
        self.assertEqual(
            payload["recommendation"]["kind"], "upstream-compiler-or-hardware-work"
        )
        self.assertIn("math.exp", payload["first_remaining_frontier"]["operation"])
        self.assertIn("not numerical equivalence evidence", markdown)

    def test_renderer_rejects_scout_exactness_claim(self) -> None:
        module = load_module()
        matrix = {
            "model_key": "tinystories-w8a8-rc-study-mask9-vocab6-width2",
            "oracle": {"case_ids": [], "comparison": {"status": "not-run"}},
            "routes": [
                route(
                    "tanh",
                    "math.tanh",
                    "accepted",
                    route_id="scout-tanh",
                    classification="exact",
                    comparison="pass",
                )
            ],
            "composites": [],
        }
        with self.assertRaisesRegex(ValueError, "approximate or scout"):
            module.build_result(matrix, {"composites": []}, {"results": []})


if __name__ == "__main__":
    unittest.main()
