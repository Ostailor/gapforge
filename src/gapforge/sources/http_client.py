"""Small cached HTTP client for source connectors."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HttpClientError(RuntimeError):
    pass


class CachedHttpClient:
    def __init__(
        self,
        cache_dir: Path,
        *,
        timeout: float = 10.0,
        retries: int = 2,
        user_agent: str = "GapForge/0.1 (+https://example.local/gapforge)",
    ) -> None:
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_json(self, url: str, params: dict[str, Any] | None = None, *, namespace: str = "http") -> Any:
        body = self.get_text(url, params, namespace=namespace)
        return json.loads(body)

    def get_text(self, url: str, params: dict[str, Any] | None = None, *, namespace: str = "http") -> str:
        body, _headers = self.get_bytes(url, params, namespace=namespace)
        return body.decode("utf-8", errors="replace")

    def get_bytes(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        namespace: str = "http",
        max_bytes: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        cache_path = self._cache_path(namespace, url, params or {})
        if cache_path.exists():
            return cache_path.read_bytes(), {}
        if os.environ.get("GAPFORGE_DISABLE_NETWORK") == "1":
            raise HttpClientError(f"Network disabled for uncached GET {url}")

        full_url = self._full_url(url, params or {})
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                request_headers = {"User-Agent": self.user_agent, "Accept": "*/*"}
                request_headers.update(headers or {})
                request = Request(full_url, headers=request_headers)
                with urlopen(request, timeout=self.timeout) as response:
                    response_headers = _response_headers(response)
                    content_length = response_headers.get("content-length")
                    if max_bytes is not None and content_length:
                        try:
                            if int(content_length) > max_bytes:
                                raise HttpClientError(f"GET failed for {full_url}: response exceeds {max_bytes} bytes")
                        except ValueError:
                            pass
                    data = response.read(max_bytes + 1) if max_bytes is not None else response.read()
                if max_bytes is not None and len(data) > max_bytes:
                    raise HttpClientError(f"GET failed for {full_url}: response exceeds {max_bytes} bytes")
                cache_path.write_bytes(data)
                return data, response_headers
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.25 * (attempt + 1))
        raise HttpClientError(f"GET failed for {full_url}: {last_error}")

    def _cache_path(self, namespace: str, url: str, params: dict[str, Any]) -> Path:
        namespace_dir = self.cache_dir / namespace
        namespace_dir.mkdir(parents=True, exist_ok=True)
        key = json.dumps({"url": url, "params": params}, sort_keys=True, default=str)
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return namespace_dir / f"{digest}.cache"

    def _full_url(self, url: str, params: dict[str, Any]) -> str:
        clean_params = {key: value for key, value in params.items() if value not in (None, "")}
        if not clean_params:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{urlencode(clean_params, doseq=True)}"


def cache_summary(cache_dir: Path) -> dict[str, Any]:
    """Return lightweight cache diagnostics for CLI and docs examples."""

    if not cache_dir.exists():
        return {"cache_dir": str(cache_dir), "entries": 0, "bytes": 0, "namespaces": {}}
    files = [path for path in cache_dir.rglob("*.cache") if path.is_file()]
    namespaces: dict[str, int] = {}
    for path in files:
        namespace = path.parent.name if path.parent != cache_dir else "http"
        namespaces[namespace] = namespaces.get(namespace, 0) + 1
    return {
        "cache_dir": str(cache_dir),
        "entries": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "namespaces": dict(sorted(namespaces.items())),
    }


def _response_headers(response: object) -> dict[str, str]:
    raw_headers = getattr(response, "headers", {}) or {}
    if hasattr(raw_headers, "items"):
        return {str(key).lower(): str(value) for key, value in raw_headers.items()}
    return {}
