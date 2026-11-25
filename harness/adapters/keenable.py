"""Keenable: search in the setup's mode; pages come from the custom fetch."""

from __future__ import annotations

import os
from typing import Any

from .. import tool_api
from ..tool_api import VendorCall, VendorSpec, hit


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    mode = spec.request_config["mode"]
    return tool_api.request(
        method="POST", url="https://api.keenable.ai/v1/search",
        headers={"X-API-Key": os.environ["KEENABLE_API_KEY"], "Content-Type": "application/json"},
        body={"query": query, "max_results": max_results, **spec.request_config},
        timeout=90 if mode == "pro" else 45,
    )


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return [
        hit(item.get("url"), item.get("title"), item.get("snippet") or item.get("description"))
        for item in payload.get("results") or []
    ]
