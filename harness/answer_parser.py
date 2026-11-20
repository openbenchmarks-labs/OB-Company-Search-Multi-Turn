"""Turns the agent's final JSON answer into a clean list of companies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .dataset import normalize_company_name


@dataclass(frozen=True)
class ParsedCompany:
    name: str
    domain: str | None
    cited_urls: list[str]
    evidence: list[dict[str, str]]


def normalize_domain(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if "://" in raw:
        raw = urlparse(raw).hostname or ""
    raw = raw.split("/")[0].split(":")[0].removeprefix("www.").strip(".")
    if not raw or "." not in raw or not re.fullmatch(r"[a-z0-9.-]+", raw):
        return None
    return raw


def _url(value: Any) -> str | None:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    return raw if parsed.scheme in {"http", "https"} and parsed.hostname else None


def parse_company_set(raw: str) -> list[ParsedCompany]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"final response is not JSON: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("companies"), list):
        raise ValueError("final response must be an object with a companies array")
    output: list[ParsedCompany] = []
    seen: set[str] = set()
    for index, item in enumerate(payload["companies"], 1):
        if not isinstance(item, dict):
            raise ValueError(f"company {index} is not an object")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError(f"company {index} has no name")
        domain = normalize_domain(item.get("domain"))
        urls = list(dict.fromkeys(filter(None, (_url(value) for value in item.get("cited_urls") or []))))
        evidence: list[dict[str, str]] = []
        for row in item.get("evidence") or []:
            if not isinstance(row, dict):
                continue
            url = _url(row.get("url"))
            claim = str(row.get("claim") or "").strip()
            if url and claim:
                evidence.append({"url": url, "claim": claim})
                if url not in urls:
                    urls.append(url)
        identity = domain or normalize_company_name(name)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        output.append(ParsedCompany(name, domain, urls, evidence))
    return output
