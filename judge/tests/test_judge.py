from __future__ import annotations

import unittest

from judge.leaderboard import build_leaderboard, score_artifact


def _artifact(trial: int, *, correct: bool) -> dict:
    companies = (
        [
            {
                "name": "Acme",
                "domain": "https://www.acme.example/about",
                "cited_urls": ["https://acme.example/about"],
                "evidence": [],
            }
        ]
        if correct
        else []
    )
    return {
        "schema_version": "multi-turn-company-search-run-v1",
        "dataset": {"slug": "test", "content_sha256": "sha256:test"},
        "research_mode": "search_only",
        "vendor_key": "brave",
        "vendor": {"provider_name": "Brave Search", "config_slug": "brave"},
        "case": {
            "case_key": "q-1",
            "question": "Find Acme",
            "gold": [
                {
                    "entity_key": "entity:acme",
                    "name": "Acme, Inc.",
                    "domain": "acme.example",
                    "aliases": ["Acme"],
                }
            ],
        },
        "trial_index": trial,
        "result": {
            "status": "ok",
            "latency_ms": trial * 100,
            "model_turn_count": 2,
            "model_cost_usd": 0.01,
            "searches": [],
            "fetches": [],
        },
        "parsed_companies": companies,
        "parse_error": None,
    }


class JudgeTest(unittest.TestCase):
    def test_domain_and_alias_matching(self) -> None:
        score = score_artifact(_artifact(1, correct=True))
        self.assertEqual(score["true_positive"], 1)
        self.assertEqual(score["false_positive"], 0)
        self.assertEqual(score["f1"], 1.0)

    def test_mean_and_sample_sd_are_across_trial_means(self) -> None:
        result = build_leaderboard(
            [_artifact(1, correct=True), _artifact(2, correct=True), _artifact(3, correct=False)]
        )
        row = result["boards"]["search_only"][0]
        self.assertEqual(row["f1"], {"mean_pct": 66.67, "sd_pp": 57.74})
        self.assertEqual(row["rank"], 1)
        self.assertEqual(result["aggregation"]["standard_deviation_unit"], "percentage points")

    def test_incomplete_trials_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "trial indexes"):
            build_leaderboard([_artifact(1, correct=True)], expected_trials=3)

    def test_a_run_without_a_price_leaves_the_tool_cost_unknown(self) -> None:
        artifacts = [_artifact(trial, correct=True) for trial in (1, 2, 3)]
        artifacts[2]["result"]["fetches"] = [{"call": {"cost_usd": None}}]
        row = build_leaderboard(artifacts)["boards"]["search_only"][0]
        self.assertIsNone(row["mean_cost_usd"])
        self.assertEqual(row["unpriced_run_count"], 1)

    def test_the_tool_that_stopped_early_is_named(self) -> None:
        artifacts = []
        for vendor, cases in (("brave", ("q-1",)), ("serp", ("q-1", "q-2"))):
            for case_key in cases:
                for trial in (1, 2, 3):
                    artifact = _artifact(trial, correct=True)
                    artifact["vendor_key"] = vendor
                    artifact["case"]["case_key"] = case_key
                    artifacts.append(artifact)
        with self.assertRaisesRegex(ValueError, r"^search_only/brave is missing 1 of 2 questions$"):
            build_leaderboard(artifacts)

    def test_a_board_with_stopped_trials_is_refused(self) -> None:
        artifacts = [_artifact(trial, correct=True) for trial in (1, 2, 3)]
        artifacts[1]["result"].update(status="error", stop_reason="model call failed")
        with self.assertRaisesRegex(ValueError, "search_only/brave stopped early"):
            build_leaderboard(artifacts)

    def test_an_answer_without_accents_matches_an_accented_list_name(self) -> None:
        artifact = _artifact(1, correct=True)
        artifact["case"]["gold"][0].update(name="Jüsto", domain="justo.mx", aliases=[])
        artifact["parsed_companies"][0].update(name="Justo", domain=None)
        self.assertEqual(score_artifact(artifact)["true_positive"], 1)


if __name__ == "__main__":
    unittest.main()
