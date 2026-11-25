"""Brave Search: web search only; pages come from the custom fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    return tool_api.request(
        method="GET", url="https://api.search.brave.com/res/v1/web/search",
        headers={"X-Subscription-Token": os.environ["BRAVE_SEARCH_API_KEY"], "Accept": "application/json"},
        params={"q": query, "count": min(max_results, 20), "result_filter": "web"},
        timeout=45,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("description") or item.get("snippet"))
        for item in (payload.get("web") or {}).get("results") or []
    ]
