"""Tavily: search at the setup's depth, and extract as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    search_depth = str(spec.request_config["search_depth"])
    body = {"query": query, "search_depth": search_depth, "max_results": max_results}
    if search_depth == "advanced":
        body["chunks_per_source"] = int(spec.request_config["chunks_per_source"])
    return tool_api.request(
        method="POST", url="https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}", "Content-Type": "application/json"},
        body=body,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("content"), {"score": item.get("score")})
        for item in payload.get("results") or []
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.tavily.com/extract",
        headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}", "Content-Type": "application/json"},
        body={"urls": [url], "extract_depth": spec.request_config["search_depth"]},
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = (payload.get("results") or [{}])[0]
    return page(spec, url, item.get("raw_content") or item.get("content") or "", item.get("url") or url, "", max_chars)
