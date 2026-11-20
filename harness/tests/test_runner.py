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


def _dataset(path: Path) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"slug": "test-dataset", "name": "Test dataset"},
        "source": {"type": "test"},
        "gold_release": {"version": 1, "source": "generated"},
        "cases": [
            {
                "case_key": "q-1",
                "question": "Find companies founded after 2020",
                "family": "other",
                "constraint_count": 1,
                "constraints": ["founded after 2020"],
                "predicates": {},
                "sort_order": 1,
                "gold": [
                    {"entity_key": entity_key("Acme"), "name": "Acme", "domain": "acme.example", "aliases": []},
                ],
            }
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

    def test_perplexity_context_size_follows_research_mode(self) -> None:
        tool_call = [{
            "type": "function_call", "name": "web_search", "call_id": "call-1",
            "arguments": json.dumps({"query": "focused company query"}),
        }]
        vendor_call = VendorCall("ok", 5, {}, {}, None, [], 0.005, hits=[])
        for config, expected in (
            (AgentConfig(), "high"),
            (AgentConfig(max_fetches=0, max_fetches_per_turn=None), "low"),
        ):
            with self.subTest(context_size=expected):
                client = FakeClient([FakeResponse({}, tool_call), FakeResponse({"companies": []})])
                with patch("harness.agent.search", return_value=vendor_call) as search_mock:
                    result = run_agent(
                        "Find companies",
                        vendor_key="perplexity",
                        client=client,
                        config=config,
                    )
                self.assertEqual(result.status, "ok")
                search_mock.assert_called_once_with(
                    "perplexity",
                    "focused company query",
                    max_results=10,
                    search_context_size=expected,
                )


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
