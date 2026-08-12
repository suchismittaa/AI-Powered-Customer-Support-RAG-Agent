"""
analytics.py — Support Operations Analytics

Aggregates real numbers out of the conversations/feedback tables that
auth/auth_manager.py already writes to on every /ask call, plus the
ticket store in tickets.py. No metric here is fabricated: anything the
UI can't compute from stored data is simply omitted or reported as 0,
rather than invented.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

AUTH_DB_PATH = "./auth/users.db"

_CATEGORY_KEYWORDS = {
    "Billing": ["billing", "refund", "charge", "payment", "invoice", "subscription"],
    "Shipping": ["shipping", "delivery", "package", "tracking", "shipment"],
    "Account": ["account", "login", "password", "access"],
    "Technical": ["api", "bug", "error", "technical", "crash", "integration"],
}


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def overview(org_id: str) -> dict:
    """Top-line metrics for the analytics dashboard header cards."""
    conn = _get_db()

    row = conn.execute(
        """SELECT
               COUNT(*) AS total,
               SUM(CASE WHEN triage_level='L1' THEN 1 ELSE 0 END) AS l1,
               SUM(CASE WHEN triage_level='L2' THEN 1 ELSE 0 END) AS l2,
               SUM(CASE WHEN from_cache=1 THEN 1 ELSE 0 END) AS cached,
               AVG(confidence_score) AS avg_confidence
           FROM conversations
           WHERE org_id = ? AND role = 'assistant'""",
        (org_id,),
    ).fetchone()

    fb = conn.execute(
        """SELECT
               SUM(CASE WHEN rating='positive' THEN 1 ELSE 0 END) AS positive,
               SUM(CASE WHEN rating='negative' THEN 1 ELSE 0 END) AS negative
           FROM feedback WHERE org_id = ?""",
        (org_id,),
    ).fetchone()
    conn.close()

    total = row["total"] or 0
    l1 = row["l1"] or 0
    l2 = row["l2"] or 0
    cached = row["cached"] or 0
    positive = fb["positive"] or 0
    negative = fb["negative"] or 0
    fb_total = positive + negative

    return {
        "total_queries": total,
        "ai_resolved": l1,
        "escalated": l2,
        "automation_rate": round((l1 / total) * 100, 1) if total else 0.0,
        "avg_confidence": round((row["avg_confidence"] or 0.0) * 100, 1),
        "cache_hit_rate": round((cached / total) * 100, 1) if total else 0.0,
        "satisfaction_rate": round((positive / fb_total) * 100, 1) if fb_total else None,
        "positive_feedback": positive,
        "negative_feedback": negative,
    }


def resolution_trend(org_id: str, days: int = 14) -> list[dict]:
    """AI-resolved vs. escalated counts per day, for the last N days."""
    conn = _get_db()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT substr(timestamp,1,10) AS day, triage_level, COUNT(*) AS n
           FROM conversations
           WHERE org_id = ? AND role='assistant' AND timestamp >= ?
           GROUP BY day, triage_level ORDER BY day ASC""",
        (org_id, since),
    ).fetchall()
    conn.close()

    by_day: dict[str, dict] = {}
    for r in rows:
        d = by_day.setdefault(r["day"], {"date": r["day"], "ai_resolved": 0, "escalated": 0})
        if r["triage_level"] == "L1":
            d["ai_resolved"] += r["n"]
        elif r["triage_level"] == "L2":
            d["escalated"] += r["n"]
    return sorted(by_day.values(), key=lambda x: x["date"])


def query_categories(org_id: str) -> list[dict]:
    """Best-effort category breakdown, inferred from query keywords —
    labeled clearly in the UI as keyword-based classification."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT content FROM conversations WHERE org_id = ? AND role = 'user'",
        (org_id,),
    ).fetchall()
    conn.close()

    counts = {k: 0 for k in _CATEGORY_KEYWORDS}
    counts["Other"] = 0
    for r in rows:
        text = (r["content"] or "").lower()
        matched = False
        for cat, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                counts[cat] += 1
                matched = True
                break
        if not matched:
            counts["Other"] += 1
    return [{"category": k, "count": v} for k, v in counts.items() if v > 0] or \
           [{"category": k, "count": 0} for k in counts]


def escalation_reasons(org_id: str) -> list[dict]:
    """Breakdown of why queries were escalated to L2, parsed from the
    triage_reason text the RAG pipeline already stores per message."""
    conn = _get_db()
    rows = conn.execute(
        """SELECT triage_reason FROM conversations
           WHERE org_id = ? AND role='assistant' AND triage_level='L2'""",
        (org_id,),
    ).fetchall()
    conn.close()

    buckets = {"Low confidence": 0, "Security": 0, "Complexity": 0, "Other": 0}
    for r in rows:
        reason = (r["triage_reason"] or "").lower()
        if "confidence" in reason or "coverage" in reason:
            buckets["Low confidence"] += 1
        elif any(k in reason for k in ["fraud", "security", "breach", "hack"]):
            buckets["Security"] += 1
        elif "complex" in reason or "word" in reason:
            buckets["Complexity"] += 1
        else:
            buckets["Other"] += 1
    return [{"reason": k, "count": v} for k, v in buckets.items() if v > 0] or \
           [{"reason": k, "count": 0} for k in buckets]


def cache_performance(org_id: str) -> dict:
    conn = _get_db()
    row = conn.execute(
        """SELECT
               SUM(CASE WHEN from_cache=1 THEN 1 ELSE 0 END) AS hits,
               SUM(CASE WHEN from_cache=0 THEN 1 ELSE 0 END) AS misses
           FROM conversations WHERE org_id = ? AND role='assistant'""",
        (org_id,),
    ).fetchone()
    conn.close()
    hits = row["hits"] or 0
    misses = row["misses"] or 0
    total = hits + misses
    return {
        "hits": hits,
        "misses": misses,
        "hit_rate": round((hits / total) * 100, 1) if total else 0.0,
    }
