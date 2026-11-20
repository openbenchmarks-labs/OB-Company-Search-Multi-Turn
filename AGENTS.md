# AGENTS.md — OB-Company-Search-Multi-Turn

Quick navigation guide for coding agents working in `OB-Company-Search-Multi-Turn`.

## Structure (Zero Overlap)

| Folder | Owns | Files |
|---|---|---|
| **`data/`** | Question file format | `data/README.md` |
| **`harness/`** | Execution only: CLI runner, agent loop, tool loading, search adapters, page fetch, dataset loading | `harness/run.py`, `harness/runner.py`, `harness/agent.py`, `harness/search_tools.py`, `harness/tool_api.py`, `harness/adapters/<tool>.py`, `harness/custom_fetch.py`, `harness/dataset.py`, `harness/answer_parser.py`, `harness/model_client.py`, `harness/tests/` |
| **`tools/`** | Tool setups & pricing (one file per tool for clean PRs) | `tools/<tool>.yaml` |
| **`judge/`** | Grading only: company matching, scores, board | `judge/leaderboard.py`, `judge/tests/` |

Benchmark order & win condition live at the root in `benchmark.yaml`.

## Commands

```sh
# Offline tests (no API keys)
uv venv && uv pip install -r requirements.txt
.venv/bin/python -B -m unittest

# Print a run plan; paid runs also need --execute --confirm-paid
.venv/bin/python -m harness.run --dataset <questions.json>

# Build the board from saved runs
.venv/bin/python -m judge.leaderboard --runs runs
```

## Guidelines

- **Keep folders strictly separated:** Question format in `data/`; execution in `harness/`; per-tool setups and prices in `tools/<tool>.yaml`; grading in `judge/`.
- **Adding or tuning a tool:** Edit `tools/<tool>.yaml`. A new search API also needs `harness/adapters/<tool>.py` and one line in `harness/search_tools.py`. Then run the offline tests.
- **Tests sit next to their code:** `harness/tests/` and `judge/tests/`; `python -m unittest` runs both.
- **No secrets or raw run logs in git:** Keep API keys in `.env` and run outputs in `runs/` (both gitignored).
- **Consistent terminology:** Use `tool`, `setup`, `question`, `ground truth`, `judge`, `board`.
