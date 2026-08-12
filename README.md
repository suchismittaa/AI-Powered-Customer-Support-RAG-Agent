# SupportAI — AI Support Operations Platform

A grounded, transparent, confidence-aware customer support agent: it answers
from your knowledge base, shows the evidence behind every answer, and
escalates to a human when it isn't confident enough to help.

This is an upgrade of the original RAG demo — the RAG pipeline, triage
logic, auth, caching, and evaluation engine are unchanged. What's new is a
production-style FastAPI surface and a dark, enterprise-grade web frontend
built directly on top of it.

## What's here

**Unchanged (existing backend, preserved as-is):**
- `rag_chain.py` — retrieval, L1/L2 triage, Groq LLaMA3 generation, response cache
- `ingest.py` — chunking + embedding + ChromaDB storage pipeline
- `auth/` — JWT auth, bcrypt password hashing, per-org conversation & feedback logs
- `evalution/` — token-F1 / triage-accuracy evaluation engine
- `streamlit_app.py` — the original Streamlit UI (kept as a legacy/alternate interface)

**New:**
- `tickets.py` — SQLite-backed support ticket store, with category/priority
  heuristics reused from the same triage-reason text the RAG pipeline already
  produces
- `kb_manager.py` — reflects on `data/support_docs/` + the live Chroma
  collection to report real document/chunk counts, and wraps upload +
  re-ingestion
- `analytics.py` — aggregates the conversations/feedback tables already
  written by `auth/auth_manager.py` into dashboard-ready numbers (nothing
  fabricated — metrics with no data show as empty states, not invented values)
- `api.py` — extended with Tickets, Knowledge Base, Analytics, Conversations,
  Feedback, and System Status endpoints; also serves the new frontend
- `frontend/` — a vanilla HTML/CSS/JS single-page app implementing the full
  product surface: chat with a live AI-analysis panel, "why this answer?"
  source attribution, ticket creation from L2 escalations, a ticket inbox,
  an analytics dashboard, the RAG evaluation console, and knowledge-base
  management

## Running it

```bash
pip install -r requirements.txt

# 1. Build the vector index (only needed once, or after adding documents)
python ingest.py

# 2. Start the API + new frontend
python api.py
# → open http://localhost:8000

# (optional) the original Streamlit demo still works independently
streamlit run streamlit_app.py
```

Demo accounts (seeded automatically on first run):

| Email             | Password    | Role   |
|-------------------|-------------|--------|
| admin@demo.com    | Admin@1234  | admin  |
| agent@demo.com    | Agent@1234  | agent  |
| viewer@demo.com   | View@1234   | viewer |

Evaluation runs and knowledge-base ingestion require the `admin` role.

## Notes on data integrity

Every number in the Analytics and Knowledge Base pages is computed from data
that's actually been logged (conversations, feedback, files on disk, chunks
in ChromaDB) — there is no seeded or simulated activity. On a fresh install
those pages will show empty states until real queries have been asked.

## Security

`.env` (with your real `GROQ_API_KEY`) is included so the app runs out of the
box, but it's listed in `.gitignore` — if you push this to a public repo,
rotate the key first and keep `.env` untracked. Use `env.example` as the
template for teammates.
