import io
import unittest
from pathlib import Path

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))
sys.path.insert(0, str(PROJECT_ROOT))

from retrieval.vector_store import SearchHit
from ui_app import create_app, list_domains, run_query


class FakeRetriever:
    def retrieve_for_domain(self, *, domain, query, limit):
        self.domain = domain
        self.query = query
        self.limit = limit
        return [
            SearchHit(
                score=0.91,
                point_id="point-1",
                payload={
                    "text": "Contenu de test sur le sejour.",
                    "document_name": "CESEDA",
                    "metadata": {"article_id": "Art. L111-1"},
                },
            )
        ]

    def build_prompt(self, *, domain, question, hits):
        return f"Domaine={domain}\nQuestion={question}\nHits={len(hits)}"


class FakeResponder:
    def is_available(self):
        return True

    def answer(self, prompt):
        return f"Reponse testee depuis: {prompt.splitlines()[0]}"


class UiAppTests(unittest.TestCase):
    def test_list_domains_returns_configured_domain(self):
        domains = list_domains(PROJECT_ROOT / "domains")
        self.assertIn("droit_etranger", domains)

    def test_run_query_formats_hits_for_template(self):
        result = run_query(
            domain="droit_etranger",
            question="Quels sont les regles ?",
            limit=3,
            retriever_factory=FakeRetriever,
            responder_factory=FakeResponder,
        )

        self.assertEqual(result["hits"][0]["article_id"], "Art. L111-1")
        self.assertIn("Reponse testee", result["answer"])
        self.assertIn("Question=Quels sont les regles ?", result["prompt"])

    def test_post_request_renders_results(self):
        app = create_app(
            retriever_factory=FakeRetriever,
            responder_factory=FakeResponder,
            domains_dir=PROJECT_ROOT / "domains",
        )
        body = "domain=droit_etranger&question=Question+demo&limit=2".encode("utf-8")
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        response = b"".join(
            app(
                {
                    "REQUEST_METHOD": "POST",
                    "CONTENT_LENGTH": str(len(body)),
                    "wsgi.input": io.BytesIO(body),
                },
                start_response,
            )
        ).decode("utf-8")

        self.assertEqual(captured["status"], "200 OK")
        self.assertIn("Question demo", response)
        self.assertIn("Art. L111-1", response)
        self.assertIn("Reponse", response)
        self.assertIn("Prompt RAG", response)
