"""Shared pieces every search tool adapter uses.

There is deliberately no generic HTTP fallback here. A tool without a
documented native fetch endpoint exposes search only, or uses the reviewed
custom fetch in custom_fetch.py when its setup says so.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import requests
import yaml

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
REDACTED = "***REDACTED***"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class VendorSpec:
    key: str
    provider_slug: str
    provider_name: str
    config_slug: str
    endpoint: str
    env_keys: tuple[str, ...]
    search_unit_cost_usd: float | None
    native_fetch: bool
    fetch_endpoint: str | None
    fetch_kind: str | None
    request_config: dict[str, Any]
    fetch_unit_cost_usd: float | None = None
    custom_fetch: bool = False

    def public_dict(self, fetch_unit_cost_usd: float | None) -> dict[str, Any]:
        value = asdict(self)
        value["env_keys"] = list(self.env_keys)
        value["fetch_unit_cost_usd"] = fetch_unit_cost_usd
        return value


@dataclass
class VendorCall:
    status: str
    latency_ms: int
    raw_request: dict[str, Any]
    raw_response: Any
    error: str | None
    attempts: list[dict[str, Any]]
    cost_usd: float | None
    hits: list[dict[str, Any]] | None = None
    page: dict[str, Any] | None = None


def tool_config(tool: str) -> dict[str, Any]:
    return yaml.safe_load((TOOLS_DIR / f"{tool}.yaml").read_text(encoding="utf-8"))


def load_setups(tool: str) -> list[VendorSpec]:
    specs = []
    for key, setup in tool_config(tool)["setups"].items():
        pricing = setup["pricing"]
        specs.append(VendorSpec(
            key=key,
            provider_slug=setup["provider_slug"],
            provider_name=setup["provider_name"],
            config_slug=setup["config_slug"],
            endpoint=setup["endpoint"],
            env_keys=tuple(setup["env_keys"]),
            search_unit_cost_usd=pricing["search_usd"],
            native_fetch=setup["native_fetch"],
            fetch_endpoint=setup.get("fetch_endpoint"),
            fetch_kind=setup.get("fetch_kind"),
            request_config=setup["request_config"],
            fetch_unit_cost_usd=pricing.get("fetch_usd"),
            custom_fetch=setup.get("custom_fetch", False),
        ))
    return specs


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: REDACTED if any(token in key.lower() for token in ("key", "token", "authorization", "secret")) else value
        for key, value in headers.items()
    }


def json_or_text(response: Any) -> Any:
    headers = getattr(response, "headers", None) or {}
    if str(headers.get("content-type") or "").lower().startswith("text/markdown"):
        # String answers a fetch with the page itself and the destination status header.
        return {
            "_markdown": str(getattr(response, "text", ""))[:100_000],
            "_status_code": headers.get("x-status-code"),
        }
    try:
        return response.json()
    except ValueError:
        return {"_raw": str(getattr(response, "text", ""))[:100_000]}


def request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 90,
    retries: int = 3,
    request_fn: Callable[..., Any] = requests.request,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> VendorCall:
    started = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    payload: Any = None
    error: str | None = None
    for attempt in range(1, retries + 2):
        attempt_started = time.perf_counter()
        try:
            response = request_fn(
                method=method, url=url, headers=headers, json=body, params=params, timeout=timeout
            )
            payload = json_or_text(response)
            attempts.append({
                "attempt": attempt,
                "status_code": response.status_code,
                "latency_ms": round((time.perf_counter() - attempt_started) * 1000),
            })
            if response.ok:
                error = None
                break
            error = f"HTTP {response.status_code}: {str(payload)[:500]}"
            if response.status_code not in RETRYABLE_STATUS or attempt > retries:
                break
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            attempts.append({
                "attempt": attempt,
                "status_code": None,
                "latency_ms": round((time.perf_counter() - attempt_started) * 1000),
                "error": error,
            })
            if attempt > retries:
                break
        sleep_fn(min(2 ** (attempt - 1), 8))
    return VendorCall(
        status="ok" if error is None else "error",
        latency_ms=round((time.perf_counter() - started) * 1000),
        raw_request={
            "method": method,
            "url": url,
            "headers": redact_headers(headers),
            "body": body,
            "params": params,
        },
        raw_response=payload,
        error=error,
        attempts=attempts,
        cost_usd=None,
    )


def hit(url: Any, title: Any, snippet: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "url": str(url or ""),
        "title": str(title or ""),
        "snippet": str(snippet or "")[:4000],
        "metadata": metadata or {},
    }


def page(spec: VendorSpec, url: str, text: Any, final_url: Any, title: Any, max_chars: int) -> dict[str, Any]:
    if not str(text).strip():
        raise RuntimeError(f"{spec.key} native fetch returned no page content")
    return {
        "requested_url": url,
        "final_url": str(final_url),
        "title": str(title),
        "text": str(text)[:max_chars],
        "truncated": len(str(text)) > max_chars,
        "fetch_provider": spec.fetch_kind,
    }
