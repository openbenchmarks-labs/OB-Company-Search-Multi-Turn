from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from harness.adapters.parallel import parallel_site_policy
from harness.search_tools import (
    VENDORS,
    capability_inventory,
    fetch,
    parse_hits,
    read_page,
    search,
)
from harness.tool_api import VendorCall


class SearchToolsTest(unittest.TestCase):
    def test_parallel_modes_use_source_policy_for_site_queries(self) -> None:
        fixture = {"results": [{"url": "https://example.test", "title": "Example", "excerpts": ["Evidence"]}]}
        empty_call = VendorCall(
            status="ok", latency_ms=1, raw_request={}, raw_response=fixture,
            error=None, attempts=[], cost_usd=None,
        )
        query = "funding site:Crunchbase.com/org site:https://techcrunch.com/startups -site:reddit.com"
        self.assertEqual(
            parallel_site_policy(query),
            ("funding -site:reddit.com", ["crunchbase.com", "techcrunch.com"]),
        )
        for key, mode in (
            ("parallel_basic", "basic"),
            ("parallel_advanced", "advanced"),
            ("parallel_fast", "fast"),
            ("parallel_turbo", "turbo"),
        ):
            with self.subTest(key=key):
                spec = VENDORS[key]
                self.assertEqual(spec.request_config, {
                    "mode": mode,
                    "site_operator_policy": "source_policy",
                })
                self.assertEqual(
                    spec.search_unit_cost_usd,
                    0.001 if mode in {"fast", "turbo"} else 0.005,
                )
                self.assertTrue(spec.native_fetch)
                self.assertEqual(parse_hits(key, fixture, 10)[0]["url"], "https://example.test")
                with (
                    patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}),
                    patch("harness.tool_api.request", return_value=empty_call) as request,
                ):
                    search(key, query, max_results=7)
                    body = request.call_args.kwargs["body"]
                    self.assertEqual(body["mode"], mode)
                    self.assertEqual(body["objective"], "funding -site:reddit.com")
                    self.assertEqual(body["search_queries"], ["funding -site:reddit.com"])
                    self.assertEqual(body["advanced_settings"], {
                        "max_results": 7,
                        "source_policy": {
                            "include_domains": ["crunchbase.com", "techcrunch.com"],
                        },
                    })

    def test_parallel_query_without_site_filter_is_unchanged(self) -> None:
        empty_call = VendorCall(
            status="ok", latency_ms=1, raw_request={}, raw_response={"results": []},
            error=None, attempts=[], cost_usd=None,
        )
        with (
            patch.dict(os.environ, {"PARALLEL_API_KEY": "test-key"}),
            patch("harness.tool_api.request", return_value=empty_call) as request,
        ):
            search("parallel_fast", "ordinary company query")
        body = request.call_args.kwargs["body"]
        self.assertEqual(body["objective"], "ordinary company query")
        self.assertNotIn("source_policy", body["advanced_settings"])

    def test_vendor_roster_and_fetch_inventory(self) -> None:
        self.assertEqual(
            set(VENDORS),
            {
                "context", "nimble_lite", "nimble_standard", "brave", "exa_deep", "exa_instant", "firecrawl", "linkup_deep",
                "linkup_fast", "linkup_standard", "parallel_advanced", "parallel_basic",
                "parallel_fast", "parallel_turbo", "seltz_companies", "serp",
                "tavily_advanced", "tavily_basic", "you_highlights", "you_highlights_core", "tinyfish", "perplexity",
            },
        )
        capabilities = {row["vendor"]: row for row in capability_inventory()}
        for key in (
            "context", "exa_deep", "exa_instant", "firecrawl", "linkup_deep", "linkup_fast",
            "linkup_standard", "parallel_advanced", "parallel_basic",
            "parallel_fast", "parallel_turbo", "tavily_advanced", "tavily_basic", "you_highlights", "you_highlights_core", "tinyfish",
        ):
            self.assertTrue(capabilities[key]["native_fetch"])
        for key in ("brave", "seltz_companies", "serp", "perplexity"):
            self.assertFalse(capabilities[key]["native_fetch"])
            self.assertTrue(capabilities[key]["custom_fetch"])
        self.assertTrue(all(row["fetch_available"] for row in capabilities.values()))
        self.assertEqual(
            VENDORS["perplexity"].request_config["search_context_size_by_research_mode"],
            {"search_only": "low", "search_and_fetch": "high"},
        )

    def test_every_vendor_response_shape_produces_ranked_hits(self) -> None:
        fixtures = {
            "context": {"results": [{"url": "https://a.test", "title": "A", "description": "fallback",
                                      "highlights": {"code": "SUCCESS", "highlights": ["one"]}}]},
            "brave": {"web": {"results": [{"url": "https://a.test", "title": "A", "description": "one"}]}},
            "exa_deep": {"results": [{"url": "https://a.test", "title": "A", "highlights": ["one"]}]},
            "exa_instant": {"results": [{"url": "https://a.test", "title": "A", "highlights": ["one"]}]},
            "firecrawl": {"data": {"web": [{"url": "https://a.test", "title": "A", "description": "one"}]}},
            "linkup_deep": {"results": [{"url": "https://a.test", "name": "A", "content": "one"}]},
            "linkup_fast": {"results": [{"url": "https://a.test", "name": "A", "content": "one"}]},
            "linkup_standard": {"results": [{"url": "https://a.test", "name": "A", "content": "one"}]},
            "parallel_advanced": {"results": [{"url": "https://a.test", "title": "A", "excerpts": ["one"]}]},
            "parallel_basic": {"results": [{"url": "https://a.test", "title": "A", "excerpts": ["one"]}]},
            "parallel_fast": {"results": [{"url": "https://a.test", "title": "A", "excerpts": ["one"]}]},
            "parallel_turbo": {"results": [{"url": "https://a.test", "title": "A", "excerpts": ["one"]}]},
            "seltz_companies": {"documents": [{"url": "https://a.test", "title": "A", "content": "one"}]},
            "serp": {"results": [{"url": "https://a.test", "title": "A", "description": "one"}]},
            "tavily_advanced": {"results": [{"url": "https://a.test", "title": "A", "content": "one"}]},
            "tavily_basic": {"results": [{"url": "https://a.test", "title": "A", "content": "one"}]},
            "you_highlights": {"results": {"web": [{"url": "https://a.test", "title": "A", "snippets": ["one"]}]}},
            "tinyfish": {"results": [{"url": "https://a.test", "title": "A", "snippet": "one"}]},
            "perplexity": {"results": [{"url": "https://a.test", "title": "A", "snippet": "one"}]},
        }
        fixtures["you_highlights_core"] = fixtures["you_highlights"]
        fixtures["nimble_lite"] = {"results": [{"url": "https://a.test", "title": "A", "description": "one"}]}
        fixtures["nimble_standard"] = fixtures["nimble_lite"]
        self.assertEqual(set(fixtures), set(VENDORS))
        for vendor, payload in fixtures.items():
            with self.subTest(vendor=vendor):
                self.assertEqual(parse_hits(vendor, payload, 10)[0]["url"], "https://a.test")
                if vendor == "context":
                    self.assertEqual(parse_hits(vendor, payload, 10)[0]["snippet"], "one")

    def test_public_board_search_request_contracts(self) -> None:
        fixtures = {
            "you_highlights": ("YOU_API_KEY", "https://ydc-index.io/v1/search", "POST"),
            "tinyfish": ("TINYFISH_API_KEY", "https://api.search.tinyfish.ai", "GET"),
            "perplexity": ("PERPLEXITY_API_KEY", "https://api.perplexity.ai/search", "POST"),
        }
        for vendor, (env_key, endpoint, method) in fixtures.items():
            with self.subTest(vendor=vendor):
                empty_call = VendorCall(
                    status="ok", latency_ms=1, raw_request={}, raw_response={},
                    error=None, attempts=[], cost_usd=None,
                )
                with (
                    patch.dict(os.environ, {env_key: "test-key"}),
                    patch("harness.tool_api.request", return_value=empty_call) as request,
                ):
                    search(vendor, "company query", max_results=7)
                self.assertEqual(request.call_args.kwargs["url"], endpoint)
                self.assertEqual(request.call_args.kwargs["method"], method)

    def test_perplexity_search_context_size_contract(self) -> None:
        for context_size in ("low", "high"):
            with self.subTest(context_size=context_size):
                empty_call = VendorCall("ok", 1, {}, {"results": []}, None, [], None)
                with (
                    patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test-key"}),
                    patch("harness.tool_api.request", return_value=empty_call) as request,
                ):
                    search(
                        "perplexity",
                        "company query",
                        search_context_size=context_size,
                    )
                self.assertEqual(
                    request.call_args.kwargs["body"]["search_context_size"],
                    context_size,
                )

    def test_tavily_search_depth_contracts(self) -> None:
        empty_call = VendorCall("ok", 1, {}, {"results": []}, None, [], None)
        for vendor, depth, expected_cost in (
            ("tavily_basic", "basic", 0.008),
            ("tavily_advanced", "advanced", 0.016),
        ):
            with self.subTest(vendor=vendor):
                with (
                    patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}),
                    patch("harness.tool_api.request", return_value=empty_call) as request,
                ):
                    search(vendor, "company query", max_results=7)
                body = request.call_args.kwargs["body"]
                self.assertEqual(body["search_depth"], depth)
                self.assertEqual(body["max_results"], 7)
                self.assertEqual(VENDORS[vendor].search_unit_cost_usd, expected_cost)
                if depth == "advanced":
                    self.assertEqual(body["chunks_per_source"], 3)
                else:
                    self.assertNotIn("chunks_per_source", body)

    def test_public_board_native_fetch_response_shapes(self) -> None:
        fixtures = {
            "you_highlights": [{"url": "https://a.test", "title": "A", "markdown": "one"}],
            "tinyfish": {
                "results": [{
                    "url": "https://a.test",
                    "final_url": "https://a.test/final",
                    "title": "A",
                    "text": "one",
                }],
            },
        }
        for vendor, payload in fixtures.items():
            with self.subTest(vendor=vendor):
                page = read_page(vendor, "https://a.test", payload, 12_000)
                self.assertEqual(page["text"], "one")
                self.assertEqual(page["fetch_provider"], VENDORS[vendor].fetch_kind)

    def test_public_board_native_fetch_request_contracts(self) -> None:
        fixtures = {
            "you_highlights": ("YOU_API_KEY", "https://ydc-index.io/v1/contents"),
            "tinyfish": ("TINYFISH_API_KEY", "https://api.fetch.tinyfish.ai"),
        }
        responses = {
            "you_highlights": [{"url": "https://a.test", "markdown": "one"}],
            "tinyfish": {"results": [{"url": "https://a.test", "text": "one"}]},
        }
        for vendor, (env_key, endpoint) in fixtures.items():
            with self.subTest(vendor=vendor):
                vendor_call = VendorCall(
                    status="ok", latency_ms=1, raw_request={}, raw_response=responses[vendor],
                    error=None, attempts=[], cost_usd=None,
                )
                with (
                    patch.dict(os.environ, {env_key: "test-key"}),
                    patch("harness.search_tools._assert_public_url"),
                    patch("harness.tool_api.request", return_value=vendor_call) as request,
                ):
                    result = fetch(vendor, "https://a.test", objective="Find evidence")
                self.assertEqual(result.status, "ok")
                self.assertEqual(request.call_args.kwargs["url"], endpoint)
                self.assertEqual(request.call_args.kwargs["method"], "POST")

        with patch("harness.search_tools.fetch_page", return_value={
            "requested_url": "https://a.test", "final_url": "https://a.test",
            "title": "A", "text": "one", "truncated": False,
            "fetch_provider": "http",
        }) as custom_fetch:
            result = fetch("perplexity", "https://a.test", objective="Find evidence")
        self.assertEqual(result.status, "ok")
        custom_fetch.assert_called_once_with("https://a.test", max_chars=12_000)


if __name__ == "__main__":
    unittest.main()
