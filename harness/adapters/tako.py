"""Tako: web search with highlights, and the contents API as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page, site_scoped


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    sent_query, include_domains = site_scoped(spec, query)
    web: dict[str, Any] = {"count": min(max_results, 20), "highlights": spec.request_config["highlights"]}
    if include_domains:
        web["include_domains"] = include_domains
    return tool_api.request(
        method="POST", url="https://tako.com/api/v3/search",
        headers={"X-API-Key": os.environ["TAKO_API_KEY"], "Content-Type": "application/json"},
        body={"query": sent_query, "effort": spec.request_config["effort"], "sources": {"web": web}},
        timeout=90,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet"),
            {"source_name": item.get("source_name"), "publish_date": item.get("publish_date")})
        for item in payload.get("web_results") or []
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://tako.com/api/v1/contents",
        headers={"X-API-Key": os.environ["TAKO_API_KEY"], "Content-Type": "application/json"},
        body={"url": url, "mode": "inline", "max_chars": max_chars},
        timeout=120,
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = (payload.get("contents") or [{}])[0]
    return page(spec, url, item.get("data") or "", item.get("source_url") or url, "", max_chars)
