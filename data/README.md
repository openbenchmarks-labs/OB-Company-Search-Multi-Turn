# data

No question files are committed to this folder.

## Public vs. held-out evaluation sets

- **Public split:** Published on Hugging Face at [`openbenchmarks/OB-Company-Websearch`](https://huggingface.co/datasets/openbenchmarks/OB-Company-Websearch).
- **Held-out split (private):** The evaluation set used for the published leaderboard stays private so tools cannot train on it. Pass your dataset file to the runner with `--dataset <file>.json`.

## Files and schema

A dataset file is a single JSON object validated by `harness/dataset.py`:

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Always `company-research-dataset-v1`. |
| `dataset` | object | `slug` and `name` of the question set. |
| `source`, `gold_release` | string | Provenance and ground-truth release identifier. |
| `cases` | array | Questions, each with `case_key`, `question`, `family` (`investor`, `accelerator`, `funding`, or `other`), `constraints`, `constraint_count`, `predicates`, `sort_order`, and `gold`. |
| `gold` | array | Ground-truth companies per question, each with `name`, `domain`, `aliases`, and `entity_key`. |
| `content_sha256` | string | SHA-256 digest of the rest of the file; the runner refuses mismatched hashes. |

## Hugging Face copies

Hugging Face publishes each split as `metadata.json` (every field above except `cases`) and `data/<split>.jsonl` (one question per line). Pass the downloaded folder, or its `.jsonl` file, as `--dataset`; the runner joins the two into the file above and checks `content_sha256` the same way.

```sh
.venv/bin/python -m harness.run --dataset OB-Company-Search-Multi-Turn
```
