from __future__ import annotations

import os
from pathlib import Path

import certifi


SSL_ENV_KEYS = ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")


def ensure_valid_ca_bundle() -> str:
    certifi_bundle = certifi.where()

    for key in SSL_ENV_KEYS:
        value = os.environ.get(key)
        if value and not Path(value).exists():
            os.environ[key] = certifi_bundle

    if not os.environ.get("SSL_CERT_FILE"):
        os.environ["SSL_CERT_FILE"] = certifi_bundle

    return certifi_bundle
