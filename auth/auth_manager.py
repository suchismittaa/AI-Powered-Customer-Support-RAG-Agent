"""
auth/auth_manager.py — User Authentication and Multi-Tenancy Manager

Handles user registration, login, JWT session tokens, and per-user
conversation isolation. Each user gets their own conversation history,
feedback log, and query cache — fully isolated from other users.

Storage: SQLite (local file, no external DB needed).
Sessions: JWT tokens with configurable expiry.
Passwords: Bcrypt hashed, never stored in plaintext.
"""

import os
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

import jwt
import bcrypt

# ── Constants ─────────────────────────────────────────────────────────────────
DB_PATH = "./auth/users.db"
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24
MIN_PASSWORD_LENGTH = 8


@dataclass
class User:
    """Represents an authenticated user record."""
    id: int
    email: str
    name: str
    role: str          # "admin" | "agent" | "viewer"
    org_id: str        # Organization/tenant identifier
    created_at: str
    last_login: Optional[str] = None
    is_active: bool = True


@dataclass
class SessionToken:
    """JWT session token payload and metadata."""
    token: str
    user_id: int
    email: str
    name: str
    role: str
    org_id: str
    expires_at: str


def _get_db() -> sqlite3.Connection:
    """
    Open a SQLite connection with row factory for dict-like access.

    Returns:
        sqlite3.Connection with row_factory set.
    """
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db() -> None:
    """
    Create database tables if they don't exist.

    Tables created:
        users           — User accounts with hashed passwords
        conversations   — Per-user chat history (multi-tenancy)
        feedback        — Per-user answer feedback logs
    """
    conn = _get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    UNIQUE NOT NULL,
            name        TEXT    NOT NULL,
            password_hash TEXT  NOT NULL,
            role        TEXT    DEFAULT 'agent',
            org_id      TEXT    NOT NULL DEFAULT 'default',
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT    NOT NULL,
            last_login  TEXT
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            org_id      TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            sources     TEXT,
            triage_level TEXT,
            triage_reason TEXT,
            confidence_score REAL,
            from_cache  INTEGER DEFAULT 0,
            timestamp   TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            org_id      TEXT    NOT NULL,
            query       TEXT    NOT NULL,
            answer      TEXT    NOT NULL,
            rating      TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
        CREATE INDEX IF NOT EXISTS idx_conv_org  ON conversations(org_id);
        CREATE INDEX IF NOT EXISTS idx_feed_user ON feedback(user_id);
    """)

    conn.commit()
    conn.close()

    # Seed a default demo admin if no users exist
    _seed_demo_users()


def _seed_demo_users() -> None:
    """
    Create default demo accounts if the database is empty.

    Demo accounts:
        admin@demo.com / Admin@1234  (role: admin,  org: demo-corp)
        agent@demo.com / Agent@1234  (role: agent,  org: demo-corp)
        viewer@demo.com / View@1234  (role: viewer, org: demo-corp)
    """
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

    if count > 0:
        return

    demo_users = [
        ("admin@demo.com",  "Admin User",   "Admin@1234",  "admin",  "demo-corp"),
        ("agent@demo.com",  "Support Agent","Agent@1234",  "agent",  "demo-corp"),
        ("viewer@demo.com", "View Only",    "View@1234",   "viewer", "demo-corp"),
    ]
    for email, name, password, role, org_id in demo_users:
        register_user(email, name, password, role, org_id)


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Args:
        password: Plaintext password string.

    Returns:
        Bcrypt hash string.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against its bcrypt hash.

    Args:
        password: Plaintext password to check.
        hashed: Stored bcrypt hash.

    Returns:
        True if password matches, False otherwise.
    """
    return bcrypt.checkpw(password.encode(), hashed.encode())


def register_user(
    email: str,
    name: str,
    password: str,
    role: str = "agent",
    org_id: str = "default",
) -> tuple[bool, str]:
    """
    Register a new user account.

    Args:
        email: Unique email address.
        name: Display name.
        password: Plaintext password (will be hashed).
        role: User role — 'admin', 'agent', or 'viewer'.
        org_id: Organization/tenant identifier.

    Returns:
        Tuple of (success: bool, message: str).
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    if not email or "@" not in email:
        return False, "Invalid email address."

    try:
        conn = _get_db()
        conn.execute(
            """INSERT INTO users (email, name, password_hash, role, org_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                email.lower().strip(),
                name.strip(),
                hash_password(password),
                role,
                org_id,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, f"Registration failed: {e}"


def login_user(email: str, password: str) -> tuple[bool, str, Optional[SessionToken]]:
    """
    Authenticate a user and return a JWT session token.

    Args:
        email: User's email address.
        password: Plaintext password to verify.

    Returns:
        Tuple of (success: bool, message: str, session_token or None).
    """
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1",
        (email.lower().strip(),),
    ).fetchone()

    if not row:
        conn.close()
        return False, "Invalid email or password.", None

    if not verify_password(password, row["password_hash"]):
        conn.close()
        return False, "Invalid email or password.", None

    # Update last login
    conn.execute(
        "UPDATE users SET last_login = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), row["id"]),
    )
    conn.commit()
    conn.close()

    # Generate JWT
    expiry = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "user_id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "org_id": row["org_id"],
        "exp": expiry,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    session = SessionToken(
        token=token,
        user_id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        org_id=row["org_id"],
        expires_at=expiry.isoformat(),
    )
    return True, "Login successful.", session


