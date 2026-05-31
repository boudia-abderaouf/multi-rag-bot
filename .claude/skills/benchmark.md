---
description: Run the RAG benchmark for droit_etranger and score results. Trigger when the user says "run benchmark", "lance le benchmark", "check recall", "score le retrieval", "valide le retrieval", "benchmark", or after any change to retriever.py / reranker.py.
---

Delegate to the `benchmark-runner` agent to run and score the benchmark.

Pass along any context the user gave (e.g., reranker backend, top-k value, specific theme or difficulté filter).

After the agent reports, summarize the delta in one line:
`recall@k: X% → Y% (±Z pp) | precision@k: ... | threshold: PASS/FAIL`

If the result is a regression (recall drops), flag it prominently and recommend not committing the change.
