"""SERP via RapidAPI: Google results only; pages come from the custom fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    return tool_api.request(
        method="GET", url="https://google-search74.p.rapidapi.com/",
        headers={"x-rapidapi-key": os.environ["RAPIDAPI_KEY"], "x-rapidapi-host": "google-search74.p.rapidapi.com"},
        params={"query": query, "limit": max_results}, timeout=45,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url") or item.get("link"), item.get("title"), item.get("description") or item.get("snippet"))
        for item in payload.get("results") or []
    ]
