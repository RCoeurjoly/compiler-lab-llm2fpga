import unittest

from scripts.analysis.check_task6_pnr_timing import last_max_frequency, timing_failures


class Task6PnrTimingTest(unittest.TestCase):
    def test_uses_final_report_when_log_contains_pre_and_post_route_timing(self):
        log = """
Info: Max frequency for clock 'rowstream_clk': 12.90 MHz (FAIL at 83.33 MHz)
Info: Max frequency for clock 'pcie_user_clk': 59.56 MHz (FAIL at 62.50 MHz)
Info: Max frequency for clock 'rowstream_clk': 90.00 MHz (PASS at 83.33 MHz)
Info: Max frequency for clock 'pcie_user_clk': 77.28 MHz (PASS at 62.50 MHz)
"""
        self.assertEqual(last_max_frequency(log, "rowstream_clk"), 90.0)
        self.assertEqual(timing_failures(log), [])

    def test_reports_controller_clock_failure_without_relaxing_target(self):
        log = """
Info: Max frequency for clock 'rowstream_clk': 20.48 MHz (FAIL at 83.33 MHz)
Info: Max frequency for clock 'pcie_user_clk': 77.28 MHz (PASS at 62.50 MHz)
"""
        self.assertEqual(
            timing_failures(log),
            ["rowstream_clk: 20.48 MHz < required 83.33 MHz"],
        )

    def test_missing_required_clock_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "no max-frequency result"):
            timing_failures("Info: no clock report")


if __name__ == "__main__":
    unittest.main()
