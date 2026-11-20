"""Context.dev: web search with highlights, and markdown scrape as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page

USD_PER_CREDIT = tool_api.tool_config("context")["usd_per_credit"]


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.context.dev/v1/web/search",
        headers={"Authorization": f"Bearer {os.environ['CONTEXT_API_KEY']}", "Content-Type": "application/json"},
        body={**spec.request_config, "query": query, "numResults": max(10, min(max_results, 100))},
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    hits = []
    for item in payload.get("results") or []:
        highlights = item.get("highlights") or {}
        parts = highlights.get("highlights") or []
        snippet = "\n".join(part for part in parts if isinstance(part, str)) if highlights.get("code") == "SUCCESS" else ""
        hits.append(hit(item.get("url"), item.get("title"), snippet.strip() or item.get("description")))
    return hits


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="GET", url="https://api.context.dev/v1/web/scrape/markdown",
        headers={"Authorization": f"Bearer {os.environ['CONTEXT_API_KEY']}"},
        params={"url": url, "useMainContentOnly": "true"}, timeout=120,
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("success") is not True:
        raise RuntimeError("context native fetch failed")
    metadata = payload.get("metadata") or {}
    final_url = metadata.get("finalUrl") or payload.get("url") or url
    return page(spec, url, payload.get("markdown") or "", final_url, metadata.get("title") or "", max_chars)


def actual_cost(call: VendorCall, default: float | None) -> float | None:
    """Context bills in credits and reports how many each call used."""
    payload = call.raw_response if isinstance(call.raw_response, dict) else {}
    credits = (payload.get("key_metadata") or {}).get("credits_consumed")
    return credits * USD_PER_CREDIT if isinstance(credits, (int, float)) else None
