"""Firecrawl: web search, and scrape as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.firecrawl.dev/v2/search",
        headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}", "Content-Type": "application/json"},
        body={"query": query, "limit": max_results},
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    rows = (data.get("web") or data.get("results") or []) if isinstance(data, dict) else data
    return [
        hit(item.get("url") or item.get("link"), item.get("title"), item.get("description") or item.get("snippet"))
        for item in rows or []
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.firecrawl.dev/v2/scrape",
        headers={"Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}", "Content-Type": "application/json"},
        body={"url": url, "formats": ["markdown"], "onlyMainContent": True},
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = payload.get("data") or {}
    metadata = item.get("metadata") or {}
    return page(spec, url, item.get("markdown") or "", metadata.get("sourceURL") or url, metadata.get("title") or "", max_chars)
