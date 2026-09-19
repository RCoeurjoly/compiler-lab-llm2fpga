"""Contract tests for the authenticated fixed-width compiler replay package."""
import hashlib
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analysis" / "build_compiler_trace_replay.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_compiler_trace_replay", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRACE = (
    "Q 0 000087f0\n"
    "R 0 000087f0 00000000000000000280010109621d1e\n"
    "Q 1 00000020\n"
    "R 1 00000020 ffeeddccbbaa99887766554433221100\n"
).encode("ascii")
EXPECTED = (
    struct.pack("<I", 0x87F0)
    + bytes.fromhex("1e1d6209010180020000000000000000")
    + struct.pack("<I", 0x20)
    + bytes.fromhex("00112233445566778899aabbccddeeff")
)


class CompilerTraceReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = _load()

    def bindings(self, trace=TRACE):
        return {
            "source_trace_sha256": hashlib.sha256(trace).hexdigest(),
            "candidate_sha256": "a" * 64,
            "image_sha256": "b" * 64,
            "prompt": [7454, 2402, 257, 640],
            "token": 11,
        }

    def build(self, trace=TRACE, bindings=None):
        directory = tempfile.TemporaryDirectory(prefix="compiler-trace-replay-")
        self.addCleanup(directory.cleanup)
        work = Path(directory.name)
        source, output = work / "reference.trace", work / "replay.bin"
        source.write_bytes(trace)
        manifest = self.module.build_replay(source, output, bindings or self.bindings(trace))
        return output, manifest

    def test_valid_pairs_preserve_wishbone_lane_order_and_authentication_bindings(self):
        output, manifest = self.build()
        self.assertEqual(output.read_bytes(), EXPECTED)
        self.assertEqual(manifest["schema"], "tinystories-1m-compiler-trace-replay-v1")
        self.assertEqual(manifest["record_count"], 2)
        self.assertEqual(manifest["record_bytes"], 20)
        self.assertEqual(manifest["binary_sha256"], hashlib.sha256(EXPECTED).hexdigest())
        self.assertEqual(manifest["source_trace_sha256"], hashlib.sha256(TRACE).hexdigest())
        self.assertEqual(manifest["candidate_sha256"], "a" * 64)
        self.assertEqual(manifest["image_sha256"], "b" * 64)
        self.assertEqual(manifest["prompt"], [7454, 2402, 257, 640])
        self.assertEqual(manifest["token"], 11)
        self.assertEqual(manifest["byte_order"], "little-endian uint32 address; Wishbone lane-order response bytes")

    def test_rejects_bad_trace_or_binding_before_replacing_existing_output(self):
        mutations = {
            "missing response": TRACE.rsplit(b"R 1", 1)[0],
            "response-address mismatch": TRACE.replace(b"R 1 00000020", b"R 1 00000024"),
            "duplicate sequence": TRACE.replace(b"Q 1", b"Q 0"),
            "reordered pair": b"".join(TRACE.splitlines(keepends=True)[2:] + TRACE.splitlines(keepends=True)[:2]),
            "trailing garbage": TRACE + b"not a trace record\n",
            "changed response data": TRACE.replace(b"ffeeddccbbaa99887766554433221100", b"ffeeddccbbaa99887766554433221101"),
        }
        for label, trace in mutations.items():
            with self.subTest(label=label):
                self.assert_rejected_without_replacement(trace, self.bindings())
        bad_bindings = self.bindings()
        bad_bindings["source_trace_sha256"] = "0" * 64
        self.assert_rejected_without_replacement(TRACE, bad_bindings)

    def assert_rejected_without_replacement(self, trace, bindings):
        with tempfile.TemporaryDirectory(prefix="compiler-trace-replay-") as directory:
            work = Path(directory)
            source, output = work / "reference.trace", work / "replay.bin"
            source.write_bytes(trace)
            output.write_bytes(b"existing authenticated package")
            with self.assertRaises(self.module.TraceReplayError):
                self.module.build_replay(source, output, bindings)
            self.assertEqual(output.read_bytes(), b"existing authenticated package")


if __name__ == "__main__":
    unittest.main()
