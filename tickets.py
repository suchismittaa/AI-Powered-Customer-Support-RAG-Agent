"""
tickets.py — Support Ticket Store

Lightweight SQLite-backed ticket system that turns L2 (human-review)
triage outcomes into trackable support tickets. Mirrors the storage
pattern already used by auth/auth_manager.py so it fits the existing
architecture without introducing a new database technology.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

DB_PATH = "./data/tickets.db"

VALID_STATUSES = {"open", "in_progress", "ai_resolved", "resolved", "closed"}
VALID_PRIORITIES = {"low", "normal", "high", "critical"}
VALID_CATEGORIES = {"billing", "account", "shipping", "technical", "security", "general"}

# Keyword heuristics reused to auto-suggest category/priority for a ticket
# opened from an L2 escalation, based on the same triage reason text the
# RAG pipeline already produces (see rag_chain.classify_triage).
_CATEGORY_KEYWORDS = {
    "security": ["fraud", "hack", "breach", "security", "compromise", "unauthorized"],
    "billing": ["billing", "refund", "charge", "payment", "invoice", "subscription"],
    "shipping": ["shipping", "delivery", "package", "tracking", "shipment"],
    "account": ["account", "login", "password", "access"],
    "technical": ["api", "bug", "error", "technical", "crash", "integration"],
}
_PRIORITY_KEYWORDS = {
    "critical": ["fraud", "hack", "breach", "security", "legal", "lawsuit", "compromise"],
    "high": ["urgent", "emergency", "critical", "cannot work", "blocking", "down for days"],
}


@dataclass
class Ticket:
    id: int
    ticket_number: str
    org_id: str
    user_id: Optional[int]
    query: str
    ai_summary: str
    suggested_response: str
    category: str
    priority: str
    status: str
    triage_reason: str
    confidence_score: float
    sources: list
    created_at: str
    updated_at: str


def _get_db() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db() -> None:
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tickets (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_number       TEXT UNIQUE NOT NULL,
            org_id              TEXT NOT NULL,
            user_id             INTEGER,
            query               TEXT NOT NULL,
            ai_summary          TEXT,
            suggested_response  TEXT,
            category            TEXT NOT NULL DEFAULT 'general',
            priority            TEXT NOT NULL DEFAULT 'normal',
            status              TEXT NOT NULL DEFAULT 'open',
            triage_reason       TEXT,
            confidence_score    REAL,
            sources             TEXT,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ticket_org ON tickets(org_id);
        CREATE INDEX IF NOT EXISTS idx_ticket_status ON tickets(status);
    """)
    conn.commit()
    conn.close()


def suggest_category_priority(query: str, triage_reason: str) -> tuple[str, str]:
    """Heuristically guess a ticket's category and priority from the query
    and the triage reason already produced by the RAG pipeline."""
    text = f"{query} {triage_reason}".lower()

    category = "general"
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            category = cat
            break

    priority = "normal"
    for pr, keywords in _PRIORITY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            priority = pr
            break

    return category, priority


def _next_ticket_number(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()
    seq = (row[0] or 0) + 1041  # start numbering at #1042 to match brief example
    return f"SUP-{seq}"


def create_ticket(
    org_id: str,
    user_id: Optional[int],
    query: str,
    ai_summary: str = "",
    suggested_response: str = "",
    category: str = "general",
    priority: str = "normal",
    triage_reason: str = "",
    confidence_score: float = 0.0,
    sources: Optional[list] = None,
) -> Ticket:
    if category not in VALID_CATEGORIES:
        category = "general"
    if priority not in VALID_PRIORITIES:
        priority = "normal"

    conn = _get_db()
    ticket_number = _next_ticket_number(conn)
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        """INSERT INTO tickets
           (ticket_number, org_id, user_id, query, ai_summary, suggested_response,
            category, priority, status, triage_reason, confidence_score, sources,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
        (
            ticket_number, org_id, user_id, query, ai_summary, suggested_response,
            category, priority, triage_reason, confidence_score,
            json.dumps(sources or []), now, now,
        ),
    )
    conn.commit()
    ticket_id = cur.lastrowid
    conn.close()
    return get_ticket(ticket_id, org_id)


def get_ticket(ticket_id: int, org_id: str) -> Optional[Ticket]:
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM tickets WHERE id = ? AND org_id = ?", (ticket_id, org_id)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_ticket(row)


def list_tickets(
    org_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
) -> list[Ticket]:
    conn = _get_db()
    query = "SELECT * FROM tickets WHERE org_id = ?"
    params: list = [org_id]

    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (query LIKE ? OR ticket_number LIKE ? OR ai_summary LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_ticket(r) for r in rows]


def update_ticket_status(ticket_id: int, org_id: str, status: str) -> Optional[Ticket]:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status. Must be one of {sorted(VALID_STATUSES)}")
    conn = _get_db()
    conn.execute(
        "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ? AND org_id = ?",
        (status, datetime.utcnow().isoformat(), ticket_id, org_id),
    )
    conn.commit()
    conn.close()
    return get_ticket(ticket_id, org_id)


def get_kpis(org_id: str) -> dict:
    conn = _get_db()
    row = conn.execute(
        """SELECT
               SUM(CASE WHEN status IN ('open','in_progress') THEN 1 ELSE 0 END) AS open_count,
               SUM(CASE WHEN priority='critical' AND status NOT IN ('resolved','closed') THEN 1 ELSE 0 END) AS critical_count,
               SUM(CASE WHEN status IN ('resolved','closed','ai_resolved') THEN 1 ELSE 0 END) AS resolved_count,
               COUNT(*) AS total_count
           FROM tickets WHERE org_id = ?""",
        (org_id,),
    ).fetchone()
    conn.close()
    return {
        "open": row["open_count"] or 0,
        "l2": row["total_count"] or 0,
        "critical": row["critical_count"] or 0,
        "resolved": row["resolved_count"] or 0,
    }


def _row_to_ticket(row: sqlite3.Row) -> Ticket:
    return Ticket(
        id=row["id"],
        ticket_number=row["ticket_number"],
        org_id=row["org_id"],
        user_id=row["user_id"],
        query=row["query"],
        ai_summary=row["ai_summary"] or "",
        suggested_response=row["suggested_response"] or "",
        category=row["category"],
        priority=row["priority"],
        status=row["status"],
        triage_reason=row["triage_reason"] or "",
        confidence_score=row["confidence_score"] or 0.0,
        sources=json.loads(row["sources"] or "[]"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


initialize_db()
