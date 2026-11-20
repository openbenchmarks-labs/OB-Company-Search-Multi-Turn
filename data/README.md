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
