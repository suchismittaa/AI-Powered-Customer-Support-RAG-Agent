"""
api.py — FastAPI REST API v2 with Auth and Evaluation endpoints

Endpoints:
  POST /auth/login          — Authenticate and receive JWT token
  POST /auth/register       — Register a new user account
  POST /ask                 — Submit a query (requires JWT)
  GET  /health              — System health check
  GET  /eval/history        — List evaluation run summaries (admin)
  POST /eval/run            — Trigger evaluation run (admin)
"""

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="SupportAI RAG API v2",
    description="Enterprise RAG-powered customer support API with auth and evaluation.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Background ingestion state (single-slot — good enough for a demo/portfolio deployment)
_ingest_state = {"running": False, "last_result": None, "last_error": None}

# ── Singletons ────────────────────────────────────────────────────────────────
_rag_chain = None

def get_rag():
    global _rag_chain
    if _rag_chain is None:
        try:
            from rag_chain import get_rag_chain
            _rag_chain = get_rag_chain()
        except Exception as e:
            raise HTTPException(503, detail=str(e))
    return _rag_chain


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validate JWT Bearer token and return decoded user payload.

    Args:
        credentials: HTTP Authorization header credentials.

    Returns:
        Decoded JWT payload dict.

    Raises:
        HTTPException(401): If token is missing, invalid, or expired.
    """
    from auth import verify_token
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return payload


# ── Models ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str
    org_id: str = "default"
    role: str = "agent"

class LoginResponse(BaseModel):
    token: str
    user_id: int
    name: str
    email: str
    role: str
    org_id: str
    expires_at: str

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    use_cache: bool = True

class RetrievedChunkResponse(BaseModel):
    source: str
    text: str
    score: float = 0.0

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    triage_level: str
    triage_reason: str
    confidence_score: float
    from_cache: bool
    query: str
    retrieved_chunks: list[RetrievedChunkResponse] = []

class HealthResponse(BaseModel):
    status: str
    knowledge_base_ready: bool
    doc_count: int
    llm_model: str
    groq_api_configured: bool
    timestamp: str

class FeedbackRequest(BaseModel):
    query: str
    answer: str
    rating: str  # "positive" | "negative"

class CreateTicketRequest(BaseModel):
    query: str = Field(..., min_length=1)
    ai_summary: str = ""
    suggested_response: str = ""
    category: Optional[str] = None
    priority: Optional[str] = None
    triage_reason: str = ""
    confidence_score: float = 0.0
    sources: list[str] = []

class TicketStatusUpdate(BaseModel):
    status: str


# ── Auth endpoints ────────────────────────────────────────────────────────────
@app.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
async def login(req: LoginRequest):
    """Authenticate with email/password and receive a JWT token."""
    from auth import login_user
    success, msg, session = login_user(req.email, req.password)
    if not success:
        raise HTTPException(status_code=401, detail=msg)
    return LoginResponse(
        token=session.token, user_id=session.user_id,
        name=session.name, email=session.email,
        role=session.role, org_id=session.org_id,
        expires_at=session.expires_at,
    )

@app.post("/auth/register", status_code=201, tags=["Auth"])
async def register(req: RegisterRequest):
    """Register a new user account."""
    from auth import register_user
    success, msg = register_user(req.email, req.name, req.password, req.role, req.org_id)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


# ── RAG endpoints ─────────────────────────────────────────────────────────────
@app.post("/ask", response_model=QueryResponse, tags=["RAG"])
async def ask(req: QueryRequest, user=Depends(get_current_user)):
    """
    Submit a customer support query. Requires JWT Bearer token.

    Returns a grounded answer with source attribution and triage classification.
    """
    rag = get_rag()
    if not rag.is_ready:
        raise HTTPException(503, detail="Knowledge base not ready. Run python ingest.py first.")
    try:
        from auth import save_message
        result = rag.ask(req.query, use_cache=req.use_cache)
        save_message(user["user_id"], user["org_id"], "user", req.query)
        save_message(user["user_id"], user["org_id"], "assistant", result.answer,
                     result.sources, result.triage_level, result.triage_reason,
                     result.confidence_score, result.from_cache)
        return QueryResponse(
            answer=result.answer, sources=result.sources,
            triage_level=result.triage_level, triage_reason=result.triage_reason,
            confidence_score=result.confidence_score, from_cache=result.from_cache,
            query=result.query,
            retrieved_chunks=[
                RetrievedChunkResponse(source=c.source, text=c.text, score=c.score)
                for c in (result.retrieved_chunks or [])
            ],
        )
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Return system status — no auth required."""
    doc_count, kb_ready = 0, False
    try:
        rag = get_rag()
        doc_count = rag.doc_count
        kb_ready  = rag.is_ready
    except Exception:
        pass
    return HealthResponse(
        status="ok" if kb_ready else "degraded",
        knowledge_base_ready=kb_ready,
        doc_count=doc_count,
        llm_model="llama3-8b-8192 (Groq)",
        groq_api_configured=bool(os.getenv("GROQ_API_KEY")),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/eval/history", tags=["Evaluation"])
async def eval_history(user=Depends(get_current_user)):
    """List all evaluation run summaries. Admin only."""
    if user.get("role") != "admin":
        raise HTTPException(403, detail="Admin role required.")
    from evalution import get_eval_history
    return {"runs": get_eval_history()}

@app.get("/eval/history/{run_id}", tags=["Evaluation"])
async def eval_history_detail(run_id: str, user=Depends(get_current_user)):
    """Per-question results for a single evaluation run. Admin only."""
    if user.get("role") != "admin":
        raise HTTPException(403, detail="Admin role required.")
    from evalution import get_eval_details
    return {"run_id": run_id, "results": get_eval_details(run_id)}

@app.post("/eval/run", tags=["Evaluation"])
async def eval_run(user=Depends(get_current_user)):
    """Trigger a new evaluation run. Admin only. Returns summary."""
    if user.get("role") != "admin":
        raise HTTPException(403, detail="Admin role required.")
    rag = get_rag()
    from evalution import run_evaluation
    try:
        summary = run_evaluation(rag, verbose=False)
        from dataclasses import asdict
        return asdict(summary)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ── Feedback ──────────────────────────────────────────────────────────────────
@app.post("/feedback", tags=["Conversations"])
async def submit_feedback(req: FeedbackRequest, user=Depends(get_current_user)):
    """Record 👍/👎 feedback on a specific AI answer."""
    from auth import save_feedback
    if req.rating not in ("positive", "negative"):
        raise HTTPException(400, detail="rating must be 'positive' or 'negative'.")
    save_feedback(user["user_id"], user["org_id"], req.query, req.answer, req.rating)
    return {"message": "Feedback recorded."}


# ── Conversations ─────────────────────────────────────────────────────────────
@app.get("/conversations", tags=["Conversations"])
async def conversations(limit: int = 50, user=Depends(get_current_user)):
    """Return the current user's conversation history."""
    from auth import get_conversation_history
    return {"messages": get_conversation_history(user["user_id"], user["org_id"], limit)}

@app.delete("/conversations", tags=["Conversations"])
async def clear_conversations(user=Depends(get_current_user)):
    """Clear the current user's conversation history."""
    from auth import clear_conversation_history
    clear_conversation_history(user["user_id"], user["org_id"])
    return {"message": "Conversation history cleared."}


# ── Tickets ───────────────────────────────────────────────────────────────────
@app.get("/tickets", tags=["Tickets"])
async def get_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    user=Depends(get_current_user),
):
    import tickets
    from dataclasses import asdict
    results = tickets.list_tickets(
        user["org_id"], status=status, priority=priority, category=category, search=search
    )
    return {"tickets": [asdict(t) for t in results]}

