import unittest

from scripts.comparison.pack_softmax_external_abi import convert


class PackedSoftmaxAbiTest(unittest.TestCase):
    def test_exact_shape_is_packed(self):
        source = (
            'func.func @f(tensor<16x32xi32>, i32) -> tensor<16x32xi32> {\n'
            '  %0 = "llm2fpga.attention_softmax_fixed"(%arg0, %arg1) '
            ': (tensor<16x32xi32>, i32) -> tensor<16x32xi32>\n'
            '  return %0 : tensor<16x32xi32>\n'
            '}\n'
        )
        result = convert(source)
        self.assertNotIn("tensor<16x32xi32>", result)
        self.assertEqual(result.count("i16384"), 5)

    def test_wrong_shape_fails_closed(self):
        with self.assertRaises(ValueError):
            convert('"llm2fpga.attention_softmax_fixed" : tensor<16x32xi32>')


if __name__ == "__main__":
    unittest.main()
