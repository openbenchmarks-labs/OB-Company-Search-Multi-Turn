"""No search: the model answers from what it already knows. The agent gives it no tools, so nothing here is called."""

from __future__ import annotations

from typing import Any

from ..tool_api import VendorCall, VendorSpec


def search(spec: VendorSpec, query: str, max_results: int) -> VendorCall:
    raise RuntimeError("the no-search setup has no web_search tool")


def parse_hits(payload: dict[str, Any], max_results: int) -> list[dict[str, Any]]:
    return []
