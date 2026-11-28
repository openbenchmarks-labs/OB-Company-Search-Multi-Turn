from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.agent import AgentConfig, AgentResult, run_agent
from harness.dataset import SCHEMA_VERSION, content_sha256, entity_key
from harness.runner import RunnerConfig, execute, runner_plan
from harness.tool_api import VendorCall


def _dataset(path: Path, case_count: int = 1) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"slug": "test-dataset", "name": "Test dataset"},
        "source": {"type": "test"},
        "gold_release": {"version": 1, "source": "generated"},
        "cases": [
            {
                "case_key": f"q-{number}",
                "question": f"Find companies founded after 202{number}",
                "family": "other",
                "constraint_count": 1,
                "constraints": [f"founded after 202{number}"],
                "predicates": {},
                "sort_order": number,
                "gold": [
                    {"entity_key": entity_key("Acme"), "name": "Acme", "domain": "acme.example", "aliases": []},
                ],
            }
            for number in range(1, case_count + 1)
        ],
    }
    payload["content_sha256"] = content_sha256(payload)
    path.write_text(json.dumps(payload))
    return payload


class RunnerTest(unittest.TestCase):
    def test_plan_is_local_and_counts_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset.json"
            _dataset(dataset)
            config = RunnerConfig(
                dataset_path=dataset,
                output_dir=root / "runs",
                vendor_keys=("brave",),
                trial_count=3,
                research_mode="search_only",
                agent=AgentConfig(max_fetches=0, max_fetches_per_turn=None),
            )
            plan = runner_plan(config)
            self.assertEqual(plan["planned_agent_runs"], 3)
            self.assertIn("local JSON only", plan["writes"])
            self.assertFalse((root / "runs").exists())

    def test_execute_writes_resumable_trial_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset.json"
            _dataset(dataset)
            config = RunnerConfig(
                dataset_path=dataset,
                output_dir=root / "runs",
                vendor_keys=("brave",),
                trial_count=2,
                research_mode="search_only",
                agent=AgentConfig(max_fetches=0, max_fetches_per_turn=None),
            )
            response = json.dumps(
                {
                    "companies": [
                        {
                            "name": "Acme",
                            "domain": "acme.example",
                            "cited_urls": ["https://acme.example/about"],
                            "evidence": [
                                {"url": "https://acme.example/about", "claim": "Founded in 2021"}
                            ],
                        }
                    ]
                }
            )

            def fake_run(question, *, vendor_key, client, config):
                return AgentResult(question, vendor_key, response, "ok", None, 10)

            with patch("harness.runner.run_agent", side_effect=fake_run) as run:
                execute(config, object())
                execute(config, object())
            self.assertEqual(run.call_count, 2)
            paths = sorted((root / "runs").rglob("trial-*.json"))
            self.assertEqual(len(paths), 2)
            artifact = json.loads(paths[0].read_text())
            self.assertEqual(artifact["dataset"]["slug"], "test-dataset")
            self.assertEqual(artifact["parsed_companies"][0]["name"], "Acme")

    def test_search_only_rejects_fetch_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset = Path(temporary) / "dataset.json"
            _dataset(dataset)
            with self.assertRaisesRegex(ValueError, "max_fetches=0"):
                runner_plan(
                    RunnerConfig(
                        dataset_path=dataset,
                        vendor_keys=("brave",),
                        research_mode="search_only",
                    )
                )

    def test_no_search_setup_answers_without_tools(self) -> None:
        client = FakeClient([FakeResponse({"companies": []})])
        result = run_agent("Find companies", vendor_key="no_search", client=client, config=AgentConfig())
        self.assertEqual(result.status, "ok")
        self.assertNotIn("tools", client.responses.requests[0])

    def test_credit_errors_stop_a_tool_but_an_outage_does_not(self) -> None:
        failures = {
            "brave": (402, "HTTP 402: out of credit"),
            "tavily_basic": (432, "HTTP 432: plan limit exceeded"),
            "serp": (503, "HTTP 503: unavailable"),
        }

        def failing_search(vendor_key, query, *, max_results):
            status, error = failures[vendor_key]
            return VendorCall("error", 1, {}, {}, error, [{"attempt": 1, "status_code": status}], 0.0, hits=[])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _two_question_config(root, tuple(failures))
            with patch("harness.agent.search", side_effect=failing_search):
                summary = execute(config, SearchThenAnswerClient())
            ran = {vendor: len(list((root / "runs").rglob(f"search_only/{vendor}/*/trial-*.json"))) for vendor in failures}
        self.assertEqual(ran, {"brave": 1, "tavily_basic": 1, "serp": 2})
        by_vendor = {row["vendor"]: row for row in summary["vendors"]}
        self.assertEqual([by_vendor[v]["complete"] for v in failures], [False, False, True])
        self.assertIn("q-1", by_vendor["brave"]["stopped"])

    def test_a_model_failure_stops_the_tool_and_the_resumed_run_retries_it(self) -> None:
        class DeadModel:
            def __init__(self) -> None:
                self.responses = self

            def create(self, **request: object) -> None:
                raise ConnectionError("model provider unreachable")

        found = VendorCall("ok", 1, {}, {}, None, [{"attempt": 1, "status_code": 200}], 0.005, hits=[])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = _two_question_config(root, ("brave",))
            first = execute(config, DeadModel())
            with patch("harness.agent.search", return_value=found):
                second = execute(config, SearchThenAnswerClient())
            statuses = sorted(json.loads(path.read_text())["result"]["status"] for path in (root / "runs").rglob("trial-*.json"))
        self.assertEqual((first["vendors"][0]["complete"], second["vendors"][0]["complete"]), (False, True))
        self.assertEqual(statuses, ["ok", "ok"])


