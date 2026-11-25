"""Offline search and native fetch contracts for You highlights/core."""
import json
import os
import unittest
from unittest.mock import patch

from harness import search_tools, tool_api
from harness.agent import AgentConfig, run_agent


class YouContracts(unittest.TestCase):
    def test_search_and_separate_contents_fetch(self):
        payload = {"results": {"web": [{"url": "https://example.com", "snippets": ["fallback"],
                    "contents": {"highlights": ["Relevant evidence"]}}]}}
        for arm in ("you_highlights", "you_highlights_core"):
            with self.subTest(arm=arm), patch.dict(os.environ, {"YOU_API_KEY": "test-key"}):
                body = {"query": "Unchanged question?", "count": 8,
                        "extraction": {"extraction_mode": "highlights"}}
                if arm.endswith("_core"):
                    body["knowledge"] = "core"
                call_result = tool_api.VendorCall(status="ok", latency_ms=1, raw_request={}, raw_response=payload,
                                                 error=None, attempts=[], cost_usd=None)
                with patch.object(tool_api, "request", return_value=call_result) as call:
                    result = search_tools.search(arm, "Unchanged question?", max_results=8)
                    self.assertEqual(result.hits[0]["snippet"], "Relevant evidence")
                    self.assertEqual(call.call_args.kwargs["body"], body)
                    self.assertEqual(call.call_args.kwargs["url"], "https://ydc-index.io/v1/search")
                call_result = tool_api.VendorCall(status="ok", latency_ms=1, raw_request={},
                    raw_response=[{"url": "https://example.com", "markdown": "Page"}],
                    error=None, attempts=[], cost_usd=None)
                with patch.object(tool_api, "request", return_value=call_result) as call:
                    result = search_tools.fetch(arm, "https://example.com", objective="question")
                    self.assertEqual(result.page["text"], "Page")
                    self.assertEqual(call.call_args.kwargs["url"], "https://ydc-index.io/v1/contents")
                    self.assertEqual(call.call_args.kwargs["body"], {
                        "urls": ["https://example.com"], "formats": ["markdown", "metadata"]})
                self.assertIn(arm, search_tools.DEFAULT_VENDOR_KEYS)
                self.assertTrue(search_tools.VENDORS[arm].native_fetch)

    def test_core_knowledge_answers_reach_the_agent(self):
        payload = {"results": {
            "web": [{"url": "https://example.com", "contents": {"highlights": ["Web evidence"]}}],
            "knowledge": [{"type": "answer", "title": "Acme funding", "description": "Acme raised a $5M seed in 2023.",
                           "as_of": "2026-11-01", "attribution": [{"name": "Licensed provider"}]}],
        }}
        search_reply = tool_api.VendorCall("ok", 1, {}, payload, None, [{"attempt": 1, "status_code": 200}], None)
        client = _SearchOnceClient()
        with patch.dict(os.environ, {"YOU_API_KEY": "test-key"}), patch.object(tool_api, "request", return_value=search_reply):
            result = run_agent("Find funded companies", vendor_key="you_highlights_core", client=client,
                               config=AgentConfig(max_fetches=0, max_fetches_per_turn=None))
        self.assertEqual(result.status, "ok")
        seen = [json.loads(item["output"]) for item in client.inputs[-1] if item.get("type") == "function_call_output"]
        self.assertEqual(seen[0]["knowledge"][0]["answer"], "Acme raised a $5M seed in 2023.")
        self.assertEqual(seen[0]["knowledge"][0]["providers"], ["Licensed provider"])

    def test_plain_you_not_in_roster(self):
        self.assertNotIn("you", search_tools.VENDORS)


class _Response:
    def __init__(self, output: list[dict], text: str = "") -> None:
        self.output, self.output_text, self.usage = output, text, None

    def model_dump(self, **_: object) -> dict:
        return {"output_text": self.output_text}


class _SearchOnceClient:
    """Asks for one search, then answers; keeps a copy of each request's input."""

    def __init__(self) -> None:
        self.responses, self.inputs = self, []

    def create(self, **request: object) -> _Response:
        self.inputs.append(list(request["input"]))
        if len(self.inputs) == 1:
            return _Response([{"type": "function_call", "name": "web_search", "call_id": "c1",
                               "arguments": json.dumps({"query": "acme funding"})}])
        return _Response([], json.dumps({"companies": []}))


if __name__ == "__main__":
    unittest.main()
