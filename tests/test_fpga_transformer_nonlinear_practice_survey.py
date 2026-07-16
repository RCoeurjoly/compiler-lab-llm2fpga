import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURVEY = (
    ROOT
    / "docs"
    / "results"
    / "2026-07-16-fpga-transformer-nonlinear-practice-survey.md"
)


class FpgaTransformerNonlinearPracticeSurveyTest(unittest.TestCase):
    def test_survey_has_primary_sources_and_preserves_the_oracle_boundary(self) -> None:
        self.assertTrue(SURVEY.is_file(), SURVEY)
        text = SURVEY.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for url in (
            "https://proceedings.mlr.press/v139/kim21d.html",
            "https://dai.sjtu.edu.cn/my_file/pdf/4fcb20f6-7386-4907-a138-bb24e21d2260.pdf",
            "https://iris.polito.it/retrieve/handle/11583/2987506/cd452780-3ae7-457f-9349-d980c79d0ac7/2304.03986.pdf",
            "https://www.mdpi.com/2079-9292/14/12/2337",
            "https://www.mdpi.com/2072-666X/17/1/84",
        ):
            self.assertIn(url, text)
        for heading in (
            "## Scope and finding",
            "## Evidence map",
            "## What this does and does not authorize",
        ):
            self.assertIn(heading, text)
        for operation in ("math.exp", "math.tanh", "math.fpowi", "math.rsqrt"):
            self.assertIn(operation, text)
        self.assertIn("approximation or reformulation", normalized)
        self.assertIn(
            "does not authorize changing the frozen PT2E W8A8 oracle", normalized
        )
        self.assertIn("not a semantic-equivalence proof", normalized)


if __name__ == "__main__":
    unittest.main()
