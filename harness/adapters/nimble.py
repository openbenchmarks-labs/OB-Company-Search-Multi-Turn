"""Nimble: search at the setup's depth, and Extract as the page fetch."""

from __future__ import annotations

import math
import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit

SEARCH_URL = "https://sdk.nimbleway.com/v2/search"
EXTRACT_URL = "https://sdk.nimbleway.com/v2/extract"


def search(spec: VendorSpec, query: str, max_results: int, search_context_size: str | None) -> VendorCall:
    return tool_api.request(
        method="POST", url=SEARCH_URL,
        headers={"Authorization": f"Bearer {os.environ['NIMBLE_API_KEY']}", "Content-Type": "application/json"},
        body={"query": query, "search_depth": spec.request_config["search_depth"], "full_content": False,
              "focus": "general", "max_results": max_results},
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    rows = payload.get("results")
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get("url"), str):
            continue
        url = row["url"].strip()
        if not url or url in seen:
            continue
        seen.add(url)
        hits.append(hit(url, str(row.get("title") or ""), str(row.get("description") or "")))
        if len(hits) >= max_results:
            break
    return hits


def fetch(spec: VendorSpec, url: str, objective: str, max_chars: int) -> VendorCall:
    fetch_unit_cost()  # Validate an optional rate before issuing the call.
    return tool_api.request(
        method="POST", url=EXTRACT_URL,
        headers={"Authorization": f"Bearer {os.environ['NIMBLE_API_KEY']}", "Content-Type": "application/json"},
        body={"url": url, "formats": ["markdown"]}, timeout=90,
    )


def read_page(spec: VendorSpec, url: str, payload: Any, max_chars: int) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("status") not in (None, "success"):
        raise RuntimeError("Nimble Extract returned an unsuccessful response")
    status = payload.get("status_code")
    if status is not None and not 200 <= int(status) < 300:
        raise RuntimeError(f"Nimble Extract upstream HTTP {status}")
    data = payload.get("data") or {}
    text = data.get("markdown") if isinstance(data, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Nimble Extract returned no markdown content")
    return {"requested_url": url, "final_url": payload.get("url") or url,
            "title": "", "text": text[:max_chars], "truncated": len(text) > max_chars,
            "fetch_provider": "nimble_extract"}


def fetch_unit_cost() -> float | None:
    """Extract has no list price; your own rate comes from the environment, unset means unknown."""
    raw = os.getenv("NIMBLE_EXTRACT_USD_PER_REQUEST", "").strip()
    if not raw:
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError("NIMBLE_EXTRACT_USD_PER_REQUEST must be finite and nonnegative")
    return value
