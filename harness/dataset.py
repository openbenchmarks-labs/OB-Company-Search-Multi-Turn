"""Loads and checks the dataset file: questions, constraints, and ground-truth companies."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "company-research-dataset-v1"
FAMILIES = {"investor", "accelerator", "funding", "other"}


class DatasetValidationError(ValueError):
    """The dataset file is invalid."""


@dataclass(frozen=True)
class DatasetSummary:
    dataset_slug: str
    case_count: int
    company_count: int
    gold_membership_count: int
    content_sha256: str


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_sha256(payload: dict[str, Any]) -> str:
    without_receipt = dict(payload)
    without_receipt.pop("content_sha256", None)
    return "sha256:" + hashlib.sha256(canonical_json(without_receipt).encode("utf-8")).hexdigest()


def normalize_company_name(value: str) -> str:
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value.casefold())
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def entity_key(name: str) -> str:
    normalized = normalize_company_name(name)
    return "name:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _require_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetValidationError(f"{path} must be a non-empty string")
    return value.strip()


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise DatasetValidationError(f"{path} must be an array")
    return value


def validate_artifact(payload: dict[str, Any]) -> DatasetSummary:
    if not isinstance(payload, dict):
        raise DatasetValidationError("dataset root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise DatasetValidationError(
            f"schema_version must be {SCHEMA_VERSION!r}, got {payload.get('schema_version')!r}"
        )
    expected_hash = content_sha256(payload)
    if payload.get("content_sha256") != expected_hash:
        raise DatasetValidationError(
            f"content hash mismatch: stored={payload.get('content_sha256')!r} computed={expected_hash!r}"
        )

    dataset = payload.get("dataset")
    if not isinstance(dataset, dict):
        raise DatasetValidationError("dataset must be an object")
    dataset_slug = _require_text(dataset.get("slug"), "dataset.slug")
    _require_text(dataset.get("name"), "dataset.name")

    source = payload.get("source")
    if not isinstance(source, dict):
        raise DatasetValidationError("source must be an object")
    _require_text(source.get("type"), "source.type")

    release = payload.get("gold_release")
    if not isinstance(release, dict) or release.get("version") != 1:
        raise DatasetValidationError("gold_release.version must be 1")
    if release.get("source") not in {"generated", "hand_labelled"}:
        raise DatasetValidationError("gold_release.source must be 'generated' or 'hand_labelled'")

    cases = _require_list(payload.get("cases"), "cases")
    if not cases:
        raise DatasetValidationError("cases cannot be empty")
    case_keys: set[str] = set()
    sort_orders: set[int] = set()
    entity_names: dict[str, str] = {}
    memberships = 0
    for index, case in enumerate(cases):
        path = f"cases[{index}]"
        if not isinstance(case, dict):
            raise DatasetValidationError(f"{path} must be an object")
        key = _require_text(case.get("case_key"), f"{path}.case_key")
        if key in case_keys:
            raise DatasetValidationError(f"duplicate case_key {key!r}")
        case_keys.add(key)
        question = _require_text(case.get("question"), f"{path}.question")
        family = _require_text(case.get("family"), f"{path}.family")
        if family not in FAMILIES:
            raise DatasetValidationError(f"{path}.family is unsupported: {family!r}")
        constraint_count = case.get("constraint_count")
        constraints = _require_list(case.get("constraints"), f"{path}.constraints")
        if not isinstance(constraint_count, int) or constraint_count <= 0:
            raise DatasetValidationError(f"{path}.constraint_count must be positive")
        if len(constraints) != constraint_count:
            raise DatasetValidationError(
                f"{path} has constraint_count={constraint_count} but {len(constraints)} clauses"
            )
        if any(not isinstance(clause, str) or not clause.strip() for clause in constraints):
            raise DatasetValidationError(f"{path}.constraints contains an empty clause")
        if any(clause.casefold() not in question.casefold() for clause in constraints):
            raise DatasetValidationError(f"{path}.question does not contain every constraint clause")
        if not isinstance(case.get("predicates"), dict):
            raise DatasetValidationError(f"{path}.predicates must be an object")
        order = case.get("sort_order")
        if not isinstance(order, int) or order <= 0 or order in sort_orders:
            raise DatasetValidationError(f"{path}.sort_order must be unique and positive")
        sort_orders.add(order)

        gold = _require_list(case.get("gold"), f"{path}.gold")
        if not gold:
            raise DatasetValidationError(f"{path}.gold cannot be empty")
        member_keys: set[str] = set()
        for member_index, member in enumerate(gold):
            member_path = f"{path}.gold[{member_index}]"
            if not isinstance(member, dict):
                raise DatasetValidationError(f"{member_path} must be an object")
            name = _require_text(member.get("name"), f"{member_path}.name")
            key_value = _require_text(member.get("entity_key"), f"{member_path}.entity_key")
            if key_value != entity_key(name):
                raise DatasetValidationError(f"{member_path}.entity_key is not derived from its name")
            if key_value in member_keys:
                raise DatasetValidationError(f"{path} repeats entity {name!r}")
            member_keys.add(key_value)
            existing_name = entity_names.setdefault(key_value, name)
            if normalize_company_name(existing_name) != normalize_company_name(name):
                raise DatasetValidationError(f"entity key collision: {existing_name!r} and {name!r}")
            aliases = _require_list(member.get("aliases"), f"{member_path}.aliases")
            if any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
                raise DatasetValidationError(f"{member_path}.aliases contains an empty value")
            memberships += 1

    if sort_orders != set(range(1, len(cases) + 1)):
        raise DatasetValidationError("case sort_order values must be contiguous from 1")
    return DatasetSummary(
        dataset_slug=dataset_slug,
        case_count=len(cases),
        company_count=len(entity_names),
        gold_membership_count=memberships,
        content_sha256=expected_hash,
    )


def _read_hugging_face(path: Path) -> dict[str, Any]:
    """Join a Hugging Face copy back into one dataset: metadata.json plus the question rows in data/*.jsonl."""
    if path.is_dir():
        root = path
        rows_files = sorted((path / "data").glob("*.jsonl"))
        if len(rows_files) != 1:
            raise DatasetValidationError(f"{path}/data must hold exactly one .jsonl file, found {len(rows_files)}")
        rows_file = rows_files[0]
    else:
        rows_file = path
        root = path.parent.parent if path.parent.name == "data" else path.parent
    metadata_file = root / "metadata.json"
    if not metadata_file.is_file():
        raise DatasetValidationError(f"{metadata_file} is missing; it holds the dataset's name and content_sha256")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise DatasetValidationError(f"{metadata_file} must be an object")
    lines = rows_file.read_text(encoding="utf-8").splitlines()
    return {**metadata, "cases": [json.loads(line) for line in lines if line.strip()]}


def load_artifact(path: Path) -> tuple[dict[str, Any], DatasetSummary]:
    """Load a dataset file (.json), or a Hugging Face copy: its folder or its data/*.jsonl file."""
    if path.is_dir() or path.suffix == ".jsonl":
        payload = _read_hugging_face(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, validate_artifact(payload)
