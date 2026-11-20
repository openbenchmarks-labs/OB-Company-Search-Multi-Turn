"""Linkup: search at the setup's depth, and the fetch endpoint as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    depth = spec.request_config["depth"]
    return tool_api.request(
        method="POST", url="https://api.linkup.so/v1/search",
        headers={"Authorization": f"Bearer {os.environ['LINKUP_API_KEY']}", "Content-Type": "application/json"},
        body={"q": query, "depth": depth, "outputType": "searchResults", "maxResults": max_results},
        timeout=180 if depth == "deep" else 90,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("name") or item.get("title"), item.get("content") or item.get("snippet"))
        for item in payload.get("results") or []
        if item.get("type") != "image"
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.linkup.so/v1/fetch",
        headers={"Authorization": f"Bearer {os.environ['LINKUP_API_KEY']}", "Content-Type": "application/json"},
        body={"url": url, "mode": "standard", "renderJs": False},
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    return page(spec, url, payload.get("markdown") or "", url, "", max_chars)
