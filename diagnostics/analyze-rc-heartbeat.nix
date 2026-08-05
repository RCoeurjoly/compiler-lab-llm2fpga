{ pkgs
, heartbeat
}:

pkgs.runCommand "tinystories-w8a8-rc-heartbeat-analysis" {
  nativeBuildInputs = [ pkgs.python3 ];
} ''
  mkdir -p "$out"
  ${pkgs.python3}/bin/python3 - "${heartbeat}/heartbeat.log" "$out/analysis.json" <<'PY'
import json, re, sys
from collections import Counter, defaultdict

source, destination = sys.argv[1:]
pattern = re.compile(
    r"HEARTBEAT (?P<case>\S+) cycles=(?P<cycles>\d+) "
    r"state=(?P<state>\d+) inner_state=(?P<inner>\d+) .*?"
    r"done=(?P<done>\d+) requests=(?P<requests>\d+) "
    r"mem_completions=(?P<completions>\d+) "
    r"output_writes=(?P<outputs>\d+)"
)
samples = []
with open(source, encoding="utf-8", errors="replace") as stream:
    for line in stream:
        match = pattern.search(line)
        if match:
            row = {key: int(value) if key not in ("case",) else value
                   for key, value in match.groupdict().items()}
            samples.append(row)

residency = Counter()
transitions = Counter()
no_memory_intervals = []
request_deltas = Counter()
completion_deltas = Counter()
for previous, current in zip(samples, samples[1:]):
    delta_cycles = current["cycles"] - previous["cycles"]
    delta_requests = current["requests"] - previous["requests"]
    delta_completions = current["completions"] - previous["completions"]
    residency[previous["state"]] += max(delta_cycles, 0)
    request_deltas[delta_requests] += 1
    completion_deltas[delta_completions] += 1
    if current["state"] != previous["state"]:
        transitions[(previous["state"], current["state"])] += 1
    if delta_cycles > 0 and delta_requests == 0:
        no_memory_intervals.append({
            "from_cycle": previous["cycles"],
            "to_cycle": current["cycles"],
            "cycles": delta_cycles,
            "from_state": previous["state"],
            "to_state": current["state"],
        })

last = samples[-1] if samples else None
result = {
    "sample_count": len(samples),
    "last_sample": last,
    "state_residency_cycles": {str(k): v for k, v in residency.items()},
    "top_states_by_residency": [list(item) for item in residency.most_common(20)],
    "state_transition_count": sum(transitions.values()),
    "top_transitions": [[list(edge), count] for edge, count in transitions.most_common(20)],
    "no_memory_intervals": no_memory_intervals,
    "no_memory_interval_count": len(no_memory_intervals),
    "request_delta_histogram": dict(request_deltas),
    "completion_delta_histogram": dict(completion_deltas),
}
with open(destination, "w", encoding="utf-8") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
''
