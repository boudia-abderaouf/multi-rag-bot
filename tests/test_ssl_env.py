import os
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

import ssl_env


class FakeCertifi:
    @staticmethod
    def where():
        return "C:/fake/cacert.pem"


class SslEnvTests(unittest.TestCase):
    def test_ensure_valid_ca_bundle_replaces_missing_env_paths(self):
        original_certifi = ssl_env.certifi
        original_env = {key: os.environ.get(key) for key in ssl_env.SSL_ENV_KEYS}

        ssl_env.certifi = FakeCertifi
        os.environ["SSL_CERT_FILE"] = "C:/missing/cert.pem"
        os.environ["REQUESTS_CA_BUNDLE"] = "C:/missing/requests.pem"
        os.environ["CURL_CA_BUNDLE"] = "C:/missing/curl.pem"

        try:
            bundle = ssl_env.ensure_valid_ca_bundle()
            ssl_value = os.environ.get("SSL_CERT_FILE")
            requests_value = os.environ.get("REQUESTS_CA_BUNDLE")
            curl_value = os.environ.get("CURL_CA_BUNDLE")
        finally:
            ssl_env.certifi = original_certifi
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(bundle, "C:/fake/cacert.pem")
        self.assertEqual(ssl_value, "C:/fake/cacert.pem")
        self.assertEqual(requests_value, "C:/fake/cacert.pem")
        self.assertEqual(curl_value, "C:/fake/cacert.pem")

    def test_ensure_valid_ca_bundle_sets_ssl_cert_file_when_missing(self):
        original_certifi = ssl_env.certifi
        original_env = {key: os.environ.get(key) for key in ssl_env.SSL_ENV_KEYS}

        ssl_env.certifi = FakeCertifi
        for key in ssl_env.SSL_ENV_KEYS:
            os.environ.pop(key, None)

        try:
            bundle = ssl_env.ensure_valid_ca_bundle()
            ssl_value = os.environ.get("SSL_CERT_FILE")
        finally:
            ssl_env.certifi = original_certifi
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(bundle, "C:/fake/cacert.pem")
        self.assertEqual(ssl_value, "C:/fake/cacert.pem")


if __name__ == "__main__":
    unittest.main()
