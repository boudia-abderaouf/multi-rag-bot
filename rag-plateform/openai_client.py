from __future__ import annotations

from typing import Any

import httpx

from ssl_env import ensure_valid_ca_bundle

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on optional dependency
    OpenAI = None


def build_openai_client(api_key: str) -> Any:
    if not api_key or OpenAI is None:
        return None

    ca_bundle = ensure_valid_ca_bundle()

    try:
        return OpenAI(api_key=api_key)
    except FileNotFoundError:
        # Fallback for broken SSL_CERT_FILE / CA bundle env on Windows or Conda envs.
        return OpenAI(
            api_key=api_key,
            http_client=httpx.Client(
                verify=ca_bundle,
                trust_env=False,
            ),
        )
