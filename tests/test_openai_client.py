import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

import openai_client


class FakeHttpxClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeHttpxModule:
    Client = FakeHttpxClient


class FakeOpenAI:
    calls = []

    def __init__(self, **kwargs):
        type(self).calls.append(kwargs)
        if len(type(self).calls) == 1:
            raise FileNotFoundError("missing ca bundle")
        self.kwargs = kwargs


class OpenAIClientTests(unittest.TestCase):
    def test_build_openai_client_falls_back_to_certifi_bundle(self):
        original_openai = openai_client.OpenAI
        original_httpx = openai_client.httpx
        original_ensure = openai_client.ensure_valid_ca_bundle
        FakeOpenAI.calls.clear()

        openai_client.OpenAI = FakeOpenAI
        openai_client.httpx = FakeHttpxModule
        openai_client.ensure_valid_ca_bundle = lambda: "C:/fake/cacert.pem"

        try:
            client = openai_client.build_openai_client("sk-test")
        finally:
            openai_client.OpenAI = original_openai
            openai_client.httpx = original_httpx
            openai_client.ensure_valid_ca_bundle = original_ensure

        self.assertIsInstance(client, FakeOpenAI)
        self.assertEqual(len(FakeOpenAI.calls), 2)
        fallback_kwargs = FakeOpenAI.calls[1]
        self.assertEqual(fallback_kwargs["api_key"], "sk-test")
        self.assertIsInstance(fallback_kwargs["http_client"], FakeHttpxClient)
        self.assertEqual(
            fallback_kwargs["http_client"].kwargs,
            {"verify": "C:/fake/cacert.pem", "trust_env": False},
        )


if __name__ == "__main__":
    unittest.main()
