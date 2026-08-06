#!/usr/bin/env python3
"""Gate Calyx-generated SV FP-to-int result captures with converter ``done``.

The Futil source supplies the semantic group-to-converter binding.  The SV
supplies the post-cell-sharing group-to-physical-register mapping.  The tool
rejects incomplete or ambiguous closure shapes instead of guessing.
"""

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


GROUP = re.compile(r"(?ms)^\s*group\s+(\w+)\s*\{(.*?^\s*\})")
INPUT = re.compile(
    r"(?m)^\s*(fptosi_\d+_reg)\.in\s*=\s*(std_fpToIntFN_\d+)\.out;\s*$"
)
WRITE_ENABLE = re.compile(
    r"(?m)^\s*(fptosi_\d+_reg)\.write_en\s*=\s*"
    r"(1'b1|std_fpToIntFN_\d+\.done)\s*;\s*$"
)
ASSIGNMENT = re.compile(
    r"(?ms)\bassign\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(.*?);"
)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def semantic_bindings(futil: str) -> list[dict[str, str]]:
    bindings = []
    for group_match in GROUP.finditer(futil):
        group, body = group_match.groups()
        input_match = INPUT.search(body)
        if input_match is None:
            continue
        result_reg, converter = input_match.groups()
        enables = WRITE_ENABLE.findall(body)
        matching = [value for reg, value in enables if reg == result_reg]
        if len(matching) != 1:
            raise ValueError(
                f"{group}: expected one write enable for {result_reg}, found {len(matching)}"
            )
        expected = {"1'b1", f"{converter}.done"}
        if matching[0] not in expected:
            raise ValueError(f"{group}: converter/write-enable binding is inconsistent")
        bindings.append(
            {
                "group": group,
                "result_reg": result_reg,
                "converter": converter,
                "done_signal": f"{converter}_done",
            }
        )
    if not bindings:
        raise ValueError("Futil contains no FP-to-int result-capture groups")
    return bindings


def top_level_question(text: str) -> int | None:
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(text):
        if char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] -= 1
            if depths[closing[char]] < 0:
                return None
        elif char == "?" and not any(depths.values()):
            return index
    return None


def matching_colon(text: str, question: int) -> int | None:
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    nested = 0
    for index in range(question + 1, len(text)):
        char = text[index]
        if char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] -= 1
        elif not any(depths.values()):
            if char == "?":
                nested += 1
            elif char == ":":
                if nested == 0:
                    return index
                nested -= 1
    return None


def flat_priority_ternary(text: str) -> tuple[list[tuple[str, str]], str] | None:
    pairs = []
    rest = text.strip()
    while True:
        question = top_level_question(rest)
        if question is None:
            return (pairs, rest) if pairs and rest else None
        colon = matching_colon(rest, question)
        if colon is None:
            return None
        condition = rest[:question].strip()
        value = rest[question + 1 : colon].strip()
        if not condition or not value:
            return None
        pairs.append((condition, value))
        rest = rest[colon + 1 :].strip()


