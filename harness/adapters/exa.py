"""Exa: deep or instant search with highlights, and the contents endpoint as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page, site_scoped


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    kind = spec.request_config["type"]
    sent_query, include_domains = site_scoped(spec, query)
    body: dict[str, Any] = {"query": sent_query, "type": kind, "numResults": max_results, "contents": {"highlights": True}}
    if include_domains:
        body["includeDomains"] = include_domains
    return tool_api.request(
        method="POST", url="https://api.exa.ai/search",
        headers={"x-api-key": os.environ["EXA_API_KEY"], "Content-Type": "application/json"},
        body=body,
        timeout=120 if kind == "deep" else 60,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    hits = []
    for item in payload.get("results") or []:
        highlights = item.get("highlights") or []
        snippet = " ".join(x for x in highlights if isinstance(x, str)) or item.get("text")
        hits.append(hit(item.get("url"), item.get("title"), snippet))
    return hits


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.exa.ai/contents",
        headers={"x-api-key": os.environ["EXA_API_KEY"], "Content-Type": "application/json"},
        body={"urls": [url], "text": {"maxCharacters": max_chars, "includeHtmlTags": False}},
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = (payload.get("results") or [{}])[0]
    return page(spec, url, item.get("text") or "", item.get("url") or url, item.get("title") or "", max_chars)
