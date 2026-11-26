from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from harness.search_tools import (
    VENDORS,
    capability_inventory,
    fetch,
    parse_hits,
    read_page,
    search,
)
from harness.tool_api import VendorCall, split_site_filters


class SearchToolsTest(unittest.TestCase):
    def test_parallel_modes_use_source_policy_for_site_queries(self) -> None:
        fixture = {"results": [{"url": "https://example.test", "title": "Example", "excerpts": ["Evidence"]}]}
        empty_call = VendorCall(
            status="ok", latency_ms=1, raw_request={}, raw_response=fixture,
            error=None, attempts=[], cost_usd=None,
        )
        query = "funding site:Crunchbase.com/org site:https://techcrunch.com/startups -site:reddit.com"
        self.assertEqual(
            split_site_filters(query),
            ("funding -site:reddit.com", ["crunchbase.com", "techcrunch.com"]),
        )
        self.assertEqual(split_site_filters("best website:builder startups"), ("best website:builder startups", []))
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
                "no_search", "context", "nimble_lite", "nimble_standard", "brave", "exa_deep", "exa_instant", "firecrawl", "linkup_fast",
                "linkup_standard", "parallel_advanced", "parallel_basic",
                "parallel_fast", "parallel_turbo", "seltz_companies", "serp",
                "tavily_advanced", "tavily_basic", "you_highlights", "you_highlights_core", "tinyfish", "perplexity",
                "tako", "keenable_pro", "keenable_realtime",
            },
        )
        capabilities = {row["vendor"]: row for row in capability_inventory()}
        for key in (
            "context", "exa_deep", "exa_instant", "firecrawl", "linkup_fast",
            "linkup_standard", "parallel_advanced", "parallel_basic",
            "parallel_fast", "parallel_turbo", "tavily_advanced", "tavily_basic", "you_highlights", "you_highlights_core", "tinyfish",
            "perplexity", "tako",
        ):
            self.assertTrue(capabilities[key]["native_fetch"])
        for key in ("brave", "seltz_companies", "serp", "keenable_pro", "keenable_realtime"):
            self.assertFalse(capabilities[key]["native_fetch"])
            self.assertTrue(capabilities[key]["custom_fetch"])
        self.assertTrue(all(row["fetch_available"] for row in capabilities.values() if row["search"]))
        self.assertFalse(capabilities["no_search"]["search"] or capabilities["no_search"]["fetch_available"])

    def test_every_vendor_response_shape_produces_ranked_hits(self) -> None:
        fixtures = {
            "context": {"results": [{"url": "https://a.test", "title": "A", "description": "fallback",
                                      "highlights": {"code": "SUCCESS", "highlights": ["one"]}}]},
            "brave": {"web": {"results": [{"url": "https://a.test", "title": "A", "description": "one"}]}},
            "exa_deep": {"results": [{"url": "https://a.test", "title": "A", "highlights": ["one"]}]},
            "exa_instant": {"results": [{"url": "https://a.test", "title": "A", "highlights": ["one"]}]},
            "firecrawl": {"data": {"web": [{"url": "https://a.test", "title": "A", "description": "one"}]}},
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
            "tako": {"web_results": [{"url": "https://a.test", "title": "A", "snippet": "one"}]},
            "keenable_pro": {"results": [{"url": "https://a.test", "title": "A", "snippet": "one"}]},
        }
        fixtures["you_highlights_core"] = fixtures["you_highlights"]
        fixtures["nimble_lite"] = {"results": [{"url": "https://a.test", "title": "A", "description": "one"}]}
        fixtures["nimble_standard"] = fixtures["nimble_lite"]
        fixtures["keenable_realtime"] = fixtures["keenable_pro"]
        self.assertEqual(set(fixtures), {key for key, spec in VENDORS.items() if spec.web_search})
        for vendor, payload in fixtures.items():
            with self.subTest(vendor=vendor):
                self.assertEqual(parse_hits(vendor, payload, 10)[0]["url"], "https://a.test")
                if vendor == "context":
                    self.assertEqual(parse_hits(vendor, payload, 10)[0]["snippet"], "one")

    def test_an_unreadable_search_reply_is_a_failed_search_not_a_crash(self) -> None:
        reply = VendorCall(
            status="ok", latency_ms=1, raw_request={}, raw_response={"results": "not a list"},
            error=None, attempts=[], cost_usd=None,
        )
        with patch("harness.adapters.tavily.search", return_value=reply):
            call = search("tavily_basic", "funding", max_results=10)
        self.assertEqual((call.status, call.hits), ("error", []))
        self.assertIn("unreadable search reply", call.error)

    def test_public_board_search_request_contracts(self) -> None:
        fixtures = {
            "you_highlights": ("YOU_API_KEY", "https://ydc-index.io/v1/search", "POST"),
            "tinyfish": ("TINYFISH_API_KEY", "https://api.search.tinyfish.ai", "GET"),
            "perplexity": ("PERPLEXITY_API_KEY", "https://api.perplexity.ai/search", "POST"),
            "tako": ("TAKO_API_KEY", "https://tako.com/api/v3/search", "POST"),
            "keenable_pro": ("KEENABLE_API_KEY", "https://api.keenable.ai/v1/search", "POST"),
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

    def test_site_queries_follow_each_tools_documented_rule(self) -> None:
        empty_call = VendorCall("ok", 1, {}, {"results": []}, None, [], None)
        query = "seed rounds site:www.Crunchbase.com/organization"
        moved = ("seed rounds", ["crunchbase.com"])
        for vendor, env_key, query_key, domains_key, expected in (
            ("tavily_basic", "TAVILY_API_KEY", "query", "include_domains", moved),
            ("tavily_advanced", "TAVILY_API_KEY", "query", "include_domains", moved),
            ("linkup_fast", "LINKUP_API_KEY", "q", "includeDomains", moved),
            ("linkup_standard", "LINKUP_API_KEY", "q", "includeDomains", moved),
            ("nimble_lite", "NIMBLE_API_KEY", "query", "include_domains", moved),
            ("nimble_standard", "NIMBLE_API_KEY", "query", "include_domains", moved),
            ("perplexity", "PERPLEXITY_API_KEY", "query", "search_domain_filter", moved),
            ("tinyfish", "TINYFISH_API_KEY", "query", "include_domains", ("seed rounds", "crunchbase.com")),
            ("keenable_pro", "KEENABLE_API_KEY", "query", "include_domains", (query, None)),
            ("exa_deep", "EXA_API_KEY", "query", "includeDomains", (query, None)),
            ("you_highlights", "YOU_API_KEY", "query", "include_domains", (query, None)),
        ):
            with self.subTest(vendor=vendor):
                with (
                    patch.dict(os.environ, {env_key: "test-key"}),
                    patch("harness.tool_api.request", return_value=empty_call) as request,
                ):
                    search(vendor, query, max_results=7)
                sent = request.call_args.kwargs.get("body") or request.call_args.kwargs["params"]
                self.assertEqual((sent[query_key], sent.get(domains_key)), expected)
                self.assertNotIn("site_operator_policy", sent)

    def test_tako_sends_the_board_request_with_site_hosts_in_include_domains(self) -> None:
        empty_call = VendorCall("ok", 1, {}, {"web_results": []}, None, [], None)
        with (
            patch.dict(os.environ, {"TAKO_API_KEY": "test-key"}),
            patch("harness.tool_api.request", return_value=empty_call) as request,
        ):
            search("tako", "seed rounds site:crunchbase.com", max_results=7)
        self.assertEqual(request.call_args.kwargs["body"], {
            "query": "seed rounds", "effort": "fast",
            "sources": {"web": {"count": 7, "highlights": True, "include_domains": ["crunchbase.com"]}},
        })

    def test_both_tavily_setups_read_pages_with_advanced_extract(self) -> None:
        page_call = VendorCall("ok", 1, {}, {"results": [{"url": "https://a.test", "raw_content": "one"}]}, None, [], None)
        for vendor in ("tavily_basic", "tavily_advanced"):
            with self.subTest(vendor=vendor):
                with (
                    patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}),
                    patch("harness.search_tools._assert_public_url"),
                    patch("harness.tool_api.request", return_value=page_call) as request,
                ):
                    result = fetch(vendor, "https://a.test", objective="Find evidence")
                self.assertEqual(request.call_args.kwargs["body"]["extract_depth"], "advanced")
                self.assertEqual(result.cost_usd, 0.0032)

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
            "perplexity": {"results": [{
                "url": "https://a.test", "markdown": "one", "status": {"type": "ok", "status_code": 200},
                "metadata": {"source_url": "https://a.test/final", "title": "A"},
            }]},
            "tinyfish": {
                "results": [{
                    "url": "https://a.test",
                    "final_url": "https://a.test/final",
                    "title": "A",
                    "text": "one",
                }],
            },
            "tako": {"contents": [{"source_url": "https://a.test", "data": "one"}]},
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
            "perplexity": ("PERPLEXITY_API_KEY", "https://api.perplexity.ai/v1/context"),
            "tako": ("TAKO_API_KEY", "https://tako.com/api/v1/contents"),
        }
        responses = {
            "you_highlights": [{"url": "https://a.test", "markdown": "one"}],
            "tinyfish": {"results": [{"url": "https://a.test", "text": "one"}]},
            "perplexity": {"results": [{"url": "https://a.test", "markdown": "one", "status": {"type": "ok"}}]},
            "tako": {"contents": [{"source_url": "https://a.test", "data": "one"}]},
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
            result = fetch("brave", "https://a.test", objective="Find evidence")
        self.assertEqual(result.status, "ok")
        custom_fetch.assert_called_once_with("https://a.test", max_chars=12_000)


if __name__ == "__main__":
    unittest.main()
