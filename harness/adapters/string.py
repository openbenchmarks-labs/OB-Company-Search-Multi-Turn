"""String Web Access: Google search, and a readable-markdown page fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit, page


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['STRING_API_KEY']}", "Content-Type": "application/json"}


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    # Without searchCount, String returns the first results page, so the harness trims it to max_results.
    return tool_api.request(
        method="POST", url="https://request.usestring.ai/v1/search", headers=_headers(),
        body={"query": query, "engine": str(spec.request_config["engine"])},
        timeout=60,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet"), {"position": item.get("position"), "display_url": item.get("displayUrl")})
        for item in payload.get("results") or []
    ]


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    return tool_api.request(
        method="POST", url="https://request.usestring.ai/v1/fetch", headers=_headers(),
        body={
            "url": url,
            "format": str(spec.request_config["format"]),
            "markdownMode": str(spec.request_config["markdownMode"]),
        },
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    destination_status = str(payload.get("_status_code") or "")
    if destination_status and not destination_status.startswith("2"):
        raise RuntimeError(f"string native fetch reached HTTP {destination_status} at the destination")
    return page(spec, url, payload.get("_markdown") or "", url, "", max_chars)
