"""SpecStream: web search with one best passage per result, and the extract endpoint as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['SPECSTREAM_API_KEY']}", "Content-Type": "application/json"}


def _data(payload: Any) -> dict[str, Any]:
    # A successful reply is {"data": {...}}; a failed one is {"error": {...}}.
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else {}


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.specstream.ai/v1/web-search", headers=_headers(),
        body={**spec.request_config, "q": query, "num": max_results}, timeout=45,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet"), {"published": item.get("published")})
        for item in _data(payload).get("sources") or [] if isinstance(item, dict)
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    # With a query, the page text comes back as the passages closest to it, within max_chars.
    body: dict[str, Any] = {"urls": [url], "format": "markdown", "max_chars": max_chars}
    if objective.strip():
        body["query"] = objective.strip()[:2000]
    return tool_api.request(
        method="POST", url="https://api.specstream.ai/v1/extract", headers=_headers(), body=body, timeout=60,
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    item = (_data(payload).get("results") or [{}])[0]
    if item.get("status") != "ok":
        raise RuntimeError(f"{spec.key} could not read the page: {item.get('status') or 'no result'}")
    return page(spec, url, item.get("text") or "", item.get("url") or url, item.get("title") or "", max_chars)


def actual_cost(call: VendorCall, default: float | None) -> float | None:
    """Every reply states what the call cost; a search with no results and a page with no text cost nothing."""
    cost = _data(call.raw_response).get("price_usd")
    return float(cost) if isinstance(cost, (int, float)) and cost >= 0 else default