@app.get("/tickets/kpis", tags=["Tickets"])
async def tickets_kpis(user=Depends(get_current_user)):
    import tickets
    return tickets.get_kpis(user["org_id"])

@app.get("/tickets/suggest", tags=["Tickets"])
async def suggest_ticket_fields(query: str, triage_reason: str = "", user=Depends(get_current_user)):
    """Heuristic category/priority suggestion for the 'Create Ticket' modal."""
    import tickets
    category, priority = tickets.suggest_category_priority(query, triage_reason)
    return {"category": category, "priority": priority}

@app.post("/tickets", status_code=201, tags=["Tickets"])
async def create_ticket(req: CreateTicketRequest, user=Depends(get_current_user)):
    import tickets
    from dataclasses import asdict
    category, priority = tickets.suggest_category_priority(req.query, req.triage_reason)
    ticket = tickets.create_ticket(
        org_id=user["org_id"],
        user_id=user["user_id"],
        query=req.query,
        ai_summary=req.ai_summary,
        suggested_response=req.suggested_response,
        category=req.category or category,
        priority=req.priority or priority,
        triage_reason=req.triage_reason,
        confidence_score=req.confidence_score,
        sources=req.sources,
    )
    return asdict(ticket)

@app.get("/tickets/{ticket_id}", tags=["Tickets"])
async def get_ticket_detail(ticket_id: int, user=Depends(get_current_user)):
    import tickets
    from dataclasses import asdict
    ticket = tickets.get_ticket(ticket_id, user["org_id"])
    if not ticket:
        raise HTTPException(404, detail="Ticket not found.")
    return asdict(ticket)

