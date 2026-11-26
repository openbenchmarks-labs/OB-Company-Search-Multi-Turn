# tools

One `<tool>.yaml` file per search tool. Keeping each tool in its own file makes it easy to compare setups and open pull requests without merge conflicts.

Each file lists the tool's setups. A setup names the search endpoint and its settings, the API key it needs, how pages are fetched, and its list price per search and per page fetch.

A setup with `native_fetch: true` reads pages through the tool's own fetch API. A setup with `custom_fetch: true` has no fetch API, so pages come from the shared fetcher in `harness/custom_fetch.py` at no charge.

A setup with `site_operator_policy` moves `site:` filters out of the agent's query into the tool's own domain filter, for Parallel, whose docs ask for that. Every other tool gets `site:` in the query as the agent wrote it.

`none.yaml` is the baseline: the same agent and model with no search and no fetch (`web_search: false`), run beside the tools so the board shows how much each one adds.

To add or update a tool: edit `tools/<tool>.yaml`, run the offline tests, and open a pull request. A new search API also needs an adapter in `harness/adapters/`.
