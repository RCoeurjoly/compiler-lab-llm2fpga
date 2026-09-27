"""Guard the restartable synthesis boundary before Xilinx DSP inference."""

import unittest

from scripts.pipeline import synthesize_no_fsm


class SynthesizeNoFsmScriptTests(unittest.TestCase):
    def test_pre_dsp_stage_preserves_multipliers(self) -> None:
        self.assertTrue(hasattr(synthesize_no_fsm, "build_script"))
        script = synthesize_no_fsm.build_script(
            "model.sv", top="main", preserve_multipliers=True
        )
        self.assertIn("read_slang --threads 1", script)
        self.assertIn("memory_dff; opt_expr -fine; wreduce;", script)
        self.assertNotIn("alumacc", script)
        self.assertNotIn("memory -nomap", script)

    def test_legacy_coarse_stage_keeps_its_existing_passes(self) -> None:
        self.assertTrue(hasattr(synthesize_no_fsm, "build_script"))
        script = synthesize_no_fsm.build_script(
            "model.sv", top="main", preserve_multipliers=False
        )
        self.assertIn("wreduce; alumacc; share; opt;", script)
        self.assertIn("memory -nomap; opt_clean; stat;", script)


if __name__ == "__main__":
    unittest.main()
