# OB-Company-Search-Multi-Turn

Open, independent benchmark of web search APIs for research agents: which search API helps a multi-turn agent find and verify companies that match several criteria at once, such as investor, accelerator, funding and location. The agent, model and search budget stay fixed; only the search configuration changes. Search APIs with a setup here: Brave, Context, Exa, Firecrawl, Keenable, Linkup, Nimble, Parallel, Perplexity, Seltz, SERP, SpecStream, Tavily, TinyFish and You.com.

**Live leaderboard:** [openbenchmarks.com/multi-turn-company-search](https://openbenchmarks.com/multi-turn-company-search) · **Public dataset:** [`openbenchmarks/OB-Company-Websearch`](https://huggingface.co/datasets/openbenchmarks/OB-Company-Websearch)

Published and maintained by **[OpenBenchmarks Labs](https://openbenchmarks.com)**.

## Methodology

Each question asks a multi-turn research agent to discover and verify a set of companies that jointly satisfy multiple constraints (spanning investor, accelerator, funding, and other firmographic predicates).

- **Two boards:** **Search only** and **Search + fetch** are evaluated separately.
- **Fixed protocol:** Every tool runs behind the same research agent loop (`harness/agent.py`), model, and search budget.
- **Scoring:** `judge/leaderboard.py` matches each returned company to ground truth by domain or canonical name/alias and computes precision, recall, F1, exact-set accuracy, latency, and cost across trials.

## Tools evaluated

15 search tools configured in [`tools/`](tools/README.md), plus a no-search baseline (`none`):

`brave`, `context`, `exa`, `firecrawl`, `keenable`, `linkup`, `nimble`, `parallel`, `perplexity`, `seltz`, `serp`, `specstream`, `tavily`, `tinyfish`, `you`

## Dataset

No question files are committed to this repository.

- **Public split:** Published on Hugging Face at [`openbenchmarks/OB-Company-Websearch`](https://huggingface.co/datasets/openbenchmarks/OB-Company-Websearch).
- **Held-out split:** The private evaluation set used for the published leaderboard stays private so tools cannot train on it. Pass your dataset file with `--dataset <file>.json` (validated against `content_sha256` before any run starts).

See [`data/README.md`](data/README.md) for the complete dataset schema.

## Repository structure

- [`data/`](data/README.md): Dataset file schema and integrity rules (no question files committed).
- [`harness/`](harness/README.md): Multi-turn research agent loop, search API adapters, and CLI runner (`harness/run.py`).
- [`tools/`](tools/README.md): One `<tool>.yaml` config per search tool, with setups and pricing (15 tools).
- [`judge/`](judge/README.md): Entity matching, precision/recall/F1/exact-set scoring, and leaderboard builder (`judge/leaderboard.py`).
- [`benchmark.yaml`](benchmark.yaml): Benchmark contract, scope, and refresh cadence.
- [`AGENTS.md`](AGENTS.md): Entry guide for coding agents.

## Quick start

Run the offline test suite (no API keys required):

```sh
uv venv && uv pip install -r requirements.txt
.venv/bin/python -B -m unittest
```

To plan or run against live APIs, copy `.env.example` to `.env`, add your keys, and inspect the runner. The agent's model runs on Azure OpenAI by default, or on OpenAI when only `OPENAI_API_KEY` is set. `--dataset` takes a dataset file or a downloaded Hugging Face split folder. By default the runner prints the execution plan and budget; live paid execution requires both `--execute` and `--confirm-paid`:

```sh
cp .env.example .env
.venv/bin/python -m harness.run --help
```

Build the leaderboard from saved runs:

```sh
.venv/bin/python -B -m judge.leaderboard --runs runs --output leaderboard.json
```

## Adding or updating a tool

1. Add or edit `tools/<tool>.yaml` (and `.env.example` if adding a new API key). For a new search API, also add `harness/adapters/<tool>.py` and register it in `harness/search_tools.py`.
2. Run `.venv/bin/python -B -m unittest`.
3. Open a pull request.

## Links

- [Live leaderboard](https://openbenchmarks.com/multi-turn-company-search)
- [Most accurate](https://openbenchmarks.com/multi-turn-company-search/most-accurate-search-api), [fastest](https://openbenchmarks.com/multi-turn-company-search/fastest-search-api) and [cheapest](https://openbenchmarks.com/multi-turn-company-search/cheapest-search-api) search APIs for research agents
- [Hugging Face dataset](https://huggingface.co/datasets/openbenchmarks/OB-Company-Websearch)
- [`llms.txt`](https://openbenchmarks.com/llms.txt)

## Related benchmarks

- [OB-Company-Search-Lookalikes](https://github.com/openbenchmarks-labs/OB-Company-Search-Lookalikes): Company lookalike discovery ([leaderboard](https://openbenchmarks.com/lookalikes))
- [OB-Code-Websearch](https://github.com/openbenchmarks-labs/OB-Code-Websearch): Web search APIs for coding agents ([leaderboard](https://openbenchmarks.com/web-search-for-coding-agents))
- [OB-Company-News](https://github.com/openbenchmarks-labs/OB-Company-News): Company news search and news-index APIs ([leaderboard](https://openbenchmarks.com/company-news))
- [All OpenBenchmarks leaderboards](https://openbenchmarks.com)

## License

MIT. See [LICENSE](LICENSE).
