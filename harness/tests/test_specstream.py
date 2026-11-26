"""Offline search, native fetch and cost contracts for SpecStream."""
import os
import unittest
from unittest.mock import patch

from harness import search_tools, tool_api

# The reply shapes of POST /v1/web-search and POST /v1/extract: everything sits under "data".
SEARCH_REPLY = {"data": {
    "request_id": "r1", "took_ms": 2400, "price_usd": 0.005,
    "sources": [
        {"url": "https://acme.example/about", "title": "Acme", "snippet": "Acme raised a $5M seed led by Example VC.",
         "published": "2026-03-01"},
        {"url": "https://acme.example/about", "title": "Acme again", "snippet": "duplicate"},
        "not a source",
        {"url": "https://news.example/acme", "title": "Acme seed", "snippet": "Acme, a Y Combinator company"},
    ],
}}
EXTRACT_REPLY = {"data": {
    "request_id": "r2", "took_ms": 1010, "price_usd": 0.0008,
    "results": [{"url": "https://acme.example/about", "status": "ok", "title": "About Acme",
                 "text": "# About Acme\n\nAcme raised a $5M seed.", "published": "2026-03-01", "read_from": "live"}],
}}


def _reply(payload, status="ok"):
    return tool_api.VendorCall(status=status, latency_ms=1, raw_request={}, raw_response=payload,
                               error=None, attempts=[{"attempt": 1, "status_code": 200}], cost_usd=None)


class SpecStreamContracts(unittest.TestCase):
    def test_search_request_parse_and_cost(self):
        with patch.dict(os.environ, {"SPECSTREAM_API_KEY": "test-key"}), \
                patch.object(tool_api, "request", return_value=_reply(SEARCH_REPLY)) as call:
            result = search_tools.search("specstream", "Seed companies backed by Example VC", max_results=10)
        sent = call.call_args.kwargs
        self.assertEqual((sent["method"], sent["url"]), ("POST", "https://api.specstream.ai/v1/web-search"))
        self.assertEqual(sent["body"], {"compact": True, "q": "Seed companies backed by Example VC", "num": 10})
        self.assertEqual(sent["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual([h["url"] for h in result.hits], ["https://acme.example/about", "https://news.example/acme"])
        self.assertEqual(result.hits[0]["snippet"], "Acme raised a $5M seed led by Example VC.")
        self.assertEqual(result.hits[0]["metadata"], {"published": "2026-03-01"})
        self.assertEqual(result.cost_usd, 0.005)

    def test_fetch_reads_extract_results(self):
        with patch.dict(os.environ, {"SPECSTREAM_API_KEY": "test-key"}), \
                patch("harness.search_tools._assert_public_url"), \
                patch.object(tool_api, "request", return_value=_reply(EXTRACT_REPLY)) as call:
            result = search_tools.fetch("specstream", "https://acme.example/about", objective="Who led the seed?")
        sent = call.call_args.kwargs
        self.assertEqual(sent["url"], "https://api.specstream.ai/v1/extract")
        self.assertEqual(sent["body"], {"urls": ["https://acme.example/about"], "format": "markdown",
                                        "max_chars": 12_000, "query": "Who led the seed?"})
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.page["text"], "# About Acme\n\nAcme raised a $5M seed.")
        self.assertEqual(result.page["title"], "About Acme")
        self.assertEqual(result.page["fetch_provider"], "specstream_extract")
        self.assertEqual(result.cost_usd, 0.0008)

    def test_a_page_not_read_is_a_failed_fetch_at_its_stated_cost(self):
        blocked = {"data": {"price_usd": 0, "results": [{"url": "https://acme.example/about", "status": "blocked"}]}}
        with patch.dict(os.environ, {"SPECSTREAM_API_KEY": "test-key"}), \
                patch("harness.search_tools._assert_public_url"), \
                patch.object(tool_api, "request", return_value=_reply(blocked)):
            result = search_tools.fetch("specstream", "https://acme.example/about", objective="q")
        self.assertEqual(result.status, "error")
        self.assertIn("blocked", result.error)
        self.assertEqual(result.cost_usd, 0.0)

    def test_an_error_reply_gives_no_hits_and_no_cost(self):
        failed = {"error": {"code": "unauthorized", "message": "no key"}}
        with patch.dict(os.environ, {"SPECSTREAM_API_KEY": "test-key"}), \
                patch.object(tool_api, "request", return_value=_reply(failed, status="error")):
            result = search_tools.search("specstream", "q", max_results=10)
        self.assertEqual((result.hits, result.cost_usd), ([], 0.0))
        self.assertEqual(search_tools.parse_hits("specstream", failed, 10), [])

    def test_roster(self):
        spec = search_tools.VENDORS["specstream"]
        self.assertIn("specstream", search_tools.DEFAULT_VENDOR_KEYS)
        self.assertEqual((spec.search_unit_cost_usd, spec.fetch_unit_cost_usd), (0.005, 0.0008))
        self.assertEqual(spec.env_keys, ("SPECSTREAM_API_KEY",))


if __name__ == "__main__":
    unittest.main()
