"""Perplexity: search only; pages come from the custom fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    if search_context_size not in {None, "low", "medium", "high"}:
        raise ValueError("Perplexity search_context_size must be low, medium, or high")
    return tool_api.request(
        method="POST", url="https://api.perplexity.ai/search",
        headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}", "Content-Type": "application/json"},
        body={
            "query": query,
            "max_results": min(max_results, 20),
            "search_context_size": search_context_size or "high",
        },
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet"), {"date": item.get("date"), "last_updated": item.get("last_updated")})
        for item in payload.get("results") or []
    ]
