#!/usr/bin/env python3
"""Cache-first, credential-free metadata retrieval for the survey audit."""

from __future__ import annotations

import csv
import fcntl
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, quote, unquote, urlsplit, urlunsplit

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = ROOT / "survey/build/api-cache"
DEFAULT_LOG_PATH = ROOT / "survey/build/api_retrieval_log.csv"
SECRET_QUERY_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "email",
    "key",
    "private_token",
    "token",
}
ALLOWED_SERVICES = {
    "arxiv",
    "crossref",
    "github",
    "openalex",
    "unpaywall",
    "zenodo",
}
SERVICE_ENDPOINTS = {
    "arxiv": (
        ("export.arxiv.org", re.compile(r"^/api/query$"), {"id_list"}),
        ("arxiv.org", re.compile(r"^/pdf/[0-9.]+v[0-9]+$"), set()),
    ),
    "crossref": (
        ("api.crossref.org", re.compile(r"^/works/[^/]+$"), set()),
    ),
    "github": (
        (
            "api.github.com",
            re.compile(
                r"^/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
                r"(?:/(?:commits/[^/]+|git/trees/[^/]+|releases|license|readme))?$"
            ),
            {"per_page", "recursive", "ref"},
        ),
    ),
    "openalex": (
        ("api.openalex.org", re.compile(r"^/works/https://doi\.org/.+$"), set()),
    ),
    "unpaywall": (
        ("api.unpaywall.org", re.compile(r"^/v2/[^/]+$"), set()),
    ),
    "zenodo": (
        ("zenodo.org", re.compile(r"^/api/records/[0-9]+$"), set()),
    ),
}
SENSITIVE_NAME = re.compile(
    r"(?i)(?:auth|bearer|credential|email|key|pass(?:word)?|secret|sig(?:nature)?|token)"
)
EMAIL_LIKE = re.compile(r"(?i)(?:^|[^A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:$|[^A-Za-z])")
SENSITIVE_VALUE = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:auth|credential|key|pass(?:word)?|secret|token)\s*[:=]\s*\S+|"
    r"gh[pousr]_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{12,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.)"
)


@dataclass(frozen=True)
class CacheEntry:
    service: str
    identifier: str
    request_url: str
    raw_response_path: str
    http_status: int
    retrieved_at_utc: str
    response_sha256: str
    error_body_sha256: str
    body: bytes
    from_cache: bool


class MalformedResponseError(ValueError):
    """A successful HTTP receipt whose body cannot satisfy its JSON contract."""


LOG_FIELDS = [
    "service",
    "identifier",
    "request_url",
    "raw_response_path",
    "http_status",
    "retrieved_at_utc",
    "response_sha256",
    "error_body_sha256",
    "failure_code",
]
INDEX_ENTRY_FIELDS = set(LOG_FIELDS) - {"failure_code"}


def retrieval_failure_code(status: int) -> str:
    if status == 0:
        return "REQUEST_ERROR"
    if 200 <= status < 400:
        return "NONE"
    if status in {403, 429}:
        return "RATE_LIMITED_OR_FORBIDDEN"
    if status == 404:
        return "NOT_FOUND"
    if status == 422:
        return "INVALID_IDENTIFIER_OR_REF"
    if status >= 500:
        return "SERVICE_ERROR"
    return "HTTP_ERROR"


def _cache_root() -> Path:
    return Path(os.environ.get("SURVEY_API_CACHE_ROOT", DEFAULT_CACHE_ROOT))


def _index_path() -> Path:
    return _cache_root() / "index.json"


