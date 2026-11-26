"""Model client for the research agent: Azure OpenAI by default, OpenAI when only OPENAI_API_KEY is set.

On Azure, AZURE_OPENAI_BASE_URL is the deployment's OpenAI v1 URL (ending in `/openai/v1`) and the
`--model` name is the deployment name.
"""

from __future__ import annotations

import os
from typing import Any, Callable


AZURE_URL_ENV = "AZURE_OPENAI_BASE_URL"
AZURE_KEY_ENV = "AZURE_OPENAI_API_KEY"
OPENAI_KEY_ENV = "OPENAI_API_KEY"


def provider() -> str:
    """"openai" when only OPENAI_API_KEY is set; "azure" otherwise, including when nothing is set."""
    azure_set = any(os.environ.get(name, "").strip() for name in (AZURE_URL_ENV, AZURE_KEY_ENV))
    return "openai" if os.environ.get(OPENAI_KEY_ENV, "").strip() and not azure_set else "azure"


def required_model_env() -> tuple[str, ...]:
    return (AZURE_URL_ENV, AZURE_KEY_ENV) if provider() == "azure" else (OPENAI_KEY_ENV,)


def build_openai_client(
    client_class: Callable[..., Any] | None = None,
    *,
    timeout: int = 240,
    max_retries: int = 1,
) -> Any:
    """Build the OpenAI SDK client the research agent calls, pointed at Azure or OpenAI."""
    missing = [name for name in required_model_env() if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(f"missing model credentials: {', '.join(missing)}")
    if client_class is None:
        from openai import OpenAI

        client_class = OpenAI
    if provider() == "azure":
        return client_class(
            base_url=os.environ[AZURE_URL_ENV].strip().rstrip("/"),
            api_key=os.environ[AZURE_KEY_ENV].strip(),
            timeout=timeout,
            max_retries=max_retries,
        )
    return client_class(
        api_key=os.environ[OPENAI_KEY_ENV].strip(),
        timeout=timeout,
        max_retries=max_retries,
    )
