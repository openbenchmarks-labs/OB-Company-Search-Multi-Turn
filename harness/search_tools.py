"""Loads every tool setup from tools/*.yaml and runs searches and page fetches through its adapter."""

from __future__ import annotations

import ipaddress
import socket
import time
from importlib import import_module
from typing import Any
from urllib.parse import urlparse

from .custom_fetch import fetch_page
from .tool_api import VendorCall, VendorSpec, load_setups

# Each name is tools/<name>.yaml plus harness/adapters/<name>.py, in default run order.
TOOLS = (
    "none",
    "context",
    "brave",
    "exa",
    "firecrawl",
    "linkup",
    "parallel",
    "seltz",
    "serp",
    "tavily",
    "tinyfish",
    "perplexity",
    "nimble",
    "you",
    "keenable",
    "specstream",
)
ADAPTERS = {tool: import_module(f"{__package__}.adapters.{tool}") for tool in TOOLS}

VENDORS: dict[str, VendorSpec] = {}
_ADAPTER_BY_SETUP: dict[str, Any] = {}
for _tool, _adapter in ADAPTERS.items():
    for _spec in load_setups(_tool):
        VENDORS[_spec.key] = _spec
        _ADAPTER_BY_SETUP[_spec.key] = _adapter

DEFAULT_VENDOR_KEYS = tuple(VENDORS)


def capability_inventory() -> list[dict[str, Any]]:
    return [
        {
            "vendor": spec.key,
            "search": spec.web_search,
            "native_fetch": spec.native_fetch,
            "fetch_kind": spec.fetch_kind,
            "custom_fetch": spec.custom_fetch,
            "fetch_available": spec.native_fetch or spec.custom_fetch,
        }
        for spec in VENDORS.values()
    ]


def required_env(vendor_keys: list[str] | tuple[str, ...]) -> list[str]:
    return sorted({key for vendor in vendor_keys for key in VENDORS[vendor].env_keys})


def validate_vendor_keys(vendor_keys: list[str] | tuple[str, ...]) -> None:
    unknown = sorted(set(vendor_keys) - set(VENDORS))
    if unknown:
        raise ValueError(f"unknown company-research vendors: {unknown}")


def dedupe(hits: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        url = hit["url"].strip()
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(hit)
        if len(output) >= max_results:
            break
    return output


def parse_hits(vendor_key: str, payload: Any, max_results: int) -> list[dict[str, Any]]:
    payload = payload if isinstance(payload, dict) else {}
    return dedupe(_ADAPTER_BY_SETUP[vendor_key].parse_hits(payload, max_results), max_results)


def read_page(vendor_key: str, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    spec = VENDORS[vendor_key]
    if not spec.native_fetch:
        raise RuntimeError(f"{vendor_key} has no vendor-native fetch adapter")
    return _ADAPTER_BY_SETUP[vendor_key].read_page(spec, url, payload, max_chars)


def _reported_dollar_cost(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    cost = payload.get("costDollars")
    candidate = cost.get("total") if isinstance(cost, dict) else None
    if candidate is None and isinstance(payload.get("usage"), dict):
        candidate = payload["usage"].get("total_cost_usd")
    try:
        total = float(candidate)
    except (TypeError, ValueError):
        return None
    return total if total >= 0 else None


def _cost(vendor_key: str, call: VendorCall, unit_cost: float | None) -> float | None:
    reported = _reported_dollar_cost(call.raw_response)
    default = (reported if reported is not None else unit_cost) if call.status == "ok" else 0.0
    adapter = _ADAPTER_BY_SETUP[vendor_key]
    return adapter.actual_cost(call, default) if hasattr(adapter, "actual_cost") else default


def search(vendor_key: str, query: str, *, max_results: int = 10) -> VendorCall:
    spec = VENDORS[vendor_key]
    adapter = _ADAPTER_BY_SETUP[vendor_key]
    call = adapter.search(spec, query, max_results)
    call.cost_usd = _cost(vendor_key, call, spec.search_unit_cost_usd)
    call.hits = []
    if call.status == "ok":
        payload = call.raw_response if isinstance(call.raw_response, dict) else {}
        try:
            call.hits = dedupe(adapter.parse_hits(payload, max_results), max_results)
            call.knowledge = adapter.parse_knowledge(payload, max_results) if hasattr(adapter, "parse_knowledge") else None
        except Exception as exc:  # noqa: BLE001
            call.status = "error"
            call.error = f"unreadable search reply: {type(exc).__name__}: {exc}"
            call.hits = []
    return call


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("web_fetch requires a public absolute http(s) URL")
    if parsed.hostname.lower() == "localhost":
        raise ValueError("web_fetch blocks localhost and private networks")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("web_fetch blocks localhost and private networks")


def _custom_fetch(url: str, max_chars: int) -> VendorCall:
    started = time.perf_counter()
    try:
        page = fetch_page(url, max_chars=max_chars)
        return VendorCall(
            status="ok", latency_ms=round((time.perf_counter() - started) * 1000),
            raw_request={"url": url, "fetch_kind": "custom_http_with_playwright_fallback"},
            raw_response=page, error=None,
            attempts=[{"attempt": 1, "provider": page["fetch_provider"]}],
            cost_usd=0.0, page=page,
        )
    except Exception as exc:  # noqa: BLE001
        return VendorCall(
            status="error", latency_ms=round((time.perf_counter() - started) * 1000),
            raw_request={"url": url, "fetch_kind": "custom_http_with_playwright_fallback"},
            raw_response=None, error=f"{type(exc).__name__}: {exc}",
            attempts=[], cost_usd=0.0,
        )


def fetch(vendor_key: str, url: str, *, objective: str, max_chars: int = 12_000) -> VendorCall:
    spec = VENDORS[vendor_key]
    if spec.custom_fetch:
        return _custom_fetch(url, max_chars)
    if not spec.native_fetch:
        return VendorCall(
            status="unavailable", latency_ms=0,
            raw_request={"url": url, "vendor": vendor_key}, raw_response=None,
            error="vendor-native web_fetch is unavailable; custom fetch is intentionally not implemented",
            attempts=[], cost_usd=None,
        )
    _assert_public_url(url)
    call = _ADAPTER_BY_SETUP[vendor_key].fetch(spec, url, objective, max_chars)
    if call.status == "ok":
        try:
            call.page = read_page(vendor_key, url, call.raw_response, max_chars)
        except Exception as exc:  # noqa: BLE001
            call.status = "error"
            call.error = f"{type(exc).__name__}: {exc}"
    call.cost_usd = _cost(vendor_key, call, spec.fetch_unit_cost_usd)
    return call
