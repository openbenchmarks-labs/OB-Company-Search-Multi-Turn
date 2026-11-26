from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness.dataset import DatasetValidationError, load_artifact
from harness.tests.test_runner import _dataset


def _hugging_face_copy(root: Path) -> dict:
    """Write a dataset the way Hugging Face publishes it: metadata.json and data/<split>.jsonl."""
    payload = _dataset(root / "dataset.json")
    metadata = {key: value for key, value in payload.items() if key != "cases"}
    (root / "hf" / "data").mkdir(parents=True)
    (root / "hf" / "metadata.json").write_text(json.dumps(metadata))
    (root / "hf" / "data" / "validation.jsonl").write_text(
        "".join(json.dumps(case) + "\n" for case in payload["cases"])
    )
    return payload


class DatasetTest(unittest.TestCase):
    def test_hugging_face_folder_and_rows_file_load_like_the_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = _hugging_face_copy(root)
            for path in (root / "hf", root / "hf" / "data" / "validation.jsonl"):
                loaded, summary = load_artifact(path)
                self.assertEqual(loaded, payload)
                self.assertEqual(summary.case_count, 1)

    def test_changed_rows_fail_the_hash_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _hugging_face_copy(root)
            rows = root / "hf" / "data" / "validation.jsonl"
            rows.write_text(rows.read_text().replace("Acme", "Acme Labs"))
            with self.assertRaisesRegex(DatasetValidationError, "content hash mismatch"):
                load_artifact(rows)

    def test_missing_metadata_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _hugging_face_copy(root)
            (root / "hf" / "metadata.json").unlink()
            with self.assertRaisesRegex(DatasetValidationError, "metadata.json is missing"):
                load_artifact(root / "hf")


if __name__ == "__main__":
    unittest.main()
