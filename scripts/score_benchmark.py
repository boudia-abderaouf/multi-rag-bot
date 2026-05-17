"""
Score benchmark results: checks which articles_cibles were retrieved and/or cited.

Deux dimensions par article cible :
  - retrieved : l'article est-il dans les chunks récupérés par le retriever ?
  - cited     : l'article est-il mentionné dans la réponse générée ?

Usage:
    python3 scripts/score_benchmark.py data/benchmark/droit_etranger/20260517T143923Z.jsonl
    python3 scripts/score_benchmark.py <file>.jsonl --save   # sauvegarde *_scored.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# ── normalisation des identifiants d'articles ────────────────────────────────
# Le benchmark écrit  "Art. L413-1"
# Les chunks Qdrant   "Art. L. 413-1"  ou  "Art. L. 313-4"
# → on retire le préfixe "Art.", les espaces et les points pour comparer.

def _normalize_article(raw: str) -> str:
    s = re.sub(r"(?i)art\.?\s*", "", raw)   # retire le préfixe Art. / Art
    s = re.sub(r"[.\s]", "", s)             # retire les . et espaces restants
    return s.lower()


# Regex pour trouver les citations dans le texte d'une réponse
_ARTICLE_RE = re.compile(
    r"Art\.\s*[LRD]\.?\s*\d{3,4}-\d{1,3}(?:-\d{1,3})?",
    re.IGNORECASE,
)


def _cited_in_text(text: str) -> set[str]:
    return {_normalize_article(m) for m in _ARTICLE_RE.findall(text or "")}


def _retrieved_set(chunks: list[dict]) -> set[str]:
    return {_normalize_article(c["article_id"]) for c in chunks}


# ── scoring d'un enregistrement ──────────────────────────────────────────────

def score_record(record: dict) -> dict:
    cibles_raw: list[str] = record.get("articles_cibles") or []
    cibles_norm = [_normalize_article(a) for a in cibles_raw]

    retrieved = _retrieved_set(record.get("retrieved_chunks") or [])
    cited = _cited_in_text(record.get("answer") or "")
    has_answer = record.get("answer") is not None

    detail = [
        {
            "article": raw,
            "retrieved": norm in retrieved,
            "cited": (norm in cited) if has_answer else None,
        }
        for raw, norm in zip(cibles_raw, cibles_norm)
    ]

    n = len(detail) or 1
    retrieval_score = sum(1 for d in detail if d["retrieved"]) / n
    citation_score = (
        sum(1 for d in detail if d["cited"]) / n if has_answer else None
    )

    return {
        **record,
        "_scoring": {
            "detail": detail,
            "retrieval_score": round(retrieval_score, 3),
            "citation_score": round(citation_score, 3) if citation_score is not None else None,
            "has_answer": has_answer,
        },
    }


# ── rapport textuel ──────────────────────────────────────────────────────────

_TICK = "✓"
_CROSS = "✗"
_DASH = "—"
_DIFF_ORDER = ["simple", "moyen", "difficile"]


def _fmt(v: bool | None) -> str:
    if v is None:
        return _DASH
    return _TICK if v else _CROSS


def _pct(score: float | None) -> str:
    if score is None:
        return _DASH
    return f"{int(score * 100)}%"


def _avg(values: list[float]) -> str:
    if not values:
        return _DASH
    return f"{round(sum(values) / len(values) * 100)}%"


def print_report(scored: list[dict]) -> None:
    run_id = scored[0].get("run_id", "?")
    domain = scored[0].get("domain", "?")

    sep = "─" * 72

    print()
    print("═" * 72)
    print(f"  BENCHMARK SCORING  |  domaine: {domain}  |  run: {run_id}")
    print("═" * 72)

    by_theme: dict[str, list] = defaultdict(list)
    by_diff: dict[str, list] = defaultdict(list)

    for r in scored:
        s = r["_scoring"]
        by_theme[r["theme"]].append(s)
        by_diff[r["difficulte"]].append(s)

        q_text = r["question"]
        q_short = (q_text[:72] + "…") if len(q_text) > 72 else q_text

        print()
        print(f"  [{r['id']}]  {r['difficulte'].upper():<8}  {r['theme']}")
        print(f"  Q : {q_short}")
        print(f"  {sep}")

        if s["detail"]:
            print(f"  {'Article':<24} {'Retrieval':>10}  {'Cité réponse':>13}")
            print(f"  {'─'*24} {'─'*10}  {'─'*13}")
            for d in s["detail"]:
                print(f"  {d['article']:<24} {_fmt(d['retrieved']):>10}  {_fmt(d['cited']):>13}")
        else:
            print("  (aucun article cible défini)")

        print(
            f"\n  → retrieval: {_pct(s['retrieval_score'])}"
            f"  |  citation réponse: "
            f"{'dry-run' if not s['has_answer'] else _pct(s['citation_score'])}"
        )

    # ── Résumé global ────────────────────────────────────────────────────────
    print()
    print("═" * 72)
    print("  RÉSUMÉ GLOBAL")
    print("═" * 72)

    all_ret = [r["_scoring"]["retrieval_score"] for r in scored]
    all_cit = [r["_scoring"]["citation_score"] for r in scored
               if r["_scoring"]["citation_score"] is not None]

    print(f"\n  {'Retrieval moyen global':<38} {_avg(all_ret):>5}")
    print(f"  {'Citation réponse moyenne globale':<38} {_avg(all_cit):>5}")

    print("\n  Par difficulté :")
    for diff in _DIFF_ORDER:
        items = by_diff.get(diff)
        if not items:
            continue
        ret = [i["retrieval_score"] for i in items]
        cit = [i["citation_score"] for i in items if i["citation_score"] is not None]
        print(
            f"    {diff:<12}  retrieval={_avg(ret):>4}   "
            f"citation={_avg(cit):>4}   n={len(items)}"
        )

    print("\n  Par thème :")
    for theme in sorted(by_theme):
        items = by_theme[theme]
        ret = [i["retrieval_score"] for i in items]
        cit = [i["citation_score"] for i in items if i["citation_score"] is not None]
        print(
            f"    {theme:<18}  retrieval={_avg(ret):>4}   "
            f"citation={_avg(cit):>4}   n={len(items)}"
        )

    # ── Articles jamais retrouvés ─────────────────────────────────────────────
    missed: list[tuple[str, str]] = []
    for r in scored:
        for d in r["_scoring"]["detail"]:
            if not d["retrieved"]:
                missed.append((r["id"], d["article"]))

    if missed:
        print("\n  Articles cibles jamais retrouvés par le retriever :")
        for qid, art in missed:
            print(f"    [{qid}]  {art}")
    else:
        print("\n  Tous les articles cibles ont été retrouvés ✓")

    print()


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score un fichier de résultats benchmark (JSONL)."
    )
    parser.add_argument(
        "results_file",
        help="Fichier JSONL produit par run_benchmark.py",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Sauvegarde un fichier *_scored.jsonl avec les scores intégrés",
    )
    args = parser.parse_args()

    path = Path(args.results_file)
    if not path.exists():
        print(f"Fichier introuvable : {path}", file=sys.stderr)
        sys.exit(1)

    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if not records:
        print("Fichier vide.", file=sys.stderr)
        sys.exit(1)

    scored = [score_record(r) for r in records]
    print_report(scored)

    if args.save:
        out = path.with_name(path.stem + "_scored.jsonl")
        with out.open("w", encoding="utf-8") as f:
            for r in scored:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"Fichier scoré sauvegardé → {out}")


if __name__ == "__main__":
    main()
