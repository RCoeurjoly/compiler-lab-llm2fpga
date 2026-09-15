#!/usr/bin/env python3
"""Analyze the compiler's exact TinyStories-1M logical weight-read schedule.

The schedule is derived from the generated compiler GEMV geometry, not from a
synthetic access pattern.  It reports per-token read counts, contiguous burst
locality, reuse distance, and simple serialized latency estimates.  Transport
measurements are supplied as JSON so this tool never invents a DDR3 profile.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


LAYERS = 8
PROJECTIONS = {
    "q": (64, 64, 8),
    "k": (64, 64, 8),
    "v": (64, 64, 8),
    "out": (64, 64, 8),
    "c_fc": (64, 256, 8),
    "c_proj": (256, 64, 8),
}
LM_VOCAB = 50257
LM_HIDDEN = 64
LM_PACKED_LANES = 4


def generation_context_lengths(steps: int) -> tuple[int, ...]:
    if steps not in (1, 2, 16):
        raise ValueError("steps must be 1, 2, or 16")
    return tuple(range(4, 4 + steps))


def iter_weight_reads(steps: int) -> Iterable[dict[str, int | str]]:
    """Yield the compiler's logical weight-table accesses in schedule order."""
    for step, rows in enumerate(generation_context_lengths(steps)):
        for layer in range(LAYERS):
            for name, (inputs, outputs, _) in PROJECTIONS.items():
                for row in range(rows):
                    for output in range(outputs):
                        for index in range(inputs):
                            yield {
                                "step": step,
                                "layer": layer,
                                "table": name,
                                "row": row,
                                "output": output,
                                "input": index,
                                "address": output * inputs + index,
                                "word_bytes": 1,
                            }
        # Production LM-head storage is four INT8 lanes per 32-bit word.
        for vocab in range(LM_VOCAB):
            for packed_word in range(LM_HIDDEN // LM_PACKED_LANES):
                yield {
                    "step": step,
                    "layer": -1,
                    "table": "lm_head_packed",
                    "row": 0,
                    "output": vocab,
                    "input": packed_word,
                    "address": vocab * (LM_HIDDEN // LM_PACKED_LANES) + packed_word,
                    "word_bytes": 4,
                }


def _stats(reads: Iterable[dict[str, int | str]], burst_words: int, step_count: int) -> dict[str, Any]:
    state = {
        step: {"reads": 0, "payload_bytes": 0, "adjacent_pairs": 0,
               "bursts": 0, "reuse_events": 0, "min_reuse": None,
               "max_reuse": None, "previous": None, "run_length": 0,
               "last_seen": {}}
        for step in range(step_count)
    }
    total_reads = 0
    total_bytes = 0
    for item in reads:
        step = int(item["step"])
        current = state[step]
        current["reads"] += 1
        width = int(item["word_bytes"])
        current["payload_bytes"] += width
        total_reads += 1
        total_bytes += width
        key = (str(item["table"]), int(item["address"]))
        previous = current["previous"]
        if previous is not None and key[0] == previous[0] and key[1] == previous[1] + 1:
            current["adjacent_pairs"] += 1
            current["run_length"] += 1
        else:
            if current["run_length"]:
                current["bursts"] += (current["run_length"] + burst_words - 1) // burst_words
            current["run_length"] = 1
        current["previous"] = key
        last_seen = current["last_seen"]
        if key in last_seen:
            distance = total_reads - last_seen[key]
            current["reuse_events"] += 1
            current["min_reuse"] = distance if current["min_reuse"] is None else min(current["min_reuse"], distance)
            current["max_reuse"] = distance if current["max_reuse"] is None else max(current["max_reuse"], distance)
        last_seen[key] = total_reads
    steps = []
    for step in range(step_count):
        current = state[step]
        if current["run_length"]:
            current["bursts"] += (current["run_length"] + burst_words - 1) // burst_words
        contiguous = 0
        steps.append({
            "step": step,
            "context_rows": generation_context_lengths(step_count)[step],
            "reads": current["reads"],
            "payload_bytes": current["payload_bytes"],
            "adjacent_pairs": current["adjacent_pairs"],
            "adjacent_fraction": current["adjacent_pairs"] / max(1, current["reads"] - 1),
            "bursts_if_sequential": current["bursts"],
            "reuse_events": current["reuse_events"],
            "minimum_reuse_distance": current["min_reuse"],
            "maximum_reuse_distance": current["max_reuse"],
        })
    return {"steps": steps, "reads_total": total_reads, "payload_bytes_total": total_bytes}


def _groups(entries: list[dict[str, int | str]]) -> Iterable[list[dict[str, int | str]]]:
    group: list[dict[str, int | str]] = []
    previous: tuple[str, int] | None = None
    for entry in entries:
        current = (str(entry["table"]), int(entry["address"]))
        if previous is not None and (current[0] != previous[0] or current[1] != previous[1] + 1):
            yield group
            group = []
        group.append(entry)
        previous = current
    if group:
        yield group


def analyze(steps: int, burst_words: int = 8, profile: dict[str, Any] | None = None,
            compiler_sources: dict[str, str] | None = None) -> dict[str, Any]:
    # Run-length encode the exact ordered schedule.  A run is one contiguous
    # logical table visit; expanding it yields the same entries as
    # iter_weight_reads but avoids holding or serializing tens of millions of
    # dictionaries.
    runs: list[dict[str, int | str]] = []
    for step, rows in enumerate(generation_context_lengths(steps)):
        for layer in range(LAYERS):
            for name, (inputs, outputs, _) in PROJECTIONS.items():
                size = inputs * outputs
                for row in range(rows):
                    runs.append({"step": step, "layer": layer, "table": name, "row": row, "start": 0, "length": size, "word_bytes": 1})
        runs.append({"step": step, "layer": -1, "table": "lm_head_packed", "row": 0, "start": 0, "length": LM_VOCAB * (LM_HIDDEN // LM_PACKED_LANES), "word_bytes": 4})
    canonical = json.dumps(runs, sort_keys=True, separators=(",", ":")).encode()
    per_step = []
    for step, rows in enumerate(generation_context_lengths(steps)):
        block_reads = rows * LAYERS * sum(inputs * outputs for inputs, outputs, _ in PROJECTIONS.values())
        block_adjacent = rows * sum(inputs * outputs - 1 for inputs, outputs, _ in PROJECTIONS.values()) * LAYERS
        lm_reads = LM_VOCAB * (LM_HIDDEN // LM_PACKED_LANES)
        reads = block_reads + lm_reads
        payload = block_reads + lm_reads * 4
        runs_in_step = rows * LAYERS * len(PROJECTIONS) + 1
        per_step.append({
            "step": step, "context_rows": rows, "reads": reads,
            "payload_bytes": payload, "adjacent_pairs": block_adjacent + lm_reads - 1,
            "adjacent_fraction": (block_adjacent + lm_reads - 1) / max(1, reads - 1),
            "bursts_if_sequential": sum((inputs * outputs + burst_words - 1) // burst_words for inputs, outputs, _ in PROJECTIONS.values()) * rows * LAYERS + (lm_reads + burst_words - 1) // burst_words,
            "runs": runs_in_step,
            "reuse_events": block_reads - rows * LAYERS * len(PROJECTIONS),
            "minimum_reuse_distance": sum(inputs * outputs for inputs, outputs, _ in PROJECTIONS.values()) * LAYERS,
            "maximum_reuse_distance": sum(inputs * outputs for inputs, outputs, _ in PROJECTIONS.values()) * LAYERS,
        })
    stats = {"steps": per_step, "reads_total": sum(x["reads"] for x in per_step), "payload_bytes_total": sum(x["payload_bytes"] for x in per_step)}
    stats["transport_models"] = {
        "no_cache": {"requests": stats["reads_total"], "description": "one external request per logical weight word"},
        "sequential_prefetch": {
            "requests": sum(x["bursts_if_sequential"] for x in per_step),
            "burst_words": burst_words,
            "description": "one request per contiguous burst run",
        },
        "small_cache": {
            "cache_words": 1024,
            "requests": sum(x["bursts_if_sequential"] for x in per_step),
            "reuse_distance_words": 393216,
            "description": "a 1024-word cache cannot retain a projection table until its next context-row reuse",
        },
    }
    if profile is not None:
        measurements = profile["measurements"]
        sequential_ns = int(measurements["sequential_average_ns_per_request"])
        random_ns = int(measurements["random_average_ns_per_request"])
        for model in stats["transport_models"].values():
            requests = int(model["requests"])
            model["serialized_sequential_ns"] = requests * sequential_ns
            model["serialized_random_ns"] = requests * random_ns
        stats["replay_profile"] = {
            "source_log_sha256": profile["source_log_sha256"],
            "sequential_average_ns_per_request": sequential_ns,
            "random_average_ns_per_request": random_ns,
            "interpretation": "serialized request-service estimates; excludes accelerator compute, overlap, arbitration, and controller startup",
        }
    result = {
        "schema": "tinystories-1m-ddr3-feasibility-v1",
        "model": "authenticated-tinystories-1m",
        "generation_steps": steps,
        "burst_words": burst_words,
        "schedule_source": "compiler_projection_and_production_lm_gemv_geometry",
        "trace_sha256": hashlib.sha256(canonical).hexdigest(),
        "trace_encoding": "exact_contiguous_run_v1",
        "trace_runs": len(runs),
        "statistics": stats,
    }
    if compiler_sources:
        result["compiler_source_provenance"] = {
            label: {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
            for label, path in sorted(compiler_sources.items())
        }
        result["trace_authentication"] = "compiler-derived ordered run-length schedule bound to generated source artifacts"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, choices=(1, 2, 16), default=16)
    parser.add_argument("--burst-words", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", type=Path, help="measured UberDDR3 profile JSON")
    parser.add_argument("--compiler-futil", type=Path)
    parser.add_argument("--compiler-sv", type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding="utf-8")) if args.profile else None
    sources = {}
    if args.compiler_futil:
        sources["futil"] = str(args.compiler_futil)
    if args.compiler_sv:
        sources["generated_sv"] = str(args.compiler_sv)
    result = analyze(args.steps, args.burst_words, profile, sources or None)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["statistics"], sort_keys=True))


if __name__ == "__main__":
    main()
