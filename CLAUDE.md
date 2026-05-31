# Project conventions
## Response format

- Always in English.
- Strict Python  code .
- Concise responses, no paraphrasing.
## Hard rules

- RD1. Never commit `.env` or API keys.
- RD2. Never delete or overwrite `data/` without explicit confirmation.
- RD3. One file, one responsibility — each module owns a single concern; no catch-all files aggregating unrelated functions.
- RD4. When fixing a benchmark issue, implement a general solution that works across all benchmarks — not a hardcoded workaround for the current one.  
- RD5. When adding benchmark examples, verify in the source document that each question's expected articles are actually present and correctly cited in the source text.
- RD6. Cap generation context at 30 chunks maximum — never pass more to the LLM regardless of retrieval pool size.


## Conventions

- Dates in ISO 8601 everywhere (`2026-05-19`).
- Logs in structured JSON (`level`, `message`, `context` fields).



