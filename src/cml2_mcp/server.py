"""Thin MCP server for Cisco CML2.

Exposes two tools and one resource:
- tool  cml_openapi : fetch (and cache) CML's live OpenAPI spec
- tool  cml_api     : generic authenticated REST call (after /api/v0)
- resource cml://openapi.json : same content as cml_openapi() for clients that prefer resources

The model is expected to read openapi.json before crafting calls so request and
response shapes are never guessed. Auth (JWT) is handled internally with a cached
token and a single transparent retry on 401.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cml2")

OPENAPI_TTL_SECONDS = 24 * 3600


def _cache_dir() -> Path:
    d = Path(os.environ.get("CML_CACHE_DIR") or (Path.home() / ".cache" / "cml"))
    d.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(d, 0o700)
    return d


def _require_env() -> tuple[str, str, str]:
    url = os.environ.get("CML_URL")
    user = os.environ.get("CML_USERNAME")
    pw = os.environ.get("CML_PASSWORD")
    missing = [
        k for k, v in (("CML_URL", url), ("CML_USERNAME", user), ("CML_PASSWORD", pw)) if not v
    ]
    if missing:
        raise RuntimeError(f"missing required env: {', '.join(missing)}")
    assert url and user and pw  # narrow types for the checker
    return url.rstrip("/"), user, pw


def _verify_ssl() -> bool:
    return os.environ.get("CML_VERIFY_SSL", "false").lower() == "true"


def _client(token: str | None = None) -> httpx.Client:
    headers: dict[str, str] = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(verify=_verify_ssl(), timeout=60.0, headers=headers)


def _token_path() -> Path:
    return _cache_dir() / "token"


def _login() -> str:
    base, user, pw = _require_env()
    with _client() as c:
        r = c.post(
            f"{base}/api/v0/authenticate",
            json={"username": user, "password": pw},
        )
        if r.status_code != 200:
            raise RuntimeError(f"authenticate failed: HTTP {r.status_code}: {r.text[:200]}")
        # CML returns the JWT as a bare JSON string ("eyJ...").
        try:
            token = r.json()
        except json.JSONDecodeError:
            token = r.text.strip().strip('"')
    if not isinstance(token, str) or not token:
        raise RuntimeError("empty token from /authenticate")
    tp = _token_path()
    tp.write_text(token)
    with contextlib.suppress(OSError):
        os.chmod(tp, 0o600)
    return token


def _read_token() -> str | None:
    tp = _token_path()
    if not tp.exists():
        return None
    t = tp.read_text().strip()
    return t or None


@mcp.tool()
def cml_openapi(refresh: bool = False) -> str:
    """Return CML2's live OpenAPI spec as a JSON string.

    Cached at $CML_CACHE_DIR/openapi.json (default ~/.cache/cml/) for 24h.
    Set refresh=True to force a re-fetch.
    """
    base, _, _ = _require_env()
    p = _cache_dir() / "openapi.json"
    fresh = p.exists() and (time.time() - p.stat().st_mtime) < OPENAPI_TTL_SECONDS
    if not refresh and fresh:
        return p.read_text()
    with _client() as c:
        r = c.get(f"{base}/api/v0/openapi.json")
        r.raise_for_status()
    p.write_text(r.text)
    return r.text


@mcp.tool()
def cml_api(method: str, path: str, body: Any = None) -> str:
    """Authenticated CML2 REST call.

    Args:
      method: HTTP method (GET/POST/PUT/PATCH/DELETE).
      path:   Path AFTER /api/v0, must start with '/'. Example: '/labs'.
      body:   Optional JSON-serializable value (object/array/string/etc.).
              Sent as the request body with Content-Type: application/json.

    Returns the raw response body as text (callers should json.parse if needed).
    Re-authenticates and retries once on HTTP 401. Raises on non-2xx.
    """
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("path must be a string starting with '/'")
    if not isinstance(method, str) or not method:
        raise ValueError("method is required")

    base, _, _ = _require_env()
    url = f"{base}/api/v0{path}"
    method_u = method.upper()

    request_kwargs: dict[str, Any] = {}
    if body is not None:
        request_kwargs["json"] = body

    def _call(tok: str) -> httpx.Response:
        with _client(tok) as c:
            return c.request(method_u, url, **request_kwargs)

    token = _read_token() or _login()
    resp = _call(token)
    if resp.status_code == 401:
        token = _login()
        resp = _call(token)

    if 200 <= resp.status_code < 300:
        return resp.text
    raise RuntimeError(f"HTTP {resp.status_code} on {method_u} {path}: {resp.text[:500]}")


@mcp.resource("cml://openapi.json")
def openapi_resource() -> str:
    """The live (24h-cached) OpenAPI spec, exposed as an MCP resource."""
    return cml_openapi()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
