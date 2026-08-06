#!/usr/bin/env python3
"""Cache-first, credential-free metadata retrieval for the survey audit."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit, urlunsplit

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
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("request URL must be credential-free HTTPS")
    for item in parsed.query.split("&") if parsed.query else ():
        name = unquote(item.split("=", 1)[0]).lower()
        if name in SECRET_QUERY_NAMES:
            raise ValueError(f"request URL contains forbidden query field: {name}")
    if re.search(r"(?i)(bearer|authorization|access[_-]?token)=", url):
        raise ValueError("request URL contains credential material")


def _load_index(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1, "entries": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("entries"), list):
        raise ValueError("API cache index has unsupported schema")
    return value


def _write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
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
    index = _load_index(index_path)
    wanted = (service, identifier, url)
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
            raise ValueError(f"cached response SHA-256 mismatch: {relative.as_posix()}")
        return CacheEntry(**stored, body=body, from_cache=True)

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
        body = f"request_error:{type(error).__name__}".encode("ascii", errors="replace")

    digest = hashlib.sha256(body).hexdigest()
    request_digest = hashlib.sha256("\0".join(wanted).encode("utf-8")).hexdigest()
    relative = Path("responses") / service / f"{request_digest}.body"
    target = cache_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
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
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


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
    index = _load_index(_index_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS, lineterminator="\n")
        writer.writeheader()
        for entry in index["entries"]:
            row = {field: entry[field] for field in LOG_FIELDS if field in entry}
            row["failure_code"] = retrieval_failure_code(int(entry["http_status"]))
            writer.writerow(row)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--deep-review", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    arguments = parser.parse_args()
    enrich_selected_metadata(arguments.deep_review, arguments.records)
    write_retrieval_log(arguments.log)