def verify_token(token: str) -> Optional[dict]:
    """
    Verify a JWT token and return its decoded payload.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload dict if valid, None if invalid or expired.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_by_id(user_id: int) -> Optional[User]:
    """
    Fetch a user record by their ID.

    Args:
        user_id: The user's integer ID.

    Returns:
        User dataclass instance, or None if not found.
    """
    conn = _get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        org_id=row["org_id"],
        created_at=row["created_at"],
        last_login=row["last_login"],
        is_active=bool(row["is_active"]),
    )


# ── Conversation History (multi-tenant) ──────────────────────────────────────

def save_message(
    user_id: int,
    org_id: str,
    role: str,
    content: str,
    sources: list = None,
    triage_level: str = None,
    triage_reason: str = None,
    confidence_score: float = None,
    from_cache: bool = False,
) -> None:
    """
    Persist a single chat message to the user's conversation history.

    Args:
        user_id: ID of the user who sent/received the message.
        org_id: Organization identifier for tenant isolation.
        role: 'user' or 'assistant'.
        content: Message text content.
        sources: List of source filenames (for assistant messages).
        triage_level: L1 or L2 classification (for assistant messages).
        triage_reason: Triage classification explanation.
        confidence_score: Vector similarity score.
        from_cache: Whether response was served from cache.
    """
    conn = _get_db()
    conn.execute(
        """INSERT INTO conversations
           (user_id, org_id, role, content, sources, triage_level, triage_reason,
            confidence_score, from_cache, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            org_id,
            role,
            content,
            json.dumps(sources or []),
            triage_level,
            triage_reason,
            confidence_score,
            int(from_cache),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_conversation_history(user_id: int, org_id: str, limit: int = 50) -> list[dict]:
    """
    Retrieve a user's conversation history, scoped to their organization.

    Args:
        user_id: User's integer ID.
        org_id: Organization identifier (enforces tenant isolation).
        limit: Maximum number of messages to return (most recent first).

    Returns:
        List of message dicts ordered from oldest to newest.
    """
    conn = _get_db()
    rows = conn.execute(
        """SELECT * FROM conversations
           WHERE user_id = ? AND org_id = ?
           ORDER BY id DESC LIMIT ?""",
        (user_id, org_id, limit),
    ).fetchall()
    conn.close()

    messages = []
    for row in reversed(rows):
        msg = {
            "role": row["role"],
            "content": row["content"],
            "timestamp": row["timestamp"],
        }
        if row["role"] == "assistant":
            msg.update({
                "sources": json.loads(row["sources"] or "[]"),
                "triage_level": row["triage_level"],
                "triage_reason": row["triage_reason"],
                "confidence_score": row["confidence_score"],
                "from_cache": bool(row["from_cache"]),
            })
        messages.append(msg)
    return messages


def clear_conversation_history(user_id: int, org_id: str) -> None:
    """
    Delete all conversation history for a user within their organization.

    Args:
        user_id: User's integer ID.
        org_id: Organization identifier (enforces tenant isolation).
    """
    conn = _get_db()
    conn.execute(
        "DELETE FROM conversations WHERE user_id = ? AND org_id = ?",
        (user_id, org_id),
    )
    conn.commit()
    conn.close()


def save_feedback(user_id: int, org_id: str, query: str, answer: str, rating: str) -> None:
    """
    Save a user's 👍/👎 feedback on an AI response.

    Args:
        user_id: User's integer ID.
        org_id: Organization identifier.
        query: The original customer query.
        answer: The AI-generated answer that was rated.
        rating: 'positive' or 'negative'.
    """
    conn = _get_db()
    conn.execute(
        """INSERT INTO feedback (user_id, org_id, query, answer, rating, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, org_id, query, answer[:500], rating, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_org_stats(org_id: str) -> dict:
    """
    Return aggregate statistics for an organization (for the admin dashboard).

    Args:
        org_id: Organization identifier.

    Returns:
        Dict with total_queries, l1_count, l2_count, avg_confidence,
        positive_feedback, negative_feedback, active_users counts.
    """
    conn = _get_db()

    stats = {}
    row = conn.execute(
        """SELECT
               COUNT(*)                                       AS total_queries,
               SUM(CASE WHEN triage_level='L1' THEN 1 ELSE 0 END) AS l1_count,
               SUM(CASE WHEN triage_level='L2' THEN 1 ELSE 0 END) AS l2_count,
               AVG(confidence_score)                          AS avg_confidence,
               SUM(CASE WHEN from_cache=1 THEN 1 ELSE 0 END) AS cached_count
           FROM conversations
           WHERE org_id = ? AND role = 'assistant'""",
        (org_id,),
    ).fetchone()

    stats.update(dict(row))

    fb = conn.execute(
        """SELECT
               SUM(CASE WHEN rating='positive' THEN 1 ELSE 0 END) AS positive,
               SUM(CASE WHEN rating='negative' THEN 1 ELSE 0 END) AS negative
           FROM feedback WHERE org_id = ?""",
        (org_id,),
    ).fetchone()
    stats["positive_feedback"] = fb["positive"] or 0
    stats["negative_feedback"] = fb["negative"] or 0

    stats["active_users"] = conn.execute(
        "SELECT COUNT(*) FROM users WHERE org_id = ? AND is_active = 1",
        (org_id,),
    ).fetchone()[0]

    conn.close()
    return stats


# Initialize DB on import
initialize_db()
