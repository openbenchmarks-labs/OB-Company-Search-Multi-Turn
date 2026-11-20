"""Seltz: company-scoped search only; pages come from the custom fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.seltz.ai/v1/search",
        headers={"x-api-key": os.environ["SELTZ_API_KEY"], "Content-Type": "application/json"},
        body={"query": query, "max_results": max_results, "scope": "companies"},
        timeout=45,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title") or item.get("name"), item.get("content") or item.get("snippet"), {"domain": item.get("domain")})
        for item in payload.get("documents") or []
    ]