def _validate_request(service: str, identifier: str, url: str) -> None:
    if service not in ALLOWED_SERVICES:
        raise ValueError(f"unsupported API service: {service}")
    if not identifier.strip():
        raise ValueError("API requests require a stable identifier")
    if EMAIL_LIKE.search(identifier) or SENSITIVE_VALUE.search(identifier):
        raise ValueError("API request identifier contains sensitive material")
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("request URL must be credential-free HTTPS")
    endpoint = next(
        (
            (path_pattern, allowed_queries)
            for hostname, path_pattern, allowed_queries in SERVICE_ENDPOINTS[service]
            if parsed.hostname.lower() == hostname
        ),
        None,
    )
    if endpoint is None or not endpoint[0].fullmatch(parsed.path):
        raise ValueError(f"request URL does not match documented {service} endpoints")
    allowed_queries = endpoint[1]
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query_names = [name.lower() for name, _ in query_items]
    if len(query_names) != len(set(query_names)):
        raise ValueError("request URL contains duplicate query fields")
    expected_queries = set()
    if service == "arxiv" and parsed.hostname.lower() == "export.arxiv.org":
        expected_queries = {"id_list"}
    elif service == "github":
        if "/git/trees/" in parsed.path:
            expected_queries = {"recursive"}
        elif parsed.path.endswith("/releases"):
            expected_queries = {"per_page"}
        elif parsed.path.endswith(("/license", "/readme")):
            expected_queries = {"ref"}
    if set(query_names) != expected_queries:
        raise ValueError(f"request URL query does not match documented {service} endpoint")
    for name, value in query_items:
        lowered = name.lower()
        if lowered not in allowed_queries or SENSITIVE_NAME.search(lowered):
            raise ValueError(f"request URL contains forbidden query field: {lowered}")
        decoded = unquote(value)
        if EMAIL_LIKE.search(decoded) or SENSITIVE_VALUE.search(decoded):
            raise ValueError("request URL query contains sensitive material")


def _load_index(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "entries": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        set(value) != {"schema_version", "entries"}
        or value.get("schema_version") != 1
        or not isinstance(value.get("entries"), list)
    ):
        raise ValueError("API cache index has unsupported schema")
    seen: set[tuple[str, str, str]] = set()
    for entry in value["entries"]:
        if not isinstance(entry, dict) or set(entry) != INDEX_ENTRY_FIELDS:
            raise ValueError("API cache index entry has unsupported schema")
        _validate_request(
            str(entry["service"]),
            str(entry["identifier"]),
            str(entry["request_url"]),
        )
        raw_path = Path(str(entry["raw_response_path"]))
        if raw_path.is_absolute() or ".." in raw_path.parts:
            raise ValueError("API cache index raw response path is not portable")
        if not isinstance(entry["http_status"], int):
            raise ValueError("API cache index HTTP status is not an integer")
        for field in ("response_sha256", "error_body_sha256"):
            digest = str(entry[field])
            if digest and not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError(f"API cache index {field} is not SHA-256")
        key = _entry_key(entry)
        if key in seen:
            raise ValueError(f"duplicate API cache index entry: {key}")
        seen.add(key)
    return value


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_bytes_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _entry_key(entry: dict[str, object]) -> tuple[str, str, str]:
    return (
        str(entry["service"]),
        str(entry["identifier"]),
        str(entry["request_url"]),
    )


def cached_request(service: str, identifier: str, url: str) -> CacheEntry:
    """Return a verified cached response or retrieve and index it once."""

    _validate_request(service, identifier, url)
    cache_root = _cache_root()
    index_path = _index_path()
    wanted = (service, identifier, url)
    cache_root.mkdir(parents=True, exist_ok=True)
    lock_path = cache_root / ".index.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        index = _load_index(index_path)
        matches = [entry for entry in index["entries"] if _entry_key(entry) == wanted]
        if len(matches) > 1:
            raise ValueError(f"duplicate API cache index entry: {wanted}")
        if matches:
            stored = matches[0]
            relative = Path(str(stored["raw_response_path"]))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("cache index raw response path is not portable")
            raw_path = cache_root / relative
            body = raw_path.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            if digest != stored["response_sha256"]:
                raise ValueError(
                    f"cached response SHA-256 mismatch: {relative.as_posix()}"
                )
            return CacheEntry(**stored, body=body, from_cache=True)

        if os.environ.get("SURVEY_API_CACHE_ONLY") == "1":
            raise ValueError(f"cache-only request missing: {wanted}")
        retrieval_time = datetime.now(timezone.utc).isoformat()
        try:
            response = requests.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json, application/json, application/atom+xml",
                    "User-Agent": "compiler-lab-llm2fpga-survey/1.0",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=45,
            )
            status = int(response.status_code)
            body = response.content
        except requests.RequestException as error:
            status = 0
            body = f"request_error:{type(error).__name__}".encode(
                "ascii", errors="replace"
            )

        digest = hashlib.sha256(body).hexdigest()
        request_digest = hashlib.sha256("\0".join(wanted).encode("utf-8")).hexdigest()
        relative = Path("responses") / service / f"{request_digest}.body"
        target = cache_root / relative
        _write_bytes_atomic(target, body)
        stored = {
            "service": service,
            "identifier": identifier,
            "request_url": url,
            "raw_response_path": relative.as_posix(),
            "http_status": status,
            "retrieved_at_utc": retrieval_time,
            "response_sha256": digest,
            "error_body_sha256": digest if status == 0 or status >= 400 else "",
        }
        entries = [*index["entries"], stored]
        entries.sort(key=_entry_key)
        _write_json_atomic(index_path, {"schema_version": 1, "entries": entries})
        return CacheEntry(**stored, body=body, from_cache=False)


