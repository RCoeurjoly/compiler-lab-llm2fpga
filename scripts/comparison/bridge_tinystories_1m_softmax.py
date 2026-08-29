#!/usr/bin/env python3
"""Bridge the authenticated TinyStories-1M attention softmax boundary.

This is deliberately a *boundary* bridge, not an RTL implementation.  It
accepts a package-aware SCF/MLIR textual artifact only when the artifact
contains the complete stabilized attention pattern (row-max subtraction,
exponential, reduction, normalization, and causal-prefix evidence).  The
result is a custom operation with the recovered kev-gpt arithmetic contract;
all hashes are carried into the IR and report.  A lone ``math.exp`` is never
enough to create a bridge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator, Mapping


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SHA256 = "a3158d9e07a121ddda599a9ad0c90e2f36438bed61aa36fc1889d221948ddbcf"
SOFTMAX_DIAGNOSTIC_SHA256 = "ef052961445168cc8e05b2522ce3cd05e11cd21235ab876907d6a4c6344a05ca"
CUSTOM_OP = "llm2fpga.attention_softmax_fixed"


class SoftmaxBridgeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise SoftmaxBridgeError(code, message)


_EVIDENCE_TOKEN = object()
_ISSUED_CAPABILITIES: set[int] = set()


class _EvidenceCapability(Mapping[str, Any]):
    """Opaque, mutation-detecting capability returned by ``load_evidence``."""

    def __init__(self, token: object, payload: Mapping[str, Any]) -> None:
        require(token is _EVIDENCE_TOKEN, "evidence_capability_required", "private construction token")
        self._payload = dict(payload)
        self._fingerprint = canonical_sha256(self._payload)
        self._token = _EVIDENCE_TOKEN

    def __getitem__(self, key: str) -> Any:
        return self._payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)

    def valid(self) -> bool:
        return self._token is _EVIDENCE_TOKEN and canonical_sha256(self._payload) == self._fingerprint


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise SoftmaxBridgeError("artifact_missing", f"{path}: {error}") from error


def canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise SoftmaxBridgeError("noncanonical_value", str(error)) from error
    return hashlib.sha256(encoded).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SoftmaxBridgeError("invalid_json", f"{label}: {error}") from error
    require(isinstance(value, dict), "invalid_json", f"{label} must be an object")
    return value


def load_evidence(contract_path: Path, diagnostic_path: Path) -> Mapping[str, Any]:
    """Authenticate the frozen model/package identity and recovered contract."""

    require(sha256_file(contract_path) == CONTRACT_SHA256, "contract_identity_mismatch", str(contract_path))
    require(sha256_file(diagnostic_path) == SOFTMAX_DIAGNOSTIC_SHA256, "diagnostic_identity_mismatch", str(diagnostic_path))
    contract = _load_json(contract_path, "contract")
    diagnostic = _load_json(diagnostic_path, "softmax diagnostic")
    require(contract.get("model", {}).get("name") == "TinyStories-1M", "contract_model_mismatch", "model name")
    require(contract.get("model", {}).get("source_revision") == "ac533fb8b4f69c71894bf96badfe11e6294d9fcf", "contract_model_mismatch", "source revision")
    package = contract.get("package")
    require(isinstance(package, dict), "contract_package_missing", "package")
    for key in ("manifest_sha256", "sha256"):
        require(isinstance(package.get(key), str) and len(package[key]) == 64, "contract_package_mismatch", key)
    reference = diagnostic.get("reference", {})
    recovered = reference.get("contract") if isinstance(reference, dict) else None
    require(isinstance(recovered, dict), "softmax_contract_missing", "diagnostic reference contract")
    expected = {
        "score": {"post_shift": 24, "output_encoding": "signed 32-bit fixed point with 8 fractional bits", "causal_mask": "implicit prefix time_index <= position; no mask port"},
        "exponential": {"lut_entries": 4096, "output_encoding": "unsigned 21-bit fixed point with 20 fractional bits (Q1.20)", "zero_delta_value": 1048576},
        "normalization": {"sum_bits": 64, "division": "unsigned restoring magnitude, sign reapplied; truncates toward zero"},
    }
    for section, fields in expected.items():
        actual = recovered.get(section)
        require(isinstance(actual, dict), "softmax_contract_mismatch", section)
        for key, value in fields.items():
            require(actual.get(key) == value, "softmax_contract_mismatch", f"{section}.{key}")
    capability = _EvidenceCapability(_EVIDENCE_TOKEN, {
        "contract_sha256": CONTRACT_SHA256,
        "diagnostic_sha256": SOFTMAX_DIAGNOSTIC_SHA256,
        "package_manifest_sha256": package["manifest_sha256"],
        "package_weights_sha256": package["sha256"],
        "package_scales_sha256": package.get("files", {}).get("scales.bin"),
        "package_calibration_ids_sha256": package.get("files", {}).get("calibration_ids.bin"),
        "model_revision": contract["model"]["source_revision"],
        "contract": recovered,
    })
    _ISSUED_CAPABILITIES.add(id(capability))
    return capability


def _named_pattern_evidence(graph: str, *, expected_exp_sites: int = 8) -> dict[str, Any]:
    """Require a complete, independently linked chain for every attention head.

    The package-aware export contains one attention softmax per head.  It is
    important that this check does not find the producer for one ``exp`` and
    the reduction for another: a textual graph-wide search would make such a
    malformed graph appear valid.  Each site is therefore bounded by its
    neighbouring ``math.exp`` operations and all of its SSA/memref edges are
    checked inside that interval.

    ``expected_exp_sites`` is explicit primarily for the small one-site unit
    fixture.  Production callers use the default eight-head contract; a
    single site is not silently accepted.
    """
    require(isinstance(expected_exp_sites, int) and not isinstance(expected_exp_sites, bool) and expected_exp_sites > 0,
            "pattern_not_proven", "expected_exp_sites must be a positive integer")

    # MLIR comments and attribute strings are not operation dataflow.  Match
    # only operation-shaped lines after removing comments; every SSA value is
    # then checked against the producer/consumer immediately below.
    lines = [re.sub(r"//.*$", "", line).strip() for line in graph.splitlines()]
    lines = [line for line in lines if line]
    require(lines and lines[0].startswith("module"), "pattern_not_proven", "MLIR module wrapper")
    require(graph.count("{") == graph.count("}"), "pattern_not_proven", "unbalanced MLIR regions")
    function_lines = [index for index, line in enumerate(lines) if re.match(r"func\.func\s+@[^\s(]+\(", line)]
    require(function_lines, "pattern_not_proven", "MLIR func.func wrapper")
    # Find the lexical function region containing the exp operation.  The
    # chain must not be stitched together from separate functions.
    function_spans: list[tuple[int, int]] = []
    for start in function_lines:
        depth = 0
        opened = False
        end = None
        for index in range(start, len(lines)):
            depth += lines[index].count("{") - lines[index].count("}")
            opened |= "{" in lines[index]
            if opened and depth == 0:
                end = index
                break
        require(end is not None, "pattern_not_proven", "unterminated func.func region")
        function_spans.append((start, end))
    executable = "\n".join(lines)
    exp_sites = list(re.finditer(r"^\s*%[A-Za-z0-9_.$-]+\s*=\s*math\.exp\b", executable, re.MULTILINE))
    require(exp_sites, "pattern_not_proven", "no executable math.exp operation")
    require(len(exp_sites) == expected_exp_sites, "pattern_not_proven",
            f"expected {expected_exp_sites} stabilized exp sites, found {len(exp_sites)}")
    exp_lines = [executable[:match.start()].count("\n") for match in exp_sites]
    site_evidence: list[dict[str, Any]] = []
    used_causal_lines: set[int] = set()
    for site_number, (exp_line, exp_match_obj) in enumerate(zip(exp_lines, exp_sites), start=1):
        containing = [span for span in function_spans if span[0] <= exp_line <= span[1]]
        require(len(containing) == 1, "pattern_not_proven", "math.exp is not in one function region")
        region_start, region_end = containing[0]
        previous_exp = exp_lines[site_number - 2] + 1 if site_number > 1 else region_start
        next_exp = exp_lines[site_number] if site_number < len(exp_lines) else region_end + 1
        # A chain may not borrow operations across another executable exp.
        chain_start, chain_end = max(previous_exp, region_start), min(next_exp, region_end + 1)
        require(chain_start < exp_line < chain_end, "pattern_not_proven", f"site {site_number} crosses function regions")
        exp_line_text = lines[exp_line]
        exp_match = re.match(r"%([^ ]+)\s*=\s*math\.exp\s+%([^ ]+)", exp_line_text)
        require(exp_match is not None, "pattern_not_proven", "malformed math.exp operation")
        exp_result, exp_input = exp_match.groups()

        def find(pattern: str, start: int = chain_start, end: int = chain_end) -> tuple[int, re.Match[str]]:
            for index in range(start, end):
                match = re.match(pattern, lines[index], re.IGNORECASE)
                if match:
                    return index, match
            raise SoftmaxBridgeError("dataflow_not_proven", pattern)

        sub_index, sub = find(r"%([^ ]+)\s*=\s*arith\.subf\s+%([^, ]+)\s*,\s*%([^ ]+)")
        delta = sub.group(1)
        require(sub.group(2).lower().startswith("score"), "dataflow_not_proven", f"site {site_number} lhs is not score")
        require("max" in sub.group(3).lower(), "dataflow_not_proven", f"site {site_number} rhs is not row max")
        store_delta_index, store_delta = find(r"memref\.store\s+%([^,]+),\s*%([^\[]+)\[([^\]]+)\]", sub_index + 1)
        require(store_delta.group(1) == delta, "dataflow_not_proven", f"site {site_number} stabilized delta is not stored")
        delta_load_index, delta_load = find(r"%([^ ]+)\s*=\s*memref\.load\s+%([^\[]+)\[([^\]]+)\]", store_delta_index + 1)
        require(delta_load.group(2) == store_delta.group(2) and delta_load.group(3) == store_delta.group(3), "dataflow_not_proven", f"site {site_number} delta load does not read delta store")
        require(delta_load.group(1) == exp_input, "dataflow_not_proven", f"site {site_number} math.exp does not consume loaded delta")
        require(store_delta_index < delta_load_index < exp_line, "dataflow_not_proven", f"site {site_number} delta producer/use ordering")
        exp_store_index, exp_store = find(r"memref\.store\s+%([^,]+),\s*%([^\[]+)\[([^\]]+)\]", exp_line + 1)
        require(exp_store.group(1) == exp_result, "dataflow_not_proven", f"site {site_number} exp result is not stored")
        exp_load_index, exp_load = find(r"%([^ ]+)\s*=\s*memref\.load\s+%([^\[]+)\[([^\]]+)\]", exp_store_index + 1)
        require(exp_load.group(2) == exp_store.group(2) and exp_load.group(3) == exp_store.group(3), "dataflow_not_proven", f"site {site_number} exp load does not read exp store")
        sum_index, sum_match = find(r"%([^ ]+)\s*=\s*arith\.addf\s+%([^, ]+)\s*,\s*%([^ ]+)", exp_load_index + 1)
        require(sum_match.group(3) == exp_load.group(1), "dataflow_not_proven", f"site {site_number} reduction does not consume loaded exp")
        sum_result = sum_match.group(1)
        div_index, div_match = find(r"%([^ ]+)\s*=\s*arith\.divf\s+%([^, ]+)\s*,\s*%([^ ]+)", sum_index + 1)
        require(div_match.group(2) == exp_load.group(1) and div_match.group(3) == sum_result, "dataflow_not_proven", f"site {site_number} normalization is not exp/sum")
        require(exp_line < exp_store_index < exp_load_index < sum_index < div_index, "dataflow_not_proven", f"site {site_number} producer/use ordering")
        causal = re.compile(r"^%[^ ]+\s*=\s*arith\.cmpi\s+(?:sle|ule),\s*%time_index(?:[_.$A-Za-z0-9-]*)?,\s*%position(?:[_.$A-Za-z0-9-]*)?(?:\s|:|$)", re.IGNORECASE)
        causal_candidates = [index for index in range(chain_start, chain_end) if causal.match(lines[index]) and index not in used_causal_lines]
        require(causal_candidates, "pattern_not_proven", f"site {site_number} lacks executable causal time_index <= position comparison")
        causal_index = causal_candidates[0]
        used_causal_lines.add(causal_index)
        site_evidence.append({"site": site_number, "exp_site_line": exp_line + 1, "causal_cmpi_line": causal_index + 1,
                              "matched_edges": ["subf_score_rowmax", "delta_store_load", "exp", "exp_store_load", "sum_reduction", "normalization_division", "causal_cmpi"]})
    return {"exp_site_count": len(site_evidence), "sites": site_evidence,
            "matched_edges": ["subf_score_rowmax", "delta_store_load", "exp", "exp_store_load", "sum_reduction", "normalization_division", "causal_cmpi"]}


def _lowered_pattern_evidence(graph: str, *, expected_exp_sites: int = 8) -> dict[str, Any]:
    """Recover the same chain after linalg lowering erased semantic names.

    The lowered graph has separate SCF loops, so an exp site's producer and
    consumer are not lexically adjacent.  Binding is still deliberately
    structural: the delta load/store, exp load/store, and reduction must use
    the same memref *and index expression*, and the score/max operands of the
    subtraction must each be loads in the same head component.  A global
    nearest-neighbour or name-only match is rejected.
    """
    lines = [re.sub(r"//.*$", "", line).strip() for line in graph.splitlines()]
    lines = [line for line in lines if line]
    require(lines and lines[0].startswith("module") and graph.count("{") == graph.count("}"),
            "pattern_not_proven", "MLIR module wrapper")
    require(sum(bool(re.match(r"func\.func\s+@[^\s(]+\(", line)) for line in lines) == 1,
            "pattern_not_proven", "MLIR func.func wrapper")
    function_start = next(i for i, line in enumerate(lines) if re.match(r"func\.func\s+@[^\s(]+\(", line))
    function_depth = 0
    function_end = None
    for i in range(function_start, len(lines)):
        function_depth += lines[i].count("{") - lines[i].count("}")
        if i > function_start and function_depth == 0:
            function_end = i
            break
    require(function_end is not None, "pattern_not_proven", "unterminated func.func region")
    require("scf.for" in graph or "scf.parallel" in graph, "pattern_not_proven", "lowered SCF loop structure")
    require(any(re.match(r"%fzero\s*=\s*arith\.constant\s+0\.0\s*:\s*f32", line) for line in lines),
            "pattern_not_proven", "authenticated floating zero constant")
    # Record lexical region ownership for every line.  This prevents a typed
    # value defined in a completed loop from being treated as a dominating
    # definition merely because its spelling is reused later.
    scope_paths: list[tuple[int, ...]] = []
    scope_stack: list[int] = []
    next_scope = 0
    for line in lines:
        opens, closes = line.count("{"), line.count("}")
        for _ in range(closes):
            if scope_stack:
                scope_stack.pop()
        # Close events precede open events on `} else {`; otherwise the else
        # branch inherits the then-branch's lexical scope.
        scope_paths.append(tuple(scope_stack))
        for _ in range(opens):
            next_scope += 1
            scope_stack.append(next_scope)
    exp_lines = [i for i, line in enumerate(lines) if re.match(r"%[^ ]+\s*=\s*math\.exp\s+%[^ ]+", line)]
    require(len(exp_lines) == expected_exp_sites, "pattern_not_proven",
            f"expected {expected_exp_sites} stabilized exp sites, found {len(exp_lines)}")

    load_re = re.compile(r"%([^ ]+)\s*=\s*memref\.load\s+%([^\[]+)\[([^\]]+)\]")
    store_re = re.compile(r"memref\.store\s+%([^,]+),\s*%([^\[]+)\[([^\]]+)\]")
    sub_re = re.compile(r"%([^ ]+)\s*=\s*arith\.subf\s+%([^, ]+)\s*,\s*%([^ ]+)")
    add_re = re.compile(r"%([^ ]+)\s*=\s*arith\.addf\s+%([^, ]+)\s*,\s*%([^ ]+)")
    div_re = re.compile(r"%([^ ]+)\s*=\s*arith\.divf\s+%([^, ]+)\s*,\s*%([^ ]+)")

    def loop_context(line_number: int) -> tuple[str, str, str, str] | None:
        """Return a normalized single-induction-loop signature for a line."""
        stack: list[tuple[int, tuple[str, str, str, str]]] = []
        loop_re = re.compile(r"scf\.(?:for|parallel)\s+%([^ ]+)\s*=\s*([^ ]+)\s+to\s+([^ ]+)(?:\s+step\s+([^ ]+))?")
        for i, line in enumerate(lines[:line_number + 1]):
            m = loop_re.search(line)
            if m:
                stack.append((line.count("{") - line.count("}"), (m.group(1), m.group(2), m.group(3), m.group(4) or "")))
            else:
                delta = line.count("{") - line.count("}")
                if delta < 0:
                    for _ in range(min(-delta, len(stack))):
                        stack.pop()
        return stack[-1][1] if stack else None

    def same_index(lhs: str, lhs_line: int, rhs: str, rhs_line: int) -> bool:
        if lhs == rhs:
            return True
        # Distinct SCF induction SSA values are equivalent only when both
        # accesses are the induction variable of structurally identical loops.
        lctx, rctx = loop_context(lhs_line), loop_context(rhs_line)
        return (lctx is not None and rctx is not None and
                lhs.lstrip("%") == lctx[0] and rhs.lstrip("%") == rctx[0] and lctx[1:] == rctx[1:])

    def defined_before(value: str, line_number: int) -> bool:
        name = value.lstrip("%")
        use_scope = scope_paths[line_number]
        for definition_line, line in enumerate(lines[function_start:line_number], function_start):
            if re.search(rf"scf\.(?:for|parallel)\s+%{re.escape(name)}\s*=", line):
                definition_scope = scope_paths[definition_line]
                # An induction variable is visible only in its loop body,
                # never in a sibling or after the loop closes.
                body_scope = (scope_paths[definition_line + 1][len(definition_scope)]
                              if definition_line + 1 < len(scope_paths) and
                              len(scope_paths[definition_line + 1]) > len(definition_scope)
                              else None)
                return (body_scope is not None and len(use_scope) > len(definition_scope) and
                        definition_scope == use_scope[:len(definition_scope)] and
                        use_scope[len(definition_scope)] == body_scope)
            if re.match(rf"%{re.escape(name)}\s*=", line):
                definition_scope = scope_paths[definition_line]
                return (definition_scope == use_scope[:len(definition_scope)] and
                        bool(re.search(r":\s*index(?:\s|$)", line)))
        return False

    def reduction_loop_header(line_number: int) -> tuple[str, int, int] | None:
        """Find the enclosing reduction loop header, without crossing a region."""
        depth = 0
        for i in range(line_number, -1, -1):
            depth += lines[i].count("}") - lines[i].count("{")
            if re.search(r"scf\.for\s+%[^ ]+\s*=", lines[i]) and depth <= 0:
                header = lines[i]
                region_depth = 0
                end = None
                for j in range(i, len(lines)):
                    region_depth += lines[j].count("{") - lines[j].count("}")
                    if j > i and region_depth == 0:
                        end = j
                        break
                return (header, i, end if end is not None else len(lines))
        return None
    sites = []
    used_causal: set[int] = set()
    used_exp_memrefs: set[str] = set()
    used_delta_memrefs: set[str] = set()
    used_sum_memrefs: set[str] = set()
    used_operand_memrefs: set[str] = set()
    for number, exp_i in enumerate(exp_lines, 1):
        exp_m = re.match(r"%([^ ]+)\s*=\s*math\.exp\s+%([^ ]+)", lines[exp_i])
        assert exp_m
        exp_result, exp_input = exp_m.groups()
        # The lowered exp input is a load from the delta buffer.  Requiring
        # this exact producer prevents another head's delta from being used.
        delta_loads = [(i, m) for i, line in enumerate(lines) if i < exp_i and (m := load_re.match(line)) and m.group(1) == exp_input]
        require(delta_loads, "dataflow_not_proven", f"site {number} exp input has no dominating memref.load")
        delta_load_i, delta_load = delta_loads[-1]
        delta_mem, delta_idx = delta_load.group(2).strip(), delta_load.group(3).strip()
        require(defined_before(delta_idx, delta_load_i), "dataflow_not_proven", f"site {number} delta index is undefined")
        require(function_start <= delta_load_i <= function_end, "dataflow_not_proven", f"site {number} delta load is outside function")
        require(delta_mem not in used_delta_memrefs, "dataflow_not_proven", f"site {number} reuses another head's delta memref")
        used_delta_memrefs.add(delta_mem)
        delta_stores = [(i, m) for i, line in enumerate(lines) if i < delta_load_i and (m := store_re.match(line)) and m.group(2).strip() == delta_mem and same_index(m.group(3).strip(), i, delta_idx, delta_load_i)]
        require(delta_stores, "dataflow_not_proven", f"site {number} delta load has no same-index store")
        delta_store_i, delta_store = delta_stores[-1]
        require(function_start <= delta_store_i <= function_end, "dataflow_not_proven", f"site {number} delta store is outside function")
        delta_value = delta_store.group(1).strip()
        sub_defs = [(i, m) for i, line in enumerate(lines) if i < delta_store_i and (m := sub_re.match(line)) and m.group(1) == delta_value]
        require(sub_defs, "dataflow_not_proven", f"site {number} delta store has no dominating arith.subf")
        sub_i, sub = sub_defs[-1]
        require(function_start <= sub_i <= function_end, "dataflow_not_proven", f"site {number} subtraction is outside function")
        # Both score and row-max must be values loaded in this component.  We
        # intentionally do not infer their meaning from SSA spelling.
        operand_loads = {}
        for operand in sub.groups()[1:]:
            candidates = [(i, m) for i, line in enumerate(lines) if i < sub_i and (m := load_re.match(line)) and m.group(1) == operand]
            require(candidates, "dataflow_not_proven", f"site {number} subtraction operand is not a loaded tensor value")
            operand_loads[operand] = candidates[-1][1]
            require(function_start <= candidates[-1][0] <= function_end, "dataflow_not_proven", f"site {number} operand load is outside function")
            require(same_index(candidates[-1][1].group(3).strip(), candidates[-1][0], delta_idx, delta_load_i),
                    "dataflow_not_proven", f"site {number} subtraction operand index does not match delta index")
        # The row-max operand must come from a full-domain loop-carried max,
        # not a constant or an unrelated buffer.
        max_operand = sub.group(3)
        max_load_candidates = [(i, m) for i, line in enumerate(lines) if i < sub_i and (m := load_re.match(line)) and m.group(1) == max_operand]
        require(max_load_candidates, "dataflow_not_proven", f"site {number} row-max operand is not loaded")
        max_mem = max_load_candidates[-1][1].group(2).strip()
        max_stores = [(i, m) for i, line in enumerate(lines) if i < max_load_candidates[-1][0] and (m := store_re.match(line)) and m.group(2).strip() == max_mem]
        require(max_stores, "dataflow_not_proven", f"site {number} row-max buffer has no producer")
        max_value = max_stores[-1][1].group(1).strip()
        max_header_i = next((i for i, line in enumerate(lines[:max_stores[-1][0]])
                             if re.match(rf"%{re.escape(max_value.lstrip('%'))}\s*=\s*scf\.for\b", line)), None)
        require(max_header_i is not None, "dataflow_not_proven", f"site {number} row-max has no matching loop result")
        max_header_info = reduction_loop_header(max_header_i)
        max_header = max_header_info[0] if max_header_info else None
        require(max_header is not None and "iter_args" in max_header,
                "dataflow_not_proven", f"site {number} row-max is not loop-carried")
        max_end = max_header_info[2]
        score_mem = operand_loads[sub.group(2)].group(2).strip()
        max_body = lines[max_header_i:max_end]
        carried_match = re.search(r"iter_args\(\s*%([^ ]+)\s*=", max_header)
        max_op = next((re.match(r"%([^ ]+)\s*=\s*arith\.maximumf\s+%([^, ]+)\s*,\s*%([^ ]+)", line)
                       for line in max_body if "arith.maximumf" in line), None)
        score_load_value = next((re.match(r"%([^ ]+)\s*=\s*memref\.load", line).group(1)
                                 for line in max_body if score_mem in line and re.match(r"%[^ ]+\s*=\s*memref\.load", line)), None)
        require(carried_match is not None and max_op is not None and
                carried_match.group(1) in max_op.groups()[1:] and
                score_load_value is not None and score_load_value in max_op.groups()[1:],
                "dataflow_not_proven", f"site {number} row-max is not a loop-carried reduction")
        require(any(re.match(rf"scf\.yield\s+%{re.escape(max_op.group(1))}", line) for line in max_body),
                "dataflow_not_proven", f"site {number} row-max result is not yielded")
        require(operand_loads[sub.group(2)].group(2).strip() != operand_loads[sub.group(3)].group(2).strip(),
                "dataflow_not_proven", f"site {number} score and row-max loads are not distinct")
        for operand in sub.groups()[1:]:
            resource = operand_loads[operand].group(2).strip()
            require(resource not in used_operand_memrefs, "dataflow_not_proven", f"site {number} reuses another head's operand memref")
            used_operand_memrefs.add(resource)
        # Exp store/load and normalization may occur in later loops.  Bind by
        # exact exp memref/index and SSA edges, never by proximity alone.
        exp_store_candidates = [(i, m) for i, line in enumerate(lines) if i > exp_i and (m := store_re.match(line)) and m.group(1).strip() == exp_result]
        require(exp_store_candidates, "dataflow_not_proven", f"site {number} exp result has no store")
        exp_store_i, exp_store = exp_store_candidates[0]
        exp_mem, exp_idx = exp_store.group(2).strip(), exp_store.group(3).strip()
        require(defined_before(exp_idx, exp_store_i), "dataflow_not_proven", f"site {number} exp index is undefined")
        exp_loop = loop_context(exp_store_i)
        require(exp_loop is not None and exp_idx.lstrip("%") == exp_loop[0],
                "dataflow_not_proven", f"site {number} exponential store is not indexed by its loop IV")
        require(function_start <= exp_store_i <= function_end, "dataflow_not_proven", f"site {number} exp store is outside function")
        require(exp_mem not in used_exp_memrefs, "dataflow_not_proven", f"site {number} reuses another head's exp memref")
        used_exp_memrefs.add(exp_mem)
        exp_load_candidates = [(i, m) for i, line in enumerate(lines) if i > exp_store_i and (m := load_re.match(line)) and m.group(2).strip() == exp_mem and same_index(m.group(3).strip(), i, exp_idx, exp_store_i)]
        require(exp_load_candidates, "dataflow_not_proven", f"site {number} exp store has no same-index load")
        # A later loop can reload the same exp element more than once.  Pick
        # only a complete load -> reduction -> division chain; never assume
        # that the first reload is the one consumed by normalization.
        complete = []
        for candidate_i, candidate in exp_load_candidates:
            candidate_value = candidate.group(1)
            adds = [(i, m) for i, line in enumerate(lines) if i > candidate_i and (m := add_re.match(line)) and candidate_value in (m.group(2), m.group(3))]
            for add_i_candidate, add_candidate in adds:
                sum_candidate = add_candidate.group(1)
                # The reduction result is materialized and reloaded before
                # division in the lowered graph.  Bind that reload to the
                # exact sum store/index, rather than trusting its SSA name.
                candidate_info = reduction_loop_header(add_i_candidate)
                candidate_header = candidate_info[0] if candidate_info else None
                result_match = re.match(r"%([^ ]+)\s*=\s*scf\.for\b", candidate_header or "")
                require(result_match is not None, "dataflow_not_proven", f"site {number} reduction has no SSA loop result")
                candidate_result = result_match.group(1)
                sum_stores = [(i, m) for i, line in enumerate(lines) if i > candidate_info[2] and (m := store_re.match(line)) and m.group(1).strip() == candidate_result]
                for sum_store_i, sum_store in sum_stores:
                    sum_mem, sum_idx = sum_store.group(2).strip(), sum_store.group(3).strip()
                    sum_loads = [(i, m) for i, line in enumerate(lines) if i > sum_store_i and (m := load_re.match(line)) and m.group(2).strip() == sum_mem and same_index(m.group(3).strip(), i, sum_idx, sum_store_i)]
                    for sum_load_i, sum_load in sum_loads:
                        exp_reload_values = {candidate_value}
                        exp_reload_values.update(m.group(1) for i, line in enumerate(lines) if i > sum_load_i and (m := load_re.match(line)) and m.group(2).strip() == exp_mem and same_index(m.group(3).strip(), i, exp_idx, exp_store_i))
                        divs = [(i, m) for i, line in enumerate(lines) if i > sum_load_i and (m := div_re.match(line)) and m.group(2) in exp_reload_values and m.group(3) == sum_load.group(1)]
                        if divs:
                            complete.append((candidate_i, candidate, add_i_candidate, add_candidate, divs[0]))
                            break
                    if complete:
                        break
                if complete:
                    break
        require(complete, "dataflow_not_proven", f"site {number} reduction/division does not consume a same-memref exp reload")
        exp_load_i, exp_load, add_i, add, div_entry = complete[0]
        require(all(function_start <= index <= function_end for index in (exp_load_i, add_i, div_entry[0])),
                "dataflow_not_proven", f"site {number} normalization escapes function")
        exp_loaded = exp_load.group(1)
        sum_value = add.group(1)
        # A single add followed by a store is not evidence of a row
        # reduction.  Require an explicit loop-carried accumulator; otherwise
        # fail closed rather than accepting a fake one-element reduction.
        reduction_info = reduction_loop_header(add_i)
        reduction_header = reduction_info[0] if reduction_info else None
        require(reduction_info is not None and "iter_args" in reduction_header,
                "dataflow_not_proven", f"site {number} reduction is not loop-carried")
        result_match = re.match(r"%([^ ]+)\s*=\s*scf\.for\b", reduction_header)
        require(result_match is not None, "dataflow_not_proven", f"site {number} reduction has no SSA loop result")
        carried_match = re.search(r"iter_args\(\s*%([^ ]+)\s*=", reduction_header)
        require(carried_match is not None, "dataflow_not_proven", f"site {number} reduction carried value is malformed")
        carried = carried_match.group(1)
        add_operands = add.groups()[1:]
        require(any(operand.lstrip("%") == carried for operand in add_operands),
                "dataflow_not_proven", f"site {number} reduction add does not consume carried accumulator")
        _, reduction_start, reduction_end = reduction_info
        yield_found = any(re.match(rf"scf\.yield\s+%{re.escape(sum_value)}(?:\s|:|$)", line)
                          for line in lines[add_i + 1:reduction_end])
        require(yield_found, "dataflow_not_proven", f"site {number} reduction has no matching scf.yield")
        # A reduction is complete only when its accumulator is materialized
        # into a unique sum buffer and subsequently reloaded for division.
        reduction_result = result_match.group(1)
        sum_store_matches = [(i, m) for i, line in enumerate(lines) if i > reduction_info[2] and (m := store_re.match(line)) and m.group(1).strip() == reduction_result]
        require(sum_store_matches, "dataflow_not_proven", f"site {number} reduction result is not materialized")
        sum_mem_for_site = sum_store_matches[0][1].group(2).strip()
        require(defined_before(sum_store_matches[0][1].group(3).strip(), sum_store_matches[0][0]), "dataflow_not_proven", f"site {number} sum index is undefined")
        sum_loop = loop_context(sum_store_matches[0][0])
        require(sum_loop is not None and sum_store_matches[0][1].group(3).strip().lstrip("%") == sum_loop[0],
                "dataflow_not_proven", f"site {number} sum store is not indexed by its loop IV")
        require(function_start <= sum_store_matches[0][0] <= function_end, "dataflow_not_proven", f"site {number} sum store is outside function")
        require(sum_mem_for_site not in used_sum_memrefs, "dataflow_not_proven", f"site {number} reuses another head's sum memref")
        used_sum_memrefs.add(sum_mem_for_site)
        div_candidates = [div_entry]
        head_digits = "".join(re.findall(r"\d+", exp_mem))
        causal = []
        causal_re = re.compile(r"%[^ ]+\s*=\s*arith\.cmpi\s+(?:sle|ule),\s*(%[^, ]+),\s*(%[^ ]+)")
        for i, line in enumerate(lines):
            match = causal_re.match(line)
            if (i not in used_causal and function_start <= i <= function_end and match and
                    (loop_context(i) is not None and match.group(1).lstrip("%") == loop_context(i)[0]) and
                    match.group(2).lower().startswith("%position") and
                    (not head_digits or head_digits in line)):
                causal.append(i)
        require(causal, "pattern_not_proven", f"site {number} lacks executable causal comparison")
        causal_result = re.match(r"%([^ ]+)", lines[causal[0]]).group(1)
        require(any(re.search(rf"arith\.select\s+%{re.escape(causal_result)}\b", line)
                    and ("exp" in line or "prob" in line)
                    for line in lines[causal[0] + 1:function_end + 1]),
                "dataflow_not_proven", f"site {number} causal comparison result is unused")
        select_line = next(line for line in lines[causal[0] + 1:function_end + 1]
                           if re.search(rf"arith\.select\s+%{re.escape(causal_result)}\b", line))
        select_match = re.search(r"arith\.select\s+%[^, ]+,\s*%([^, ]+),\s*%([^ ]+)", select_line)
        div_result = div_entry[1].group(1)
        require(select_match is not None and select_match.group(1) == div_result and select_match.group(2) == "fzero",
                "dataflow_not_proven", f"site {number} causal select has no observable alternative")
        select_result = re.match(r"%([^ ]+)", select_line).group(1)
        require(any(re.search(rf"memref\.store\s+%{re.escape(select_result)}\b", line)
                    for line in lines[causal[0] + 1:function_end + 1]),
                "dataflow_not_proven", f"site {number} masked probability is not observable")
        output_store = next(line for line in lines[causal[0] + 1:function_end + 1]
                            if re.search(rf"memref\.store\s+%{re.escape(select_result)}\b", line))
        output_match = store_re.match(output_store)
        require(output_match is not None and output_match.group(2).strip() == score_mem and
                output_match.group(3).strip().lstrip("%") == loop_context(causal[0])[0],
                "dataflow_not_proven", f"site {number} masked output is not head-local")
        used_causal.add(causal[0])
        sites.append({"site": number, "exp_site_line": exp_i + 1, "causal_cmpi_line": causal[0] + 1,
                      "matched_edges": ["subf_operand_loads", "delta_store_load_same_index", "exp", "exp_store_load_same_index", "sum_reduction", "normalization_division", "causal_cmpi"]})
    return {"exp_site_count": len(sites), "sites": sites,
            "binding_mode": "lowered_memref_loop_structure",
            "matched_edges": ["subf_operand_loads", "delta_store_load_same_index", "exp", "exp_store_load_same_index", "sum_reduction", "normalization_division", "causal_cmpi"]}


def _pattern_evidence(graph: str, *, expected_exp_sites: int = 8) -> dict[str, Any]:
    try:
        return _named_pattern_evidence(graph, expected_exp_sites=expected_exp_sites)
    except SoftmaxBridgeError as named_error:
        # Only lowered SCF graphs are eligible for the structural recovery;
        # ordinary malformed fixtures retain the precise original diagnostic.
        if "scf.for" not in graph and "scf.parallel" not in graph:
            raise
        try:
            return _lowered_pattern_evidence(graph, expected_exp_sites=expected_exp_sites)
        except SoftmaxBridgeError:
            raise named_error


def bridge_graph(graph: str, evidence: Mapping[str, Any], *, source_name: str, expected_exp_sites: int = 8) -> dict[str, Any]:
    require(isinstance(graph, str) and graph, "graph_missing", source_name)
    require(isinstance(evidence, _EvidenceCapability), "evidence_capability_required", "use load_evidence result")
    require(id(evidence) in _ISSUED_CAPABILITIES, "evidence_capability_unissued", "capability was not issued by load_evidence")
    require(evidence.valid(), "evidence_capability_invalidated", "evidence changed after authentication")
    canonical = {
        "contract_sha256": CONTRACT_SHA256,
        "diagnostic_sha256": SOFTMAX_DIAGNOSTIC_SHA256,
        "package_manifest_sha256": "374171e8c0a06dc2632434965f218cf2fc6c82ee15470c47a958b6b9f5f6ca35",
        "package_weights_sha256": "caa140a70f824334d626e20819effabb3a56c28f35cc5c84e6f5f174b3f6bf4e",
        "package_scales_sha256": "a81faadf9ab21a525a8a20870f2fa97572c66bbf6b88c5cbe2a29cd253355155",
        "package_calibration_ids_sha256": "2537125a6edea656c5f6b8fe537b4cec7f2a3b2f633f5ee36297135e705bb075",
        "model_revision": "ac533fb8b4f69c71894bf96badfe11e6294d9fcf",
        "contract": evidence["contract"],
    }
    require(dict(evidence) == canonical, "evidence_payload_mismatch", "canonical contract/package evidence")
    pattern = _pattern_evidence(graph, expected_exp_sites=expected_exp_sites)
    attributes = {
        "score_width": 32,
        "score_fraction_bits": 8,
        "score_post_shift": 24,
        "causal_mask": "prefix_time_index_le_position",
        "exp_lut_entries": 4096,
        "exp_width": 21,
        "exp_fraction_bits": 20,
        "exp_zero_delta_value": 1048576,
        "sum_width": 64,
        "normalization": "unsigned_restoring_magnitude_signed_reapply",
        "division_rounding": "truncation_toward_zero",
    }
    descriptor = {
        "schema": "llm2fpga-tinystories-1m-softmax-op-v1",
        "op": CUSTOM_OP,
        "operand_types": ["tensor<16x32xi32>", "i32"],
        "result_types": ["tensor<16x32xi32>"],
        "attributes": attributes,
        "source": {"artifact": source_name, "sha256": hashlib.sha256(graph.encode()).hexdigest(), **pattern},
        "evidence": {key: evidence[key] for key in ("contract_sha256", "diagnostic_sha256", "package_manifest_sha256", "package_weights_sha256", "package_scales_sha256", "package_calibration_ids_sha256", "model_revision")},
    }
    descriptor["sha256"] = canonical_sha256({key: value for key, value in descriptor.items() if key != "sha256"})
    return descriptor


def render_custom_op(descriptor: Mapping[str, Any]) -> str:
    require(descriptor.get("op") == CUSTOM_OP, "descriptor_mismatch", "operation")
    require(descriptor.get("sha256") == canonical_sha256({key: value for key, value in descriptor.items() if key != "sha256"}), "descriptor_hash_mismatch", "descriptor")
    attrs = descriptor["attributes"]
    manifest = ", ".join(f'{key} = "{value}"' for key, value in descriptor["evidence"].items())
    rendered_attrs = ", ".join(
        f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value} : i64"
        for key, value in attrs.items()
    )
    return (
        f"module attributes {{llm2fpga.bridge_manifest = {{{manifest}}}}} {{\n"
        "  func.func @tinystories_1m_attention_softmax(%scores: tensor<16x32xi32>, %position: i32) -> tensor<16x32xi32> {\n"
        f'    %0 = "{CUSTOM_OP}"(%scores, %position) <{{{rendered_attrs}}}> : (tensor<16x32xi32>, i32) -> tensor<16x32xi32>\n'
        "    return %0 : tensor<16x32xi32>\n  }\n}\n"
    )


def make_report(descriptor: Mapping[str, Any], graph: str, mlir: str) -> dict[str, Any]:
    require(mlir == render_custom_op(descriptor), "rendered_mlir_mismatch", "custom operation")
    return {
        "schema": "tinystories-1m-softmax-compiler-bridge-v1",
        "model": "TinyStories-1M",
        "status": "unsupported",
        "alignment_status": "custom_op_emitted_backend_unverified",
        "board_authenticated": False,
        "source": descriptor["source"],
        "custom_op": dict(descriptor),
        "compiler_artifacts": {"mlir": {"kind": "custom_op_ir", "sha256": hashlib.sha256(mlir.encode()).hexdigest()}, "systemverilog": None, "rtlil": None},
        "first_unsupported_operation": {"target": CUSTOM_OP, "code": "softmax_backend_lowering_not_implemented", "pipeline_stage": "custom_op_to_linalg_or_calyx", "reason": "the exact stabilized softmax boundary is authenticated, but no backend legalization or execution is claimed"},
        "claims": {"functional_equivalence": False, "rtl_equivalence": False, "timing_closure": False, "hardware_inference": False, "reference_source_or_rtl_copied": False},
        "provenance": {"reference_role": "content_authenticated_behavioral_oracle_only", "llm_assistance_disclosure_required": True},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--diagnostic", required=True, type=Path)
    parser.add_argument("--mlir-out", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    graph = args.graph.read_text(encoding="utf-8")
    evidence = load_evidence(args.contract, args.diagnostic)
    descriptor = bridge_graph(graph, evidence, source_name=str(args.graph))
    mlir = render_custom_op(descriptor)
    report = make_report(descriptor, graph, mlir)
    report["sha256"] = canonical_sha256({key: value for key, value in report.items() if key != "sha256"})
    args.mlir_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.mlir_out.write_text(mlir, encoding="utf-8")
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
