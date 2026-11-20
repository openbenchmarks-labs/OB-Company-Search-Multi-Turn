"""Parallel: search in the setup's mode, and extract as the page fetch."""

from __future__ import annotations

import os
import re
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page

_SITE_INCLUDE_RE = re.compile(r"(?<![-])site:([^\s]+)", re.I)


def parallel_site_policy(query: str) -> tuple[str, list[str]]:
    """Move positive site: filters to Parallel's include_domains policy."""
    domains: list[str] = []
    seen: set[str] = set()

    def take(match: re.Match[str]) -> str:
        raw = match.group(1).strip("\"'").rstrip("/")
        raw = re.sub(r"^https?://", "", raw, flags=re.I).removeprefix("www.")
        host = raw.split("/", 1)[0].strip(".").lower()
        if host and host not in seen:
            seen.add(host)
            domains.append(host)
        return " "

    cleaned = re.sub(r"\s+", " ", _SITE_INCLUDE_RE.sub(take, query)).strip()
    return cleaned, domains


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    mode = str(spec.request_config["mode"])
    sent_query = query
    advanced_settings: dict[str, Any] = {"max_results": max_results}
    if spec.request_config.get("site_operator_policy") == "source_policy":
        sent_query, include_domains = parallel_site_policy(query)
        if not sent_query:
            sent_query = " ".join(include_domains) or query
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
