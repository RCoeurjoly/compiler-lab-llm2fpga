"""Canonical memory contract shared by compiler backends and DDR3 adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class ExternalMemoryContract:
    """Logical byte-addressed read contract for the validated DDR3 port."""

    address_bits: int = 32
    line_bits: int = 128
    max_outstanding: int = 1
    response_order: str = "in_order"
    response_latency: str = "variable_bounded"

    @property
    def line_bytes(self) -> int:
        if self.line_bits % 8:
            raise ValueError("line width must be byte aligned")
        return self.line_bits // 8


def validate_request(contract: ExternalMemoryContract, address: int) -> dict[str, int]:
    """Validate and decode a logical byte address into DDR line/lane fields."""

    if address < 0:
        raise ValueError("negative address")
    if address >= (1 << contract.address_bits):
        raise ValueError("address width overflow")
    line_bytes = contract.line_bytes
    return {"address": address, "line": address // line_bytes, "lane": address % line_bytes}


def canonical_contract_hash(contract: ExternalMemoryContract) -> str:
    payload = json.dumps(asdict(contract), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()
