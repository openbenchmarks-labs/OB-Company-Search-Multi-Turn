from __future__ import annotations

import unittest
from unittest.mock import patch

from harness.model_client import build_openai_client, required_model_env


def _record(calls: list):
    def client_class(**kwargs):
        calls.append(kwargs)
        return object()

    return client_class


class ModelClientTest(unittest.TestCase):
    def test_azure_is_used_when_its_variables_are_set(self) -> None:
        calls: list = []
        env = {
            "AZURE_OPENAI_BASE_URL": "https://example.openai.azure.com/openai/v1/",
            "AZURE_OPENAI_API_KEY": "azure-key",
            "OPENAI_API_KEY": "openai-key",
        }
        with patch.dict("os.environ", env, clear=True):
            build_openai_client(_record(calls), timeout=12, max_retries=3)
        self.assertEqual(
            calls,
            [{
                "base_url": "https://example.openai.azure.com/openai/v1",
                "api_key": "azure-key",
                "timeout": 12,
                "max_retries": 3,
            }],
        )

    def test_openai_is_used_when_only_its_key_is_set(self) -> None:
        calls: list = []
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
            build_openai_client(_record(calls), timeout=12, max_retries=3)
        self.assertEqual(calls, [{"api_key": "test-key", "timeout": 12, "max_retries": 3}])

    def test_azure_is_the_default_when_nothing_is_set(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(required_model_env(), ("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY"))
            with self.assertRaisesRegex(RuntimeError, "AZURE_OPENAI_BASE_URL, AZURE_OPENAI_API_KEY"):
                build_openai_client(lambda **kwargs: object())

    def test_half_configured_azure_is_refused(self) -> None:
        env = {"AZURE_OPENAI_API_KEY": "azure-key", "OPENAI_API_KEY": "openai-key"}
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "AZURE_OPENAI_BASE_URL"):
                build_openai_client(lambda **kwargs: object())


if __name__ == "__main__":
    unittest.main()
