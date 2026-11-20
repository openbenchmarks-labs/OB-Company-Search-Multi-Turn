import os
import unittest
from unittest.mock import patch

from harness import search_tools, tool_api
from harness.adapters import nimble


class NimbleTests(unittest.TestCase):
    def test_search_and_extract(self):
        for depth in ("lite", "standard"):
            key = f"nimble_{depth}"
            raw = tool_api.VendorCall("ok", 1, {}, {"results": [{"url": "https://a.test", "description": "evidence", "content": "FULL PAGE"}, {"url": "https://a.test"}, {}]}, None, [], None)
            with patch.dict(os.environ, {"NIMBLE_API_KEY": "test", "NIMBLE_EXTRACT_USD_PER_REQUEST": ""}), patch.object(tool_api, "request", return_value=raw) as call, patch.object(search_tools, "_assert_public_url"):
                result = search_tools.search(key, "query", max_results=1)
                self.assertEqual(call.call_args.kwargs["body"], {"query": "query", "search_depth": depth, "full_content": False, "focus": "general", "max_results": 1})
                self.assertEqual(result.hits[0]["snippet"], "evidence")
                self.assertEqual(result.cost_usd, {"lite": 0.0011, "standard": 0.005}[depth])
                raw.raw_response = {"status": "success", "data": {"markdown": "abcdef"}}
                result = search_tools.fetch(key, "https://a.test", objective="research", max_chars=3)
                self.assertEqual(call.call_args.kwargs["url"], nimble.EXTRACT_URL)
                self.assertEqual(call.call_args.kwargs["body"], {"url": "https://a.test", "formats": ["markdown"]})
                self.assertEqual(result.page["text"], "abc")
                self.assertTrue(result.page["truncated"])
                self.assertIsNone(result.cost_usd)
                with patch.dict(os.environ, {"NIMBLE_EXTRACT_USD_PER_REQUEST": "0.002"}):
                    self.assertEqual(search_tools.fetch(key, "https://a.test", objective="research").cost_usd, .002)
