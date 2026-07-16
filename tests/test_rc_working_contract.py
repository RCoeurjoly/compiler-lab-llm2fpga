import importlib
import json
import math
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = REPO_ROOT / "TinyStories" / "rc_working_corpus.json"

try:
    contract = importlib.import_module("TinyStories.rc_working_contract")
except ModuleNotFoundError:
    contract = None


class _FakeTensor:
    def __init__(self, shape: tuple[int, ...]) -> None:
        self.shape = shape


class RcWorkingContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(
            contract,
            "TinyStories.rc_working_contract must define the working RC contract",
        )

    def test_contract_identifies_the_exact_structural_finalist(self) -> None:
        self.assertEqual(
            contract.RC_WORKING_SOURCE_MODEL_KEY,
            "tinystories-w8a8-rc-study-mask9-vocab6-width2",
        )
        self.assertEqual(
            contract.RC_WORKING_PIPELINE_ALIAS,
            "tinystories-w8a8-rc-working-via-linalg-no-handshake",
        )
        self.assertEqual(contract.CONTEXT_LENGTH, 8)
        self.assertEqual(contract.VOCAB_SIZE, 6)

    def test_corpus_has_the_four_frozen_prompts(self) -> None:
        corpus = contract.load_corpus(CORPUS_PATH)

        self.assertEqual([case["id"] for case in corpus], [
            "ascending",
            "descending",
            "zeros",
            "alternating",
        ])
        self.assertEqual(
            [case["text"] for case in corpus],
            [
                "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1",
                "tok5 tok4 tok3 tok2 tok1 tok0 tok5 tok4",
                "tok0 tok0 tok0 tok0 tok0 tok0 tok0 tok0",
                "tok0 tok5 tok0 tok5 tok0 tok5 tok0 tok5",
            ],
        )
        self.assertTrue(all(len(contract.tokenize(case["text"])) == 8 for case in corpus))

    def test_tokenize_and_decode_round_trip(self) -> None:
        text = "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1"

        self.assertEqual(contract.tokenize(text), [0, 1, 2, 3, 4, 5, 0, 1])
        self.assertEqual(contract.decode_token_ids([0, 1, 2, 3, 4, 5, 0, 1]), text)

    def test_tokenize_rejects_unknown_and_wrong_length_inputs(self) -> None:
        for text in (
            "tok0 tok1 tok2 tok3 tok4 tok5 tok0",
            "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok1 tok2",
            "tok0 tok1 tok2 tok3 tok4 tok5 tok0 tok6",
        ):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    contract.tokenize(text)

    def test_argmax_prefers_lowest_tied_index(self) -> None:
        self.assertEqual(contract.argmax_lowest([-5, 7, 7, 1, 0, -2]), 1)
        with self.assertRaises(ValueError):
            contract.argmax_lowest([0, 1, 2, 3, 4])

    def test_qparams_require_positive_finite_scale_and_integer_zero_point(self) -> None:
        contract.validate_output_qparams(0.25, 3)
        for scale in (0.0, -0.25, math.inf, math.nan):
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError):
                    contract.validate_output_qparams(scale, 3)
        for zero_point in (3.0, True):
            with self.subTest(zero_point=zero_point):
                with self.assertRaises(ValueError):
                    contract.validate_output_qparams(0.25, zero_point)

    def test_output_shape_and_canonical_result_are_fixed_to_six_codes(self) -> None:
        contract.validate_output_tensor(_FakeTensor((1, 8, 6)))
        for shape in ((1, 7, 6), (1, 8, 5), (8, 6)):
            with self.subTest(shape=shape):
                with self.assertRaises(ValueError):
                    contract.validate_output_tensor(_FakeTensor(shape))

        result = contract.canonical_result(
            case_id="ascending",
            token_ids=[0, 1, 2, 3, 4, 5, 0, 1],
            output_codes_i8=[-4, 5, 5, 1, 0, -2],
            output_scale=0.25,
            output_zero_point=1,
        )

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["case_id"], "ascending")
        self.assertEqual(result["output_qparams"], {"scale": 0.25, "zero_point": 1})
        self.assertEqual(result["output_codes_i8"], [-4, 5, 5, 1, 0, -2])
        self.assertEqual(result["logits"], [-1.25, 1.0, 1.0, 0.0, -0.25, -0.75])
        self.assertEqual(result["token_id"], 1)


if __name__ == "__main__":
    unittest.main()