def licence_state(
    repository_status: int, licence_status: int, licence_evidence: str
) -> str:
    """Classify observed licence evidence without inferring from visibility."""

    if repository_status != 200 or licence_status not in {200, 404}:
        return "unavailable"
    if licence_status == 404:
        return "none_detected"
    return "detected" if licence_evidence.strip() else "none_detected"


def response_json(entry: CacheEntry) -> object:
    if entry.http_status < 200 or entry.http_status >= 300:
        return {}
    try:
        return json.loads(entry.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MalformedResponseError(
            f"malformed JSON response for {entry.service}:{entry.identifier}"
        ) from error


def _arxiv_url(arxiv_id: str) -> str:
    return f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id, safe='.') }"


def metadata_requests(arxiv_id: str, doi: str) -> list[tuple[str, str, str]]:
    """Return stable-identifier API requests; no title/author search is emitted."""

    requests_to_make: list[tuple[str, str, str]] = []
    if arxiv_id:
        requests_to_make.append(("arxiv", arxiv_id, _arxiv_url(arxiv_id)))
    if doi:
        normalized = doi.strip().lower()
        encoded = quote(normalized, safe="")
        requests_to_make.extend(
            [
                (
                    "crossref",
                    normalized,
                    f"https://api.crossref.org/works/{encoded}",
                ),
                (
                    "openalex",
                    f"doi:{normalized}",
                    "https://api.openalex.org/works/https://doi.org/"
                    + quote(normalized, safe="/"),
                ),
            ]
        )
    return requests_to_make


def enrich_selected_metadata(
    deep_review_path: Path, records_path: Path
) -> dict[str, dict[str, int]]:
    with records_path.open(encoding="utf-8", newline="") as handle:
        records = {row["record_id"]: row for row in csv.DictReader(handle)}
    result: dict[str, dict[str, int]] = {}
    with deep_review_path.open(encoding="utf-8", newline="") as handle:
        selected_rows = list(csv.DictReader(handle))
    for selected in selected_rows:
        family_id = selected["project_family_id"]
        record = records.get(selected["preferred_record_id"], {})
        statuses: dict[str, int] = {}
        for service, identifier, url in metadata_requests(
            record.get("arxiv_id", ""), record.get("doi", "")
        ):
            statuses[service] = cached_request(service, identifier, url).http_status
        result[family_id] = statuses
    return result


def write_retrieval_log(path: Path | None = None) -> None:
    """Write one redacted, portable row per cache-index response."""

    target = path or Path(os.environ.get("SURVEY_API_LOG_PATH", DEFAULT_LOG_PATH))
    rows = retrieval_log_rows()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=target.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(target)


def retrieval_log_rows() -> list[dict[str, object]]:
    """Return a deterministic log projection of the current cache index."""

    index = _load_index(_index_path())
    rows = []
    for entry in index["entries"]:
        row = {field: entry[field] for field in LOG_FIELDS if field in entry}
        row["failure_code"] = retrieval_failure_code(int(entry["http_status"]))
        rows.append(row)
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--deep-review", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    arguments = parser.parse_args()
    enrich_selected_metadata(arguments.deep_review, arguments.records)
    write_retrieval_log(arguments.log)
