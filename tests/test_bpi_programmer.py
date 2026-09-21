"""Compile the patched BPI implementation against a controlled JTAG transport."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import resource

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/nix/store/dghyqmhlvzsl5nr8v7zx5dcf0jkj7v5i-3ae5e5e4a5f055d12f6079616cb1ec1d67bf30f1.tar.gz")
CXX = "/nix/store/9bv7dcvmfcjnmg5mnqwqlq2wxfn8d7yi-gcc-wrapper-13.2.0/bin/g++"


class BpiProgrammerTest(unittest.TestCase):
    def setUp(self):
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def test_partition_addressing_reads_crossings_and_operation_status(self):
        """Catches hardcoded partition-zero mode commands, not just bad bytes."""
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            shutil.copytree(SOURCE, source)
            source.chmod(0o755)
            for target in source.rglob("*"):
                if not target.is_symlink(): target.chmod(0o755 if target.is_dir() else 0o644)
            for name in ("0001-defer-bpi-bridge.patch", "0002-full-bpi-verification.patch"):
                subprocess.run(["patch", "--batch", "-p1", "-i", str(ROOT / "patches/openfpgaloader" / name)],
                               cwd=source, check=True, capture_output=True)
            shutil.copyfile(ROOT / "tests/fixtures/bpi-partition-jtag.hpp", source / "src/jtag.hpp")
            shutil.copyfile(ROOT / "tests/fixtures/bpi-partitions.cpp", source / "src/test.cpp")
            command = [CXX, "-std=c++17", "-O1", "-I", str(source / "src"),
                       *[str(source / "src" / name) for name in
                         ("test.cpp", "bpiFlash.cpp", "display.cpp", "progressBar.cpp")],
                       "-o", str(source / "partitions")]
            subprocess.run(command, check=True, capture_output=True, timeout=60)
            for mode in ("read_cross", "read_start", "erase", "errors", "program", "program_cross", "program_errors"):
                with self.subTest(mode=mode):
                    result = subprocess.run([str(source / "partitions"), mode], capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            target = source / "src/bpiFlash.cpp"
            original = target.read_text()
            mutations = (
                ("bpi_write(word_addr, FLASH_CMD_READ_ARRAY)", "bpi_write(0, FLASH_CMD_READ_ARRAY)", "read_start"),
                ("i == 0 || (word_addr % 0x400000u) == 0", "i == 0", "read_cross"),
                ("bpi_write(word_addr, FLASH_CMD_READ_STATUS)", "bpi_write(0, FLASH_CMD_READ_STATUS)", "erase"),
                ("uint16_t status = bpi_read(word_addr)", "uint16_t status = bpi_read(0)", "erase"),
                ("bpi_write(word_addr, FLASH_CMD_CLEAR_STATUS)", "bpi_write(0, FLASH_CMD_CLEAR_STATUS)", "errors"),
                ("bpi_write(block_word_addr, FLASH_CMD_CLEAR_STATUS)", "bpi_write(0, FLASH_CMD_CLEAR_STATUS)", "program"),
                ("wait_ready(word_addr, 30000)", "wait_ready(0, 30000)", "erase"),
                ("wait_ready(block_word_addr, 5000)", "wait_ready(0, 5000)", "program"),
                ("bpi_read((addr + i) >> 1)", "bpi_read(i >> 1)", "program"),
            )
            for before, after, mode in mutations:
                with self.subTest(mutation=before):
                    self.assertIn(before, original, "mutation did not target production behavior")
                    target.write_text(original.replace(before, after))
                    subprocess.run(command, check=True, capture_output=True, timeout=60)
                    result = subprocess.run([str(source / "partitions"), mode], capture_output=True, text=True, timeout=10)
                    self.assertNotEqual(result.returncode, 0, "hardcoded-zero/omitted-boundary mutant escaped")

    def test_ftdi_transport_never_swallows_error_or_short_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "src").mkdir()
            target = source / "src/ftdipp_mpsse.cpp"
            target.write_bytes((SOURCE / "src/ftdipp_mpsse.cpp").read_bytes())
            result = subprocess.run(["patch", "--batch", "-p1", "-i", str(ROOT / "patches/openfpgaloader/0002-full-bpi-verification.patch")],
                                    cwd=source, capture_output=True, text=True)
            # Other patch members are intentionally absent; test this exact member.
            code = target.read_text()
            begin = code.index("int FTDIpp_MPSSE::mpsse_write()")
            end = code.index("/**", begin)
            fixture = (ROOT / "tests/fixtures/bpi-ftdi.cpp").read_text().replace("// METHODS", code[begin:end])
            (source / "test.cpp").write_text(fixture)
            result = subprocess.run([CXX, "-std=c++17", str(source / "test.cpp"), "-o", str(source / "test")], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(source / "test")], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_verifier_rejects_late_corruption_and_read_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            shutil.copytree(SOURCE, source)
            source.chmod(0o755)
            for target in source.rglob("*"):
                if not target.is_symlink(): target.chmod(0o755 if target.is_dir() else 0o644)
            for name in ("0001-defer-bpi-bridge.patch", "0002-full-bpi-verification.patch"):
                patch = ROOT / "patches/openfpgaloader" / name
                self.assertTrue(patch.exists(), f"missing authorized patch {name}")
                result = subprocess.run(["patch", "--batch", "-p1", "-i", str(patch)], cwd=source, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # Stub only transport and presentation; the actual read/verify/write
            # implementations and byte transformations compile unchanged.
            shutil.copyfile(ROOT / "tests/fixtures/bpi-jtag.hpp", source / "src/jtag.hpp")
            shutil.copyfile(ROOT / "tests/fixtures/bpi-verifier.cpp", source / "src/test.cpp")
            command = [CXX, "-std=c++17", "-O1", "-I", str(source / "src"),
                       str(source / "src/test.cpp"), str(source / "src/bpiFlash.cpp"),
                       str(source / "src/display.cpp"), str(source / "src/progressBar.cpp"),
                       "-o", str(source / "verify-test")]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(source / "verify-test")], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("all full BPI verification controls passed", result.stdout)
            original = (source / "src/bpiFlash.cpp").read_text()
            for bad in (original.replace("offset < len;", "offset < 64;"),
                        original.replace('printError("Verification FAILED!");\n\t\treturn false;',
                                         'printError("Verification FAILED!");\n\t\treturn true;')):
                self.assertNotEqual(original, bad)
                (source / "src/bpiFlash.cpp").write_text(bad)
                subprocess.run(command, check=True, capture_output=True, timeout=60)
                result = subprocess.run([str(source / "verify-test")], capture_output=True, timeout=30)
                self.assertNotEqual(result.returncode, 0, "sampled/unconditional-success mutant escaped")
            # Compile the real Xilinx method with controlled device dependencies,
            # proving --verify forwards the full parsed payload length and fails.
            xilinx = (source / "src/xilinx.cpp").read_text()
            method = xilinx[xilinx.index("void Xilinx::program_bpi("):xilinx.index("float Xilinx::get_spiOverJtag_version()")]
            fixture = (ROOT / "tests/fixtures/bpi-caller.cpp").read_text()
            for mutation in (None, "missing", "short"):
                body = method
                if mutation == "missing": body = body.replace("_verify &&", "false &&")
                if mutation == "short": body = body.replace("verify(offset, data, length)", "verify(offset, data, 64)")
                (source / "caller.cpp").write_text(fixture.replace("// METHOD", body))
                subprocess.run([CXX, "-std=c++17", str(source / "caller.cpp"), "-o", str(source / "caller")], check=True, capture_output=True, timeout=30)
                result = subprocess.run([str(source / "caller")], capture_output=True, timeout=10)
                self.assertEqual(result.returncode == 0, mutation is None)


if __name__ == "__main__":
    unittest.main()
