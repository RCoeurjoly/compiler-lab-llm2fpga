import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RcMathExpBlockerPacketTest(unittest.TestCase):
    def test_packet_keeps_the_canonical_boundary(self) -> None:
        packet = (
            ROOT / "docs/results/2026-07-16-rc-math-exp-blocker-packet.md"
        ).read_text(encoding="utf-8")
        self.assertIn("tinystories-w8a8-rc-study-mask9-vocab6-width2", packet)
        self.assertIn("math.exp", packet)
        self.assertIn("not numerical-equivalence evidence", packet)
        self.assertIn("hardware-oracle gate has not run", packet)
        self.assertNotIn("math.exp is exact", packet.lower())

    def test_corpus_result_preserves_pdf_boundary(self) -> None:
        corpus = (
            ROOT / "docs/results/2026-07-16-rc-math-exp-fpga-corpus.md"
        ).read_text(encoding="utf-8")
        self.assertIn("PDFs were read locally and were not copied", corpus)
        self.assertIn("approximation or co-design evidence", corpus)
        self.assertNotIn("bit-exact route", corpus.lower())


if __name__ == "__main__":
    unittest.main()
