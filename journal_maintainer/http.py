"""Bounded HTTP helper for GitHub and Commons public interfaces."""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from .models import utcnow


class HttpError(RuntimeError):
    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
    max_bytes: int = 2 * 1024 * 1024,
    context: ssl.SSLContext | None = None,
) -> Any:
    body = None
    request_headers = {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "mncs-atlas-journal-maintainer/0.1",
    }
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(body))
    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            raw = _read_bounded(response, max_bytes)
            status = int(getattr(response, "status", 200))
    except HTTPError as error:
        raw = _read_bounded(error, max_bytes)
        raise HttpError("HTTP_ERROR", f"HTTP {error.code} for {url}", status=int(error.code)) from error
    except URLError as error:
        raise HttpError("UNAVAILABLE", f"endpoint unavailable: {url}") from error
    except TimeoutError as error:
        raise HttpError("TIMEOUT", f"timeout contacting {url}") from error
    try:
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HttpError("INVALID_JSON", f"non-JSON response from {url}") from error
    finally:
        del status


def _read_bounded(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(64 * 1024, max_bytes - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise HttpError("RESPONSE_TOO_LARGE", "response exceeded maintainer read bound")
        chunks.append(chunk)


def encode_query(url: str, params: dict[str, str]) -> str:
    return f"{url}?{urlencode(params)}" if params else url


def join_url(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def timestamped() -> str:
    return utcnow().isoformat()
