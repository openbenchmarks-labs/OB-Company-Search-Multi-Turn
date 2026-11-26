# harness

Runs the benchmark and calls the search APIs. No grading code lives here.

- `run.py` — Command-line runner. Prints the run plan, and runs it only with `--execute --confirm-paid`.
- `runner.py` — Runs every question for every tool and trial, and saves one result file per run under `runs/`. A failed question is saved and scores zero. A tool stops early when a failure would repeat on every later trial: its key refused or its account out of credit (HTTP 401, 402, or Tavily's 432 and 433), or the model call failing. The run then reports the tool incomplete and exits with status 3, the board refuses to build, and running the same command again retries the stopped trials.
- `agent.py` — The research agent loop: the model searches, reads pages, and returns a list of companies.
- `model_client.py` — Builds the model client: Azure OpenAI from `AZURE_OPENAI_BASE_URL` and `AZURE_OPENAI_API_KEY` by default, or OpenAI when only `OPENAI_API_KEY` is set.
- `search_tools.py` — Loads every tool from `tools/*.yaml` and sends each search or page fetch to that tool's adapter.
- `tool_api.py` — Shared pieces for adapters: the setup record, the HTTP request with retries, and API keys stripped from logs.
- `adapters/` — One file per search API with its request and response handling.
- `custom_fetch.py` — Page reader for tools without their own fetch API. Tries plain HTTP first, then a headless browser, and blocks private addresses.
- `dataset.py` — Loads the question file, or a Hugging Face copy of a split, and checks it is well formed.
- `answer_parser.py` — Turns the agent's final answer into a clean list of companies.
- `tests/` — Offline tests for the runner, the agent, and every adapter.
