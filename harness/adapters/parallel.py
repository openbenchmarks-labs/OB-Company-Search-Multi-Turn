"""Parallel: search in the setup's mode, and extract as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page, site_scoped


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    mode = str(spec.request_config["mode"])
    sent_query, include_domains = site_scoped(spec, query)
    advanced_settings: dict[str, Any] = {"max_results": max_results}
    if include_domains:
        advanced_settings["source_policy"] = {"include_domains": include_domains}
    return tool_api.request(
        method="POST", url="https://api.parallel.ai/v1/search",
        headers={"x-api-key": os.environ["PARALLEL_API_KEY"], "Content-Type": "application/json"},
        body={
            "objective": sent_query,
            "search_queries": [sent_query],
            "mode": mode,
            "advanced_settings": advanced_settings,
        },
        timeout=120 if mode == "advanced" else 60,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    hits = []
    for item in payload.get("results") or []:
        excerpts = item.get("excerpts") or []
        hits.append(hit(item.get("url"), item.get("title"), "\n".join(x for x in excerpts if isinstance(x, str))))
    return hits


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://api.parallel.ai/v1/extract",
        headers={"x-api-key": os.environ["PARALLEL_API_KEY"], "Content-Type": "application/json"},
        body={"urls": [url], "objective": objective, "max_chars_total": max_chars, "advanced_settings": {"full_content": True}},
        timeout=120,
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    item = (payload.get("results") or [{}])[0]
    text = item.get("full_content") or "\n".join(item.get("excerpts") or [])
    return page(spec, url, text, item.get("url") or url, item.get("title") or "", max_chars)
