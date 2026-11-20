# harness

Runs the benchmark and calls the search APIs. No grading code lives here.

- `run.py` — Command-line runner. Prints the run plan, and runs it only with `--execute --confirm-paid`.
- `runner.py` — Runs every question for every tool and trial, and saves one result file per run under `runs/`.
- `agent.py` — The research agent loop: the model searches, reads pages, and returns a list of companies.
- `model_client.py` — Builds the OpenAI client from `OPENAI_API_KEY`.
- `search_tools.py` — Loads every tool from `tools/*.yaml` and sends each search or page fetch to that tool's adapter.
- `tool_api.py` — Shared pieces for adapters: the setup record, the HTTP request with retries, and API keys stripped from logs.
- `adapters/` — One file per search API with its request and response handling.
- `custom_fetch.py` — Page reader for tools without their own fetch API. Tries plain HTTP first, then a headless browser, and blocks private addresses.
- `dataset.py` — Loads the question file and checks it is well formed.
- `answer_parser.py` — Turns the agent's final answer into a clean list of companies.
- `tests/` — Offline tests for the runner, the agent, and every adapter.
