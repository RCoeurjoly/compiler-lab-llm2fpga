#!/usr/bin/env python3
"""Filter whole RTLIL module definitions."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


MODULE_RE = re.compile(r"^module[ \t]+(\S+)")
ATTRIBUTE_RE = re.compile(r"^attribute(?:[ \t]|$)")
CELL_RE = re.compile(r"^[ \t]*cell[ \t]+(\S+)")
BLOCK_START_RE = re.compile(r"^[ \t]*(?:cell|process|switch)(?:[ \t]|$)")


@dataclass(frozen=True)
class ModuleDefinition:
    name: str
    lines: list[str]
    dependencies: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input RTLIL file.")
    parser.add_argument("--output", required=True, help="Output RTLIL file.")
    parser.add_argument(
        "--drop-escaped-uppercase-modules",
        action="store_true",
        help="Drop module definitions whose RTLIL name starts with a backslash followed by an uppercase letter.",
    )
    parser.add_argument(
        "--keep-reachable-from",
        metavar="TOP",
        help="Keep only the module dependency closure reachable from TOP.",
    )
    return parser.parse_args()


def normalize_module_name(name: str) -> str:
    return name[1:] if name.startswith("\\") else name


def parse_modules(
    lines: list[str],
) -> tuple[list[str], list[ModuleDefinition], list[list[str]]]:
    """Split RTLIL into its preamble, modules, and top-level separators."""
    preamble: list[str] = []
    modules: list[ModuleDefinition] = []
    separators: list[list[str]] = []
    pending: list[str] = []
    index = 0

    while index < len(lines):
        module_match = MODULE_RE.match(lines[index])
        if module_match is None:
            pending.append(lines[index])
            index += 1
            continue

        attribute_start = len(pending)
        while attribute_start and ATTRIBUTE_RE.match(pending[attribute_start - 1]):
            attribute_start -= 1
        if modules:
            separators.append(pending[:attribute_start])
        else:
            preamble.extend(pending[:attribute_start])
        leading_lines = pending[attribute_start:]
        pending = []

        module_lines = leading_lines + [lines[index]]
        dependencies: list[str] = []
        depth = 1
        index += 1
        while index < len(lines):
            line = lines[index]
            module_lines.append(line)
            cell_match = CELL_RE.match(line)
            if cell_match is not None:
                dependencies.append(cell_match.group(1))
            if BLOCK_START_RE.match(line):
                depth += 1
            if line.strip() == "end":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        else:
            raise SystemExit(
                f"filter_rtlil_modules.py: unterminated module {module_match.group(1)}"
            )

        modules.append(
            ModuleDefinition(
                name=module_match.group(1),
                lines=module_lines,
                dependencies=tuple(dependencies),
            )
        )
        index += 1

    if modules:
        separators.append(pending)
    elif pending:
        preamble.extend(pending)
    return preamble, modules, separators


def select_reachable_modules(
    modules: list[ModuleDefinition], top_name: str
) -> set[str]:
    modules_by_name = {normalize_module_name(module.name): module for module in modules}
    if len(modules_by_name) != len(modules):
        raise SystemExit("filter_rtlil_modules.py: duplicate normalized module name")

    normalized_top_name = normalize_module_name(top_name)
    if normalized_top_name not in modules_by_name:
        raise SystemExit(
            "filter_rtlil_modules.py: "
            f"top module {top_name!r} is not defined in the input RTLIL"
        )

    selected: set[str] = set()
    pending = [normalized_top_name]
    while pending:
        module_name = pending.pop()
        if module_name in selected:
            continue
        selected.add(module_name)
        for dependency in modules_by_name[module_name].dependencies:
            normalized_dependency = normalize_module_name(dependency)
            if normalized_dependency in modules_by_name:
                pending.append(normalized_dependency)
    return selected


def write_modules(
    output_path: Path,
    preamble: list[str],
    modules: list[ModuleDefinition],
    separators: list[list[str]],
    selected: set[str],
) -> None:
    with output_path.open("w", encoding="utf-8") as dst:
        dst.writelines(preamble)
        for index, module in enumerate(modules):
            if normalize_module_name(module.name) in selected:
                dst.writelines(module.lines)
            dst.writelines(separators[index])


def main() -> None:
    args = parse_args()
    mode_count = int(args.drop_escaped_uppercase_modules) + int(
        args.keep_reachable_from is not None
    )
    if mode_count != 1:
        raise SystemExit(
            "filter_rtlil_modules.py requires exactly one mode: "
            "--drop-escaped-uppercase-modules or --keep-reachable-from TOP"
        )

    input_path = Path(args.input)
    output_path = Path(args.output)
    lines = input_path.read_text(encoding="utf-8", errors="ignore").splitlines(
        keepends=True
    )
    preamble, modules, separators = parse_modules(lines)

    if args.drop_escaped_uppercase_modules:
        selected = {
            normalize_module_name(module.name)
            for module in modules
            if not (
                module.name.startswith("\\")
                and len(module.name) > 1
                and module.name[1].isupper()
            )
        }
    else:
        selected = select_reachable_modules(modules, args.keep_reachable_from)

    write_modules(output_path, preamble, modules, separators, selected)


if __name__ == "__main__":
    main()
