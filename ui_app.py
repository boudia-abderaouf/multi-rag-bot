from __future__ import annotations

import html
import io
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "rag-plateform"))

from config.settings import settings
from generation.openai_responder import OpenAIResponder
from retrieval.retriever import Retriever


AppFactory = Callable[[], Retriever]
ResponderFactory = Callable[[], OpenAIResponder]


def _build_responder() -> OpenAIResponder:
    return OpenAIResponder.from_settings(settings)


def list_domains(domains_dir: Path | None = None) -> list[str]:
    root = domains_dir or (PROJECT_ROOT / "domains")
    if not root.exists():
        return []

    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "prompt_template.txt").exists()
    )


def run_query(
    *,
    domain: str,
    question: str,
    limit: int,
    retriever_factory: AppFactory = Retriever,
    responder_factory: ResponderFactory = _build_responder,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("La question est obligatoire.")
    if limit <= 0:
        raise ValueError("La limite doit etre superieure a 0.")

    retriever = retriever_factory()
    hits = retriever.retrieve_for_domain(
        domain=domain,
        query=question.strip(),
        limit=limit,
    )
    prompt = retriever.build_prompt(domain=domain, question=question.strip(), hits=hits)
    responder = responder_factory()
    answer = None
    answer_error = None

    try:
        if responder.is_available():
            answer = responder.answer(prompt)
        else:
            answer_error = "Generation indisponible : verifie OPENAI_API_KEY, RESPONSE_MODEL et la dependance openai."
    except Exception as exc:
        answer_error = f"Echec de la generation : {exc}"

    return {
        "answer": answer,
        "answer_error": answer_error,
        "prompt": prompt,
        "hits": [
            {
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "article_id": hit.payload.get("metadata", {}).get("article_id", "article inconnu"),
                "document_name": hit.payload.get("document_name", "document inconnu"),
            }
            for hit in hits
        ],
    }


def _render_hits(result: dict[str, Any]) -> str:
    items = result.get("hits", [])
    if not items:
        return "<p class='empty'>Aucun hit retourne.</p>"

    cards: list[str] = []
    for item in items:
        cards.append(
            f"""
            <article class="hit-card">
              <div class="hit-meta">
                <span>{html.escape(item["article_id"])}</span>
                <span>score {item["score"]:.4f}</span>
              </div>
              <h3>{html.escape(item["document_name"])}</h3>
              <p>{html.escape(item["text"])}</p>
            </article>
            """
        )
    return "".join(cards)


def render_page(
    *,
    domains: list[str],
    selected_domain: str,
    question: str,
    limit: int,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> str:
    if domains:
        options = "".join(
            (
                f"<option value='{html.escape(domain)}' selected>"
                if domain == selected_domain
                else f"<option value='{html.escape(domain)}'>"
            )
            + f"{html.escape(domain)}</option>"
            for domain in domains
        )
    else:
        options = "<option value=''>Aucun domaine disponible</option>"

    error_block = f"<div class='notice error'>{html.escape(error)}</div>" if error else ""
    result_block = ""
    if result is not None:
        answer = result.get("answer")
        answer_error = result.get("answer_error")
        answer_block = ""
        if answer:
            answer_block = f"""
        <section class="panel">
          <div class="panel-head">
            <h2>Reponse</h2>
          </div>
          <div class="answer">{html.escape(answer)}</div>
        </section>
        """
        elif answer_error:
            answer_block = f"""
        <section class="panel">
          <div class="panel-head">
            <h2>Reponse</h2>
          </div>
          <div class="notice error inline">{html.escape(answer_error)}</div>
        </section>
        """

        result_block = f"""
        {answer_block}
        <section class="panel">
          <div class="panel-head">
            <h2>Hits</h2>
            <span>{len(result.get("hits", []))} resultat(s)</span>
          </div>
          <div class="hits-grid">
            {_render_hits(result)}
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Prompt RAG</h2>
          </div>
          <pre>{html.escape(result.get("prompt", ""))}</pre>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Multi RAG Bot UI</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4efe7;
        --bg-accent: #e6dccd;
        --card: rgba(255, 251, 245, 0.92);
        --line: #d0c3af;
        --text: #261d14;
        --muted: #6e5f4f;
        --primary: #0f766e;
        --primary-strong: #115e59;
        --danger: #9f1239;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        min-height: 100vh;
        font-family: "Segoe UI", "Helvetica Neue", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 30%),
          linear-gradient(180deg, var(--bg) 0%, #fbf7f2 100%);
      }}

      .shell {{
        width: min(1080px, calc(100% - 32px));
        margin: 32px auto;
      }}

      .hero {{
        padding: 28px;
        border: 1px solid rgba(38, 29, 20, 0.08);
        border-radius: 28px;
        background: linear-gradient(135deg, rgba(255, 251, 245, 0.95), rgba(230, 220, 205, 0.9));
        box-shadow: 0 20px 50px rgba(38, 29, 20, 0.08);
      }}

      .eyebrow {{
        display: inline-block;
        margin-bottom: 12px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(15, 118, 110, 0.12);
        color: var(--primary-strong);
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}

      h1, h2, h3, p {{
        margin: 0;
      }}

      .hero h1 {{
        font-size: clamp(2rem, 5vw, 3.4rem);
        line-height: 0.95;
        max-width: 10ch;
      }}

      .hero p {{
        max-width: 62ch;
        margin-top: 14px;
        color: var(--muted);
        line-height: 1.55;
      }}

      form, .panel {{
        margin-top: 20px;
        padding: 24px;
        border: 1px solid rgba(38, 29, 20, 0.08);
        border-radius: 24px;
        background: var(--card);
        box-shadow: 0 14px 40px rgba(38, 29, 20, 0.06);
        backdrop-filter: blur(10px);
      }}

      .form-grid {{
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }}

      label {{
        display: grid;
        gap: 8px;
        font-size: 0.95rem;
        font-weight: 600;
      }}

      textarea,
      select,
      input {{
        width: 100%;
        border: 1px solid var(--line);
        border-radius: 16px;
        background: #fffefb;
        padding: 14px 16px;
        font: inherit;
        color: var(--text);
      }}

      textarea {{
        min-height: 160px;
        resize: vertical;
      }}

      button {{
        margin-top: 16px;
        border: 0;
        border-radius: 999px;
        background: linear-gradient(135deg, var(--primary), var(--primary-strong));
        color: white;
        padding: 14px 22px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }}

      .notice {{
        margin-top: 20px;
        padding: 14px 16px;
        border-radius: 16px;
      }}

      .notice.inline {{
        margin-top: 16px;
      }}

      .error {{
        color: var(--danger);
        background: rgba(244, 63, 94, 0.08);
        border: 1px solid rgba(244, 63, 94, 0.18);
      }}

      .panel-head,
      .hit-meta {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
      }}

      .panel-head span,
      .hit-meta span,
      .empty {{
        color: var(--muted);
      }}

      .hits-grid {{
        display: grid;
        gap: 14px;
        margin-top: 16px;
      }}

      .hit-card {{
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 241, 232, 0.95));
        border: 1px solid rgba(38, 29, 20, 0.07);
      }}

      .hit-card h3 {{
        margin-top: 10px;
        font-size: 1rem;
      }}

      .hit-card p {{
        margin-top: 10px;
        color: var(--muted);
        line-height: 1.6;
        white-space: pre-wrap;
      }}

      pre {{
        margin: 16px 0 0;
        padding: 18px;
        overflow-x: auto;
        border-radius: 18px;
        background: #1d1a17;
        color: #f9f6f0;
        line-height: 1.5;
        white-space: pre-wrap;
      }}

      .answer {{
        margin-top: 16px;
        padding: 18px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(243, 250, 248, 0.96));
        border: 1px solid rgba(15, 118, 110, 0.14);
        line-height: 1.7;
        white-space: pre-wrap;
      }}

      @media (max-width: 640px) {{
        .shell {{
          width: min(100% - 20px, 1080px);
          margin: 20px auto;
        }}

        .hero,
        form,
        .panel {{
          padding: 18px;
          border-radius: 20px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="shell">
      <section class="hero">
        <span class="eyebrow">Local retrieval UI</span>
        <h1>Pose ta question au RAG.</h1>
        <p>
          Cette interface locale envoie une question au retriever existant, affiche les hits Qdrant,
          genere une reponse a partir du prompt RAG puis montre le prompt reconstruit pour le domaine choisi.
        </p>
      </section>

      {error_block}

      <form method="post">
        <div class="form-grid">
          <label>
            Domaine
            <select name="domain">{options}</select>
          </label>
          <label>
            Limite de hits
            <input type="number" min="1" max="20" name="limit" value="{limit}" />
          </label>
        </div>
        <label style="margin-top: 16px;">
          Question
          <textarea name="question" placeholder="Ex: Quelles sont les regles de sejour en France ?">{html.escape(question)}</textarea>
        </label>
        <button type="submit">Lancer la recherche</button>
      </form>

      {result_block}
    </main>
  </body>
</html>
"""


def _read_form(environ: dict[str, Any]) -> dict[str, str]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if method == "POST":
        raw_length = environ.get("CONTENT_LENGTH", "0") or "0"
        length = int(raw_length) if raw_length.isdigit() else 0
        body = environ.get("wsgi.input", io.BytesIO()).read(length).decode("utf-8")
        parsed = parse_qs(body)
    else:
        parsed = parse_qs(environ.get("QUERY_STRING", ""))

    return {key: values[0] for key, values in parsed.items() if values}


def create_app(
    *,
    retriever_factory: AppFactory = Retriever,
    responder_factory: ResponderFactory = _build_responder,
    domains_dir: Path | None = None,
):
    def application(environ: dict[str, Any], start_response: Callable[..., Any]):
        domains = list_domains(domains_dir)
        default_domain = domains[0] if domains else ""
        form = _read_form(environ)
        selected_domain = form.get("domain", default_domain) or default_domain
        question = form.get("question", "")

        try:
            limit = int(form.get("limit", "5"))
        except ValueError:
            limit = 5

        error = None
        result = None

        if environ.get("REQUEST_METHOD", "GET").upper() == "POST":
            try:
                if selected_domain not in domains:
                    raise ValueError("Le domaine selectionne est introuvable.")
                result = run_query(
                    domain=selected_domain,
                    question=question,
                    limit=limit,
                    retriever_factory=retriever_factory,
                    responder_factory=responder_factory,
                )
            except Exception as exc:
                error = str(exc)

        content = render_page(
            domains=domains,
            selected_domain=selected_domain,
            question=question,
            limit=limit,
            result=result,
            error=error,
        ).encode("utf-8")

        start_response(
            "200 OK",
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(content))),
            ],
        )
        return [content]

    return application


def serve(*, host: str = "127.0.0.1", port: int = 8000) -> None:
    app = create_app()
    with make_server(host, port, app) as server:
        print(f"UI disponible sur http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    serve()
