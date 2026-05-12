import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api.main import app


class ApiEntrypointTests(unittest.TestCase):
    def test_health_endpoint_returns_ok_payload(self):
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "multi-rag-bot-api",
            },
        )

    def test_health_endpoint_allows_webapp_origin(self):
        client = TestClient(app)

        response = client.get(
            "/health",
            headers={"Origin": "http://127.0.0.1:4173"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://127.0.0.1:4173",
        )

    def test_openapi_exposes_health_contract(self):
        client = TestClient(app)

        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("/health", response.json()["paths"])
