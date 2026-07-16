import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pipeline" / "screen_fpga_llm_math_exp_corpus.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fpga_llm_math_exp_corpus", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FpgaLlmMathExpCorpusTest(unittest.TestCase):
    def make_fixture(self, directory: Path) -> tuple[Path, Path, str]:
        paper_root = directory / "paper-root"
        data_dir = paper_root / "data"
        papers_dir = paper_root / "papers"
        data_dir.mkdir(parents=True)
        papers_dir.mkdir()
        cached_pdf = papers_dir / "1111.11111v1.pdf"
        cached_pdf.write_bytes(b"fixture PDF bytes\n")
        digest = hashlib.sha256(cached_pdf.read_bytes()).hexdigest()
        catalog = {
            "schema_version": 1,
            "papers": {
                "1111.11111v1": {
                    "arxiv_id": "1111.11111",
                    "version": 1,
                    "title": "Verified fixture",
                    "abs_url": "https://arxiv.org/abs/1111.11111v1",
                    "pdf_url": "https://arxiv.org/pdf/1111.11111v1",
                    "cache": {
                        "filename": cached_pdf.name,
                        "sha256": digest,
                        "byte_count": cached_pdf.stat().st_size,
                    },
                },
                "2222.22222v1": {
                    "arxiv_id": "2222.22222",
                    "version": 1,
                    "title": "Missing fixture",
                    "abs_url": "https://arxiv.org/abs/2222.22222v1",
                    "pdf_url": "https://arxiv.org/pdf/2222.22222v1",
                    "cache": {
                        "filename": "2222.22222v1.pdf",
                        "sha256": "0" * 64,
                        "byte_count": 0,
                    },
                },
            },
        }
        catalog_path = data_dir / "catalog.json"
        catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
        fake_pdftotext = directory / "fake-pdftotext"
        fake_pdftotext.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdout.write("
            "\"page one: Softmax uses maximum subtraction.\\f\\n\""
            "\"page two: The exponential is implemented with a lookup table. NEVER_COPY_THIS_SENTENCE.\\n\""
            ")\n",
            encoding="utf-8",
        )
        os.chmod(fake_pdftotext, 0o755)
        return catalog_path, papers_dir, str(fake_pdftotext)

    def test_screen_records_page_evidence_without_retaining_source_text(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path, papers_dir, pdftotext = self.make_fixture(Path(temp_dir))
            result = module.screen_catalog(catalog_path, papers_dir, pdftotext)
            repeated = module.screen_catalog(catalog_path, papers_dir, pdftotext)

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["corpus"]["catalog_records"], 2)
        self.assertEqual(result["corpus"]["verified_pdf_records"], 1)
        self.assertEqual(result["papers"]["1111.11111v1"]["cache_status"], "verified")
        self.assertEqual(result["papers"]["1111.11111v1"]["term_pages"]["exp"], [2])
        self.assertTrue(result["papers"]["1111.11111v1"]["deep_read_candidate"])
        self.assertEqual(result["papers"]["2222.22222v1"]["cache_status"], "missing")
        self.assertNotIn("NEVER_COPY_THIS_SENTENCE", json.dumps(result))
        self.assertEqual(result, repeated)

    def test_hash_mismatch_is_not_searched(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog_path, papers_dir, pdftotext = self.make_fixture(Path(temp_dir))
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["papers"]["1111.11111v1"]["cache"]["sha256"] = "f" * 64
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            result = module.screen_catalog(catalog_path, papers_dir, pdftotext)

        paper = result["papers"]["1111.11111v1"]
        self.assertEqual(paper["cache_status"], "sha256-mismatch")
        self.assertEqual(paper["term_pages"], {})
        self.assertFalse(paper["deep_read_candidate"])

    def test_load_catalog_requires_schema_version_one_and_papers_mapping(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "catalog.json"
            path.write_text('{"schema_version": 2, "papers": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema_version"):
                module.load_catalog(path)

    def test_nix_app_keeps_the_external_paper_cache_outside_the_flake(self) -> None:
        flake = (ROOT / "flake.nix").read_text(encoding="utf-8")

        self.assertIn("rcMathExpPaperScreen = pkgs.writeShellApplication", flake)
        self.assertIn('name = "rc-math-exp-paper-screen";', flake)
        self.assertIn("runtimeInputs = [ python pkgs.poppler_utils ];", flake)
        self.assertIn("screen_fpga_llm_math_exp_corpus.py", flake)
        self.assertIn('"rc-math-exp-paper-screen" = rcMathExpPaperScreen;', flake)
        self.assertIn('apps."rc-math-exp-paper-screen"', flake)
        self.assertNotIn("/home/roland/LLM-inference-on-FPGA-papers", flake)


if __name__ == "__main__":
    unittest.main()
