import unittest

from scripts.pipeline import lower_fixed_point_model_to_calyx as pipeline


class PackedTokenLayoutTest(unittest.TestCase):
    def test_exact_addresses_cover_vocabulary_and_hidden_lanes(self):
        self.assertEqual(pipeline.PACKED_TOKEN_CODE_BANKS, 25)
        self.assertEqual(pipeline.packed_token_code_location(0, 0), (0, 0, 0))
        self.assertEqual(pipeline.packed_token_code_location(0, 7), (0, 0, 7))
        self.assertEqual(pipeline.packed_token_code_location(0, 8), (0, 1, 0))
        self.assertEqual(pipeline.packed_token_code_location(2047, 63), (0, 16383, 7))
        self.assertEqual(pipeline.packed_token_code_location(2048, 0), (1, 0, 0))
        self.assertEqual(pipeline.packed_token_code_location(50256, 63), (24, 8839, 7))

    def test_rejects_out_of_contract_indices(self):
        with self.assertRaises(ValueError):
            pipeline.packed_token_code_location(-1, 0)
        with self.assertRaises(ValueError):
            pipeline.packed_token_code_location(50257, 0)
        with self.assertRaises(ValueError):
            pipeline.packed_token_code_location(0, 64)

    def test_pack_preserves_signed_int8_lanes(self):
        codes = [-128, -1, 0, 1, 2, 63, 64, 127] + [0] * 56
        words = pipeline.pack_token_code_words(codes)
        self.assertEqual(words[0], 0x7F403F020100FF80)
        self.assertEqual(len(words), 8)

    def test_pack_requires_complete_row_major_tensor(self):
        with self.assertRaises(ValueError):
            pipeline.pack_token_code_words([0] * 7)

    def test_sparse_rows_round_trip_in_input_order(self):
        codes = [0, -3, 0, 7, 0, 0, 2, 0, 4, 0, 0, 0, -8, 0, 0, 1]
        bitmap, offsets, values = pipeline.pack_sparse_int8_rows(codes, 8)
        self.assertEqual(offsets, [0, 3, 6])
        self.assertEqual(values, [-3, 7, 2, 4, -8, 1])
        self.assertEqual(
            pipeline.unpack_sparse_int8_rows(bitmap, offsets, values, 8), codes
        )

    def test_sparse_rows_reject_bitmap_value_mismatch(self):
        bitmap, offsets, values = pipeline.pack_sparse_int8_rows([1, 0, 2, 0], 4)
        with self.assertRaises(ValueError):
            pipeline.unpack_sparse_int8_rows(bitmap, offsets, values[:-1], 4)


if __name__ == "__main__":
    unittest.main()
