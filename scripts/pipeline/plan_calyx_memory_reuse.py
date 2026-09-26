#!/usr/bin/env python3
"""Plan conservative Calyx scratch-memory reuse.

This pass is deliberately analysis-only.  It consumes generated Futil, derives
lexical first/last uses from the control schedule, and emits a deterministic
plan.  It never aliases memories by itself: a later transformation must prove
the IR-level dependencies and then apply the plan with semantic checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


DECL_RE = re.compile(
    r"@external(?:\([^)]*\))?\s+(\w+)\s*=\s*seq_mem_d1\((\d+),\s*(\d+),"
)
GROUP_RE = re.compile(r"\b(?:static\s+)?group\s+(\w+)\s*\{")


def _memory_names_in_group(body: str, memories: dict[str, dict[str, int]]) -> list[str]:
    """Resolve direct memory uses, including generated component arguments.

    The integrated exporter declares top-level cells as ``mem_N`` and passes
    them into the generated child component as ``arg_mem_N``.  Group bodies
    therefore reference the latter even though the actual external memory
    declaration is the former.  The suffix binding is emitted by the invoke
    ABI and is unambiguous for this generated form; keep the mapping local to
    this analysis pass and do not mutate the source.
    """
    result: set[str] = set()
    for token in re.findall(r"\b[A-Za-z_]\w*\b", body):
        if token in memories:
            result.add(token)
            continue
        if token.startswith("arg_"):
            candidate = token[4:]
            if candidate in memories:
                result.add(candidate)
    return sorted(result)


def _balanced(text: str, start: int) -> str:
    depth = 1
    pos = start
    while pos < len(text) and depth:
        depth += (text[pos] == "{") - (text[pos] == "}")
        pos += 1
    if depth:
        raise ValueError("unterminated Calyx group")
    return text[start : pos - 1]


def plan(text: str) -> dict[str, object]:
    memories = {
        m.group(1): {"width": int(m.group(2)), "depth": int(m.group(3))}
        for m in DECL_RE.finditer(text)
    }
    control_matches = list(re.finditer(r"\bcontrol\s*\{", text))
    if not control_matches:
        raise ValueError("generated Futil has no top-level control")

    # Calyx emits groups in a component's ``wires`` section, which may appear
    # before or after another component's control block.  Restricting the
    # search to text before the first control therefore misses the groups used
    # by the generated child component (the integrated RC currently has this
    # shape).  Parse all group declarations and collect references only from
    # actual control bodies, so declarations cannot masquerade as schedule
    # entries.
    groups: dict[str, str] = {}
    for match in GROUP_RE.finditer(text):
        groups[match.group(1)] = _balanced(text, match.end())
    uses = {group: _memory_names_in_group(body, memories) for group, body in groups.items()}
    order: list[str] = []
    for match in control_matches:
        body = _balanced(text, match.end())
        order.extend(token for token in re.findall(r"\b[A-Za-z_]\w*\b", body) if token in uses)
    positions: dict[str, list[int]] = {name: [] for name in memories}
    for position, group in enumerate(order):
        for name in uses[group]:
            positions[name].append(position)
    intervals = {
        name: {"first": min(points), "last": max(points)}
        for name, points in positions.items()
        if points
    }
    candidates: list[dict[str, object]] = []
    names = sorted(intervals)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            if memories[left] != memories[right]:
                continue
            a, b = intervals[left], intervals[right]
            if a["last"] < b["first"] or b["last"] < a["first"]:
                first, second = (left, right) if a["last"] < b["first"] else (right, left)
                candidates.append(
                    {
                        "first": first,
                        "second": second,
                        "shape": memories[left],
                        "saved_bits_if_aliased": memories[left]["width"] * memories[left]["depth"],
                    }
                )
    return {
        "schema": "calyx-memory-reuse-plan-v1",
        "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "memory_count": len(memories),
        "memories": memories,
        "intervals": intervals,
        "control_group_tokens": len(order),
        "same_shape_disjoint_candidates": candidates,
        "policy": "analysis-only; no aliasing without IR dependency proof",
    }


def apply_aliases(text: str, aliases: dict[str, str]) -> str:
    """Rewrite a validated alias map into Futil.

    ``aliases`` maps the removed memory name to its surviving canonical
    memory.  The caller, not this helper, is responsible for proving that the
    ranges do not overlap and that both memories are hardware-owned scratch.
    """
    if not aliases:
        return text
    names = {match.group(1) for match in DECL_RE.finditer(text)}
    for removed, canonical in aliases.items():
        if removed not in names or canonical not in names:
            raise ValueError(f"alias references unknown memory: {removed}->{canonical}")
        if removed == canonical:
            raise ValueError("memory cannot alias itself")
    if len(set(aliases)) != len(aliases):
        raise ValueError("alias map contains duplicate removed memories")
    # Never chain aliases: this keeps the resulting source and provenance
    # deterministic and makes accidental cycles fail closed.
    if set(aliases) & set(aliases.values()):
        raise ValueError("alias map must point directly to surviving memories")
    rewritten = text
    for removed, canonical in sorted(aliases.items()):
        rewritten = re.sub(
            rf"\s*@external(?:\([^)]*\))?\s+{re.escape(removed)}\s*=\s*seq_mem_d1\([^;]+;\n",
            "\n",
            rewritten,
            count=1,
        )
        if re.search(rf"\b{re.escape(removed)}\b", rewritten) is None:
            raise ValueError(f"memory declaration not found: {removed}")
        rewritten = re.sub(rf"\b{re.escape(removed)}\b", canonical, rewritten)
    return rewritten


def conservative_scratch_aliases(text: str, protected: set[str]) -> dict[str, str]:
    """Return a deterministic, non-chaining alias map for scratch memories.

    The interval test is intentionally conservative and lexical.  ``protected``
    must contain every model-owned memory; callers must still validate the
    resulting IR and semantics before accepting the map.
    """
    result = plan(text)
    memories = result["memories"]
    intervals = result["intervals"]
    by_shape: dict[tuple[int, int], list[str]] = {}
    for name, shape in memories.items():
        if name in protected or name not in intervals:
            continue
        by_shape.setdefault((shape["width"], shape["depth"]), []).append(name)
    aliases: dict[str, str] = {}
    for shape, names in sorted(by_shape.items()):
        slots: list[tuple[str, int]] = []
        for name in sorted(names, key=lambda n: (intervals[n]["first"], n)):
            first = intervals[name]["first"]
            reusable = next((i for i, (_, last) in enumerate(slots) if last < first), None)
            if reusable is None:
                slots.append((name, intervals[name]["last"]))
            else:
                canonical, _ = slots[reusable]
                aliases[name] = canonical
                slots[reusable] = (canonical, intervals[name]["last"])
    return aliases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("futil", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--apply-aliases", action="store_true")
    parser.add_argument("--protected", action="append", default=[])
    args = parser.parse_args()
    source = args.futil.read_text(encoding="utf-8")
    result = plan(source)
    if args.apply_aliases:
        aliases = conservative_scratch_aliases(source, set(args.protected))
        result["aliases"] = aliases
        result["rewritten_sha256"] = hashlib.sha256(apply_aliases(source, aliases).encode()).hexdigest()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
