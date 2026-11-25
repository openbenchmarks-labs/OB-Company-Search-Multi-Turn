"""You.com: search with highlights (and licensed knowledge answers when the setup asks), and the contents endpoint as the page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://ydc-index.io/v1/search",
        headers={"X-API-Key": os.environ["YOU_API_KEY"], "Content-Type": "application/json"},
        body={**spec.request_config, "query": query, "count": min(max_results, 20)},
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    hits = []
    for item in (payload.get("results") or {}).get("web") or []:
        contents = item.get("contents") or {}
        snippets = contents.get("highlights") or item.get("snippets") or []
        snippet = "\n".join(value for value in snippets if isinstance(value, str))
        hits.append(hit(item.get("url"), item.get("title"), snippet or item.get("description"), {"page_age": item.get("page_age")}))
    return hits


def parse_knowledge(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    """Answers from You's licensed sources (knowledge: core); they carry provider credits, not URLs."""
    return [
        {
            "title": str(item.get("title") or ""),
            "answer": str(item.get("description") or "")[:4000],
            "as_of": item.get("as_of"),
            "providers": [str(a.get("name") or "") for a in item.get("attribution") or [] if isinstance(a, dict)],
        }
        for item in (payload.get("results") or {}).get("knowledge") or []
        if isinstance(item, dict) and item.get("type") == "answer" and item.get("description")
    ][:max_results]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://ydc-index.io/v1/contents",
        headers={"X-API-Key": os.environ["YOU_API_KEY"], "Content-Type": "application/json"},
        body={"urls": [url], "formats": ["markdown", "metadata"]},
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    item = (payload if isinstance(payload, list) else [{}])[0]
    text = item.get("markdown") or item.get("html") or ""
    return page(spec, url, text, item.get("url") or url, item.get("title") or "", max_chars)
