#!/usr/bin/env python3
"""Prove that raw Futil constants preserve Calyx f32 storage words."""

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path


SCHEMA = "rc-calyx-f32-constant-bits-v1"
UINT32_MAX = (1 << 32) - 1
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_.$-]*"


class VerificationError(ValueError):
    """A source-to-Futil bit-preservation invariant was violated."""


def _round_half_even(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    twice_remainder = remainder << 1
    if twice_remainder > denominator or (
        twice_remainder == denominator and quotient & 1
    ):
        return quotient + 1
    return quotient


def _scaled_round(value: Fraction, shift: int) -> int:
    numerator = value.numerator
    denominator = value.denominator
    if shift >= 0:
        numerator <<= shift
    else:
        denominator <<= -shift
    return _round_half_even(numerator, denominator)


def _floor_log2(value: Fraction) -> int:
    numerator = value.numerator
    denominator = value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < denominator << exponent:
            exponent -= 1
    elif numerator << -exponent < denominator:
        exponent -= 1
    return exponent


def decimal_literal_to_f32_word(literal: str) -> int:
    """Return the IEEE-754 binary32 word for a finite decimal MLIR literal.

    Decimal supplies the lexical sign/coefficient/exponent; Fraction keeps the
    value exact while this function performs binary32 round-to-nearest-even.
    """

    try:
        decimal = Decimal(literal)
    except InvalidOperation as error:
        raise VerificationError(f"invalid decimal f32 literal {literal!r}") from error
    if not decimal.is_finite():
        raise VerificationError(f"decimal f32 literal must be finite: {literal!r}")

    parts = decimal.as_tuple()
    coefficient = 0
    for digit in parts.digits:
        coefficient = coefficient * 10 + digit
    if parts.exponent >= 0:
        value = Fraction(coefficient * (10 ** parts.exponent), 1)
    else:
        value = Fraction(coefficient, 10 ** (-parts.exponent))
    sign_word = parts.sign << 31
    if not coefficient:
        return sign_word

    exponent = _floor_log2(value)
    if exponent >= -126:
        significand = _scaled_round(value, 23 - exponent)
        if significand == (1 << 24):
            significand >>= 1
            exponent += 1
        if exponent > 127:
            return sign_word | 0x7F800000
        return sign_word | ((exponent + 127) << 23) | (significand - (1 << 23))

    fraction = _scaled_round(value, 149)
    if fraction == 0:
        return sign_word
    if fraction >= (1 << 23):
        return sign_word | (1 << 23)
    return sign_word | fraction


def f32_literal_to_word(literal: str) -> int:
    literal = literal.strip()
    if literal.lower().startswith("0x"):
        try:
            word = int(literal[2:], 16)
        except ValueError as error:
            raise VerificationError(f"invalid hexadecimal f32 literal {literal!r}") from error
        if word > UINT32_MAX:
            raise VerificationError(f"f32 hexadecimal word outside u32: {literal!r}")
        return word
    return decimal_literal_to_f32_word(literal)


def _without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _component_body_opening(text: str, start: int) -> int | None:
    """Find a component body, skipping braces in port/result attributes."""

    parentheses = 0
    position = start
    while position < len(text):
        character = text[position]
        if character == "(":
            parentheses += 1
        elif character == ")":
            parentheses -= 1
            if parentheses < 0:
                raise VerificationError("component signature has an unmatched closing parenthesis")
        elif character == "{" and parentheses == 0:
            return position
        position += 1
    return None


def _named_bodies(text: str, pattern: str, language: str):
    for match in re.finditer(pattern, text):
        brace = _component_body_opening(text, match.end())
        if brace is None:
            raise VerificationError(f"{language} component {match.group('name')} has no body")
        depth = 0
        for position in range(brace, len(text)):
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
                if depth == 0:
                    yield match.group("name"), text[brace + 1 : position]
                    break
        else:
            raise VerificationError(
                f"{language} component {match.group('name')} has an unclosed body"
            )


def _add_constant(
    constants: dict[tuple[str, str], int], component: str, symbol: str, word: int, source: str
) -> None:
    key = (component, symbol)
    if key in constants:
        raise VerificationError(f"duplicate {source} constant {component}/{symbol}")
    constants[key] = word


def parse_calyx_constants(text: str) -> dict[tuple[str, str], int]:
    constants: dict[tuple[str, str], int] = {}
    component_pattern = rf"calyx\.component\s+@(?P<name>{IDENTIFIER})(?=\s|\()"
    constant_pattern = re.compile(
        rf"calyx\.constant\s+@(?P<symbol>{IDENTIFIER})\s+<"
        r"(?P<literal>[^>]+?)\s*:\s*f32>"
    )
    for component, body in _named_bodies(
        _without_comments(text), component_pattern, "Calyx MLIR"
    ):
        for match in constant_pattern.finditer(body):
            _add_constant(
                constants,
                component,
                match.group("symbol"),
                f32_literal_to_word(match.group("literal")),
                "Calyx MLIR",
            )
    return constants


def parse_futil_constants(text: str) -> dict[tuple[str, str], int]:
    text = _without_comments(text)
    if re.search(r"\bstd_float_const\s*\(", text):
        raise VerificationError("legacy std_float_const is forbidden in raw Futil")

    constants: dict[tuple[str, str], int] = {}
    component_pattern = rf"\bcomponent\s+(?P<name>{IDENTIFIER})(?=\s|\()"
    cell_pattern = re.compile(
        rf"(?<![A-Za-z0-9_.$-])(?P<symbol>{IDENTIFIER})\s*=\s*"
        r"(?P<primitive>[A-Za-z_][A-Za-z0-9_.]*)\s*\((?P<args>[^;]*)\)\s*;"
    )
    for component, body in _named_bodies(text, component_pattern, "Futil"):
        for match in cell_pattern.finditer(body):
            if match.group("primitive") != "std_const":
                continue
            arguments = match.group("args").strip()
            arguments_match = re.fullmatch(r"(\d+)\s*,\s*(\d+)", arguments)
            if not arguments_match:
                raise VerificationError(
                    f"invalid std_const arguments for {component}/{match.group('symbol')}: "
                    f"{arguments!r}"
                )
            width = int(arguments_match.group(1))
            word = int(arguments_match.group(2))
            if width != 32:
                raise VerificationError(
                    f"std_const width for {component}/{match.group('symbol')} is {width}, expected 32"
                )
            if word > UINT32_MAX:
                raise VerificationError(
                    f"std_const word for {component}/{match.group('symbol')} is outside u32: {word}"
                )
            _add_constant(constants, component, match.group("symbol"), word, "Futil")
    return constants


def verify(calyx_mlir: Path, futil: Path, receipt: Path) -> None:
    calyx_text = calyx_mlir.read_text(encoding="utf-8")
    futil_text = futil.read_text(encoding="utf-8")
    source_constants = parse_calyx_constants(calyx_text)
    futil_constants = parse_futil_constants(futil_text)

    source_keys = set(source_constants)
    futil_keys = set(futil_constants)
    missing = sorted(source_keys - futil_keys)
    extra = sorted(futil_keys - source_keys)
    if missing:
        raise VerificationError("missing Futil constants: " + ", ".join("/".join(key) for key in missing))
    if extra:
        raise VerificationError("extra Futil constants: " + ", ".join("/".join(key) for key in extra))

    for key in sorted(source_keys):
        expected = source_constants[key]
        actual = futil_constants[key]
        if actual != expected:
            raise VerificationError(
                f"word mismatch for {key[0]}/{key[1]}: expected {expected}, got {actual}"
            )

    constants = [
        {"component": component, "symbol": symbol, "word_u32": source_constants[(component, symbol)]}
        for component, symbol in sorted(source_keys)
    ]
    payload = {
        "calyx_mlir_sha256": hashlib.sha256(calyx_text.encode("utf-8")).hexdigest(),
        "constants": constants,
        "futil_sha256": hashlib.sha256(futil_text.encode("utf-8")).hexdigest(),
        "mismatch_count": 0,
        "schema": SCHEMA,
        "status": "pass",
    }
    receipt.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calyx-mlir", required=True, type=Path)
    parser.add_argument("--futil", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        verify(args.calyx_mlir, args.futil, args.receipt)
    except (OSError, VerificationError) as error:
        print(f"verify_calyx_f32_constant_bits: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
