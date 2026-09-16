import unittest

from scripts.analysis.compiler_external_memory_contract import (
    ExternalMemoryContract,
    canonical_contract_hash,
    validate_request,
)


class ExternalMemoryContractTest(unittest.TestCase):
  def test_contract_matches_validated_uberddr3_boundary(self):
    contract = ExternalMemoryContract()
    assert contract.address_bits == 32
    assert contract.line_bits == 128
    assert contract.line_bytes == 16
    assert contract.max_outstanding == 1
    assert contract.response_order == "in_order"
    assert contract.response_latency == "variable_bounded"


  def test_requests_are_byte_addresses_and_reject_overflow(self):
    contract = ExternalMemoryContract()
    assert validate_request(contract, 0) == {"address": 0, "line": 0, "lane": 0}
    assert validate_request(contract, 15) == {"address": 15, "line": 0, "lane": 15}
    assert validate_request(contract, 16) == {"address": 16, "line": 1, "lane": 0}
    with self.assertRaisesRegex(ValueError, "address width"):
      validate_request(contract, 1 << 32)
    with self.assertRaisesRegex(ValueError, "negative"):
      validate_request(contract, -1)


  def test_contract_hash_is_canonical_and_stable(self):
    left = canonical_contract_hash(ExternalMemoryContract())
    right = canonical_contract_hash(ExternalMemoryContract())
    assert left == right
    self.assertEqual(len(left), 64)


if __name__ == "__main__":
  unittest.main()
