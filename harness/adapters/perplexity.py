"""Perplexity: search at one context size on both boards, and the Context API as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page, site_scoped


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}", "Content-Type": "application/json"}


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    sent_query, include_domains = site_scoped(spec, query)
    body: dict[str, Any] = {
        "query": sent_query,
        "max_results": min(max_results, 20),
        "search_context_size": spec.request_config["search_context_size"],
    }
    if include_domains:
        body["search_domain_filter"] = include_domains
    return tool_api.request(method="POST", url="https://api.perplexity.ai/search", headers=_headers(), body=body)


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet"), {"date": item.get("date"), "last_updated": item.get("last_updated")})
        for item in payload.get("results") or []
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.perplexity.ai/v1/context", headers=_headers(),
        body={"urls": [url], "formats": ["markdown"]},
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = (payload.get("results") or [{}])[0]
    status = (item.get("status") or {}).get("type")
    if status != "ok":
        raise RuntimeError(f"Perplexity Context returned status {status!r} for the page")
    metadata = item.get("metadata") or {}
    return page(spec, url, item.get("markdown") or "", metadata.get("source_url") or url, metadata.get("title") or "", max_chars)