def split_top_level_or(condition: str) -> list[str]:
    terms = []
    start = 0
    depths = {"(": 0, "[": 0, "{": 0}
    closing = {")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(condition):
        if char in depths:
            depths[char] += 1
        elif char in closing:
            depths[closing[char]] -= 1
        elif char == "|" and not any(depths.values()):
            previous = condition[index - 1] if index else ""
            following = condition[index + 1] if index + 1 < len(condition) else ""
            if previous != "|" and following != "|":
                terms.append(condition[start:index].strip())
                start = index + 1
    terms.append(condition[start:].strip())
    if any(not term for term in terms):
        raise ValueError(f"malformed OR condition: {condition!r}")
    return terms


def signal_is_term(condition: str, signal: str) -> bool:
    return any(term == signal for term in split_top_level_or(condition))


def rewrite_assignment(
    expression: str, bindings: list[dict[str, str]]
) -> tuple[str, list[str]]:
    parsed = flat_priority_ternary(expression)
    if parsed is None:
        terms = split_top_level_or(expression)
        repaired = []
        for binding in bindings:
            go = f"{binding['group']}_go_out"
            done = binding["done_signal"]
            gated = f"({go} & {done})"
            stale_indices = [index for index, term in enumerate(terms) if term == go]
            fixed_indices = [index for index, term in enumerate(terms) if term == gated]
            if len(fixed_indices) == 1 and not stale_indices:
                continue
            if len(stale_indices) != 1 or fixed_indices:
                raise ValueError(
                    f"{binding['group']}: expected one unconditional OR term, "
                    f"found {len(stale_indices)}"
                )
            terms[stale_indices[0]] = gated
            repaired.append(binding["group"])
        return " |\n ".join(terms), repaired
    pairs, fallback = parsed
    repaired = []
    pending_by_pair: dict[int, list[dict[str, str]]] = defaultdict(list)

    for binding in bindings:
        go = f"{binding['group']}_go_out"
        done = binding["done_signal"]
        exact = [
            index
            for index, (condition, value) in enumerate(pairs)
            if condition == go and value == done
        ]
        if len(exact) == 1:
            continue
        if len(exact) > 1:
            raise ValueError(f"{binding['group']}: duplicate done-gated branches")
        candidates = [
            index
            for index, (condition, value) in enumerate(pairs)
            if signal_is_term(condition, go) and re.fullmatch(r"1'[bBoOdDhH]1", value)
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"{binding['group']}: expected one unconditional SV capture branch, "
                f"found {len(candidates)}"
            )
        pending_by_pair[candidates[0]].append(binding)

    new_pairs = []
    for index, (condition, value) in enumerate(pairs):
        pending = pending_by_pair.get(index, [])
        for binding in pending:
            new_pairs.append(
                (f"{binding['group']}_go_out", binding["done_signal"])
            )
            repaired.append(binding["group"])
        if pending:
            removed = {f"{binding['group']}_go_out" for binding in pending}
            terms = [term for term in split_top_level_or(condition) if term not in removed]
            if terms:
                new_pairs.append((" |\n ".join(terms), value))
        else:
            new_pairs.append((condition, value))

    lines = []
    for condition, value in new_pairs:
        lines.append(f" {condition} ? {value} :")
    lines.append(f" {fallback}")
    return "\n".join(lines), repaired


def repair(futil: str, sv: str) -> tuple[str, list[dict[str, str]]]:
    bindings = semantic_bindings(futil)
    assignments = list(ASSIGNMENT.finditer(sv))
    by_name: dict[str, list[re.Match[str]]] = defaultdict(list)
    for match in assignments:
        by_name[match.group(1)].append(match)

    by_physical: dict[str, list[dict[str, str]]] = defaultdict(list)
    for binding in bindings:
        done_name = f"{binding['group']}_done_in"
        matches = by_name.get(done_name, [])
        if len(matches) != 1:
            raise ValueError(
                f"{binding['group']}: expected one {done_name} assignment, found {len(matches)}"
            )
        done_expression = matches[0].group(2).strip()
        physical_match = re.fullmatch(
            r"([A-Za-z_$][A-Za-z0-9_$]*)_done", done_expression
        )
        if physical_match is None:
            raise ValueError(
                f"{binding['group']}: unsupported physical-register mapping {done_expression!r}"
            )
        binding["physical_reg"] = physical_match.group(1)
        by_physical[binding["physical_reg"]].append(binding)

    replacements = []
    repaired_groups = set()
    for physical, physical_bindings in by_physical.items():
        name = f"{physical}_write_en"
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise ValueError(f"expected one {name} assignment, found {len(matches)}")
        match = matches[0]
        try:
            expression, repaired = rewrite_assignment(
                match.group(2), physical_bindings
            )
        except ValueError as error:
            groups = ", ".join(binding["group"] for binding in physical_bindings)
            raise ValueError(f"{name} ({groups}): {error}") from error
        repaired_groups.update(repaired)
        if repaired:
            replacement = f"assign {name} =\n{expression};"
            replacements.append((match.start(), match.end(), replacement))

    output = sv
    for start, end, replacement in sorted(replacements, reverse=True):
        output = output[:start] + replacement + output[end:]
    repaired_bindings = [
        binding for binding in bindings if binding["group"] in repaired_groups
    ]
    return output, repaired_bindings


def main() -> int:
    if len(sys.argv) != 5:
        print(
            f"usage: {sys.argv[0]} <model.futil> <input.sv> <output.sv> <receipt.json>",
            file=sys.stderr,
        )
        return 2
    try:
        futil = Path(sys.argv[1]).read_text(encoding="utf-8")
        source = Path(sys.argv[2]).read_text(encoding="utf-8")
        output, repaired = repair(futil, source)
        receipt = {
            "schema": "llm2fpga.sv-fptosi-handshake-repair.v1",
            "futil_sha256": sha256(futil),
            "input_sv_sha256": sha256(source),
            "output_sv_sha256": sha256(output),
            "repair_count": len(repaired),
            "bindings": repaired,
        }
        Path(sys.argv[3]).write_text(output, encoding="utf-8")
        Path(sys.argv[4]).write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"repaired {len(repaired)} FP-to-int SV capture branch(es)")
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
