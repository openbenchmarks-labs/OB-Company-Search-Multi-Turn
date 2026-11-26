"""TinyFish: search, and the fetch API as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page, site_scoped


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    sent_query, include_domains = site_scoped(spec, query)
    params = {"query": sent_query, **({"include_domains": ",".join(include_domains)} if include_domains else {})}
    return tool_api.request(
        method="GET", url="https://api.search.tinyfish.ai",
        headers={"X-API-Key": os.environ["TINYFISH_API_KEY"], "Accept": "application/json"},
        params=params, timeout=45,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet"), {"site_name": item.get("site_name"), "date": item.get("date")})
        for item in payload.get("results") or []
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.fetch.tinyfish.ai",
        headers={"X-API-Key": os.environ["TINYFISH_API_KEY"], "Content-Type": "application/json"},
        body={"urls": [url], "purpose": objective, "format": "markdown"},
        timeout=120,
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = (payload.get("results") or [{}])[0]
    final_url = item.get("final_url") or item.get("url") or url
    return page(spec, url, item.get("text") or "", final_url, item.get("title") or "", max_chars)