@app.patch("/tickets/{ticket_id}", tags=["Tickets"])
async def patch_ticket_status(ticket_id: int, req: TicketStatusUpdate, user=Depends(get_current_user)):
    import tickets
    from dataclasses import asdict
    try:
        ticket = tickets.update_ticket_status(ticket_id, user["org_id"], req.status)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    if not ticket:
        raise HTTPException(404, detail="Ticket not found.")
    return asdict(ticket)


# ── Knowledge Base ───────────────────────────────────────────────────────────
@app.get("/kb/documents", tags=["Knowledge Base"])
async def kb_documents(user=Depends(get_current_user)):
    import kb_manager
    return {"documents": kb_manager.list_documents()}

@app.get("/kb/health", tags=["Knowledge Base"])
async def kb_health(user=Depends(get_current_user)):
    import kb_manager
    rag = None
    try:
        rag = get_rag()
    except Exception:
        pass
    return kb_manager.get_kb_health(rag)

@app.post("/kb/upload", tags=["Knowledge Base"])
async def kb_upload(file: UploadFile = File(...), user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "agent"):
        raise HTTPException(403, detail="Admin or agent role required.")
    import kb_manager
    content = await file.read()
    try:
        saved_name = kb_manager.save_uploaded_file(file.filename, content)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"message": f"'{saved_name}' uploaded. Run ingestion to add it to the knowledge base.",
            "filename": saved_name}

def _run_ingest_job():
    import kb_manager
    global _rag_chain
    _ingest_state["running"] = True
    _ingest_state["last_error"] = None
    try:
        result = kb_manager.run_ingestion()
        _ingest_state["last_result"] = result
        _rag_chain = None  # force reload so the running API picks up the fresh index
    except Exception as e:
        _ingest_state["last_error"] = str(e)
    finally:
        _ingest_state["running"] = False

@app.post("/kb/ingest", tags=["Knowledge Base"])
async def kb_ingest(background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Trigger the existing ingest.py pipeline in the background. Admin only."""
    if user.get("role") != "admin":
        raise HTTPException(403, detail="Admin role required.")
    if _ingest_state["running"]:
        raise HTTPException(409, detail="An ingestion run is already in progress.")
    background_tasks.add_task(_run_ingest_job)
    return {"message": "Ingestion started."}

@app.get("/kb/ingest/status", tags=["Knowledge Base"])
async def kb_ingest_status(user=Depends(get_current_user)):
    return _ingest_state


# ── Analytics ─────────────────────────────────────────────────────────────────
@app.get("/analytics/overview", tags=["Analytics"])
async def analytics_overview(user=Depends(get_current_user)):
    import analytics
    return analytics.overview(user["org_id"])

@app.get("/analytics/resolution-trend", tags=["Analytics"])
async def analytics_resolution_trend(days: int = 14, user=Depends(get_current_user)):
    import analytics
    return {"trend": analytics.resolution_trend(user["org_id"], days)}

@app.get("/analytics/categories", tags=["Analytics"])
async def analytics_categories(user=Depends(get_current_user)):
    import analytics
    return {"categories": analytics.query_categories(user["org_id"])}

@app.get("/analytics/escalation-reasons", tags=["Analytics"])
async def analytics_escalation_reasons(user=Depends(get_current_user)):
    import analytics
    return {"reasons": analytics.escalation_reasons(user["org_id"])}

@app.get("/analytics/cache", tags=["Analytics"])
async def analytics_cache(user=Depends(get_current_user)):
    import analytics
    return analytics.cache_performance(user["org_id"])


# ── System status ─────────────────────────────────────────────────────────────
@app.get("/system/status", tags=["System"])
async def system_status():
    """Component-level health, used by the header status indicator."""
    components = {}

    try:
        rag = get_rag()
        components["vector_database"] = "online" if rag.vector_store is not None else "offline"
        components["embedding_model"] = "loaded"
        components["knowledge_base"] = "ready" if rag.is_ready else "not_ready"
    except Exception:
        components["vector_database"] = "offline"
        components["embedding_model"] = "not_loaded"
        components["knowledge_base"] = "not_ready"

    components["groq_llm"] = "connected" if os.getenv("GROQ_API_KEY") else "not_configured"
    components["response_cache"] = "active" if os.path.exists("./response_cache.json") else "inactive"
    components["api"] = "online"

    overall = "operational" if all(
        v in ("online", "loaded", "ready", "connected", "active")
        for v in components.values()
    ) else "degraded"

    return {"overall": overall, "components": components,
            "timestamp": datetime.utcnow().isoformat() + "Z"}


# ── Frontend (static SPA) ────────────────────────────────────────────────────
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(_STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(_STATIC_DIR, "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # Let real API routes 404 normally; only fall back to the SPA shell
        # for unknown non-API paths (client-side routes like /tickets, /kb).
        candidate = os.path.join(_STATIC_DIR, full_path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {"message": "SupportAI RAG API v2", "docs": "/docs", "health": "/health"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