def _two_question_config(root: Path, vendors: tuple[str, ...]) -> RunnerConfig:
    dataset = root / "dataset.json"
    _dataset(dataset, case_count=2)
    return RunnerConfig(
        dataset_path=dataset,
        output_dir=root / "runs",
        vendor_keys=vendors,
        trial_count=1,
        research_mode="search_only",
        agent=AgentConfig(max_fetches=0, max_fetches_per_turn=None),
    )


class ObjectiveSearchTest(unittest.TestCase):
    def test_parallel_agent_writes_objective_and_search_query(self) -> None:
        tool_call = [{
            "type": "function_call", "name": "web_search", "call_id": "call-1",
            "arguments": json.dumps({"objective": "Find YC fintech companies.", "search_query": "YC fintech"}),
        }]
        vendor_call = VendorCall("ok", 5, {}, {}, None, [], 0.005, hits=[])
        for vendor_key in ("parallel_advanced", "parallel_fast"):
            with self.subTest(vendor=vendor_key):
                client = FakeClient([FakeResponse({}, tool_call), FakeResponse({"companies": []})])
                with patch("harness.agent.search", return_value=vendor_call) as search_mock:
                    result = run_agent("Find companies", vendor_key=vendor_key, client=client, config=AgentConfig())
                self.assertEqual(result.status, "ok", result.error)
                tool = client.responses.requests[0]["tools"][0]
                self.assertEqual(tool["parameters"]["required"], ["objective", "search_query"])
                search_mock.assert_called_once_with(
                    vendor_key, "YC fintech", max_results=AgentConfig().max_results,
                    objective="Find YC fintech companies.",
                )
                self.assertEqual(result.searches[0].query, "YC fintech")
                self.assertEqual(result.objective_fallbacks, [])
        client = FakeClient([FakeResponse({"companies": []})])
        run_agent("Find companies", vendor_key="brave", client=client, config=AgentConfig())
        self.assertEqual(client.responses.requests[0]["tools"][0]["parameters"]["required"], ["query"])

    def test_parallel_agent_writes_fetch_objective_other_tools_use_question(self) -> None:
        search_hit = VendorCall("ok", 5, {}, {}, None, [], 0.005, hits=[{"url": "https://a.test/page"}])
        page = VendorCall("ok", 5, {}, {}, None, [], 0.001)
        cases = (
            ("parallel_advanced", {"objective": "Find X.", "search_query": "x"},
             {"url": "https://a.test/page", "objective": "Funding round size for X."}, "Funding round size for X."),
            ("parallel_fast", {"objective": "Find X.", "search_query": "x"},
             {"url": "https://a.test/page", "objective": ""}, "Find companies"),
            ("exa_deep", {"query": "x"}, {"url": "https://a.test/page"}, "Find companies"),
        )
        for vendor_key, search_args, fetch_args, expected in cases:
            with self.subTest(vendor=vendor_key):
                client = FakeClient([
                    FakeResponse({}, [{"type": "function_call", "name": "web_search", "call_id": "s1",
                                       "arguments": json.dumps(search_args)}]),
                    FakeResponse({}, [{"type": "function_call", "name": "web_fetch", "call_id": "f1",
                                       "arguments": json.dumps(fetch_args)}]),
                    FakeResponse({"companies": []}),
                ])
                with (
                    patch("harness.agent.search", return_value=search_hit),
                    patch("harness.agent.fetch", return_value=page) as fetch_mock,
                ):
                    result = run_agent("Find companies", vendor_key=vendor_key, client=client, config=AgentConfig())
                self.assertEqual(result.status, "ok", result.error)
                fetch_mock.assert_called_once_with(vendor_key, "https://a.test/page", objective=expected)
                self.assertEqual(
                    client.responses.requests[0]["tools"][1]["parameters"]["required"],
                    ["url", "objective"] if vendor_key.startswith("parallel_") else ["url"],
                )
                if vendor_key == "parallel_fast":  # empty fetch objective: flagged and stored with the run
                    self.assertEqual(result.objective_fallbacks, [{
                        "tool": "web_fetch", "turn_index": 2, "call_index": 1,
                        "target": "https://a.test/page", "stand_in": "question",
                    }])
                    self.assertEqual(result.raw_model_payload()["objective_fallbacks"], result.objective_fallbacks)
                else:
                    self.assertEqual(result.objective_fallbacks, [])
                    self.assertNotIn("objective_fallbacks", result.raw_model_payload())


class SearchThenAnswerClient:
    """Searches once, then answers after it sees the search result; safe to share across threads."""

    def __init__(self) -> None:
        self.responses = self

    def create(self, **request: object) -> FakeResponse:
        searched = any(isinstance(item, dict) and item.get("type") == "function_call_output" for item in request["input"])
        if searched:
            return FakeResponse({"companies": []})
        return FakeResponse({}, [{
            "type": "function_call", "name": "web_search", "call_id": "call-1",
            "arguments": json.dumps({"query": "company query"}),
        }])


class FakeUsage:
    input_tokens = 100
    input_tokens_details = None
    output_tokens = 20


class FakeResponse:
    def __init__(self, payload: dict, output: list[dict] | None = None) -> None:
        self.output = output or []
        self.output_text = json.dumps(payload) if not self.output else ""
        self.usage = FakeUsage()

    def model_dump(self, **_: object) -> dict:
        return {"output": [], "output_text": self.output_text}


class FakeResponses:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.requests: list[dict] = []
        self.responses = list(responses or [])

    def create(self, **request: object) -> FakeResponse:
        self.requests.append(request)
        return self.responses.pop(0) if self.responses else FakeResponse({"companies": []})


class FakeClient:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = FakeResponses(responses)


if __name__ == "__main__":
    unittest.main()
