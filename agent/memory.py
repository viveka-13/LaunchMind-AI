# agent/memory.py
# Contextual memory using ChromaDB (RAG) + SQLite (history)

import sqlite3
import json
import os
import uuid
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────
# ChromaDB — Vector Memory for RAG Retrieval
# ─────────────────────────────────────────────

_chroma_client = None
_collection = None


def get_chroma_collection():
    """Lazy-load ChromaDB to avoid startup delay."""
    global _chroma_client, _collection
    if _collection is None:
        import chromadb
        os.makedirs("./data/chroma_db", exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path="./data/chroma_db")
        _collection = _chroma_client.get_or_create_collection(
            name="startup_research",
            metadata={"description": "AutoStartup AI research memory"},
        )
    return _collection


def store_research(session_id: str, idea: str, research_type: str, content: str):
    """
    Store research in ChromaDB for RAG retrieval.
    Each piece of research is stored as a document with metadata.
    """
    try:
        collection = get_chroma_collection()
        doc_id = f"{session_id}_{research_type}_{uuid.uuid4().hex[:8]}"
        # Truncate to avoid exceeding limits
        content_chunk = content[:2000] if len(content) > 2000 else content
        collection.add(
            documents=[content_chunk],
            metadatas=[{
                "session_id": session_id,
                "idea": idea[:200],
                "type": research_type,
                "timestamp": datetime.utcnow().isoformat(),
            }],
            ids=[doc_id],
        )
        return True
    except Exception as e:
        print(f"[Memory] ChromaDB store error: {e}")
        return False


def retrieve_similar(query: str, session_id: str, n_results: int = 3) -> str:
    """
    RAG Retrieval: Find similar research stored for this session.
    Returns concatenated relevant context.
    """
    try:
        collection = get_chroma_collection()
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count()),
            where={"session_id": session_id} if collection.count() > 0 else None,
        )
        if results and results["documents"]:
            docs = results["documents"][0]
            return "\n\n---\n\n".join(docs)
        return ""
    except Exception as e:
        print(f"[Memory] ChromaDB retrieve error: {e}")
        return ""


# ─────────────────────────────────────────────
# SQLite — History Storage & Repository
# ─────────────────────────────────────────────

from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "./data/startup_history.db")


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class NotFoundError(DatabaseError):
    """Resource not found."""
    pass


@contextmanager
def get_db_connection():
    """Context-managed SQLite connection with foreign keys and WAL mode enabled."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"[DB] Transaction rollback due to error: {e}")
        raise DatabaseError(f"Database transaction failed: {e}") from e
    finally:
        conn.close()


def init_db():
    """Initialize database tables with schema versioning and safe migrations."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Schema version table for ordered migrations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version     INTEGER PRIMARY KEY,
                applied_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        # 1. Base tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS startup_plans (
                id          TEXT PRIMARY KEY,
                idea        TEXT NOT NULL,
                title       TEXT,
                plan_data   TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pitch_sessions (
                id          TEXT PRIMARY KEY,
                plan_id     TEXT NOT NULL,
                persona     TEXT NOT NULL,
                messages    TEXT NOT NULL,
                score       INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(plan_id) REFERENCES startup_plans(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audio_generations (
                id          TEXT PRIMARY KEY,
                plan_id     TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                status      TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(plan_id) REFERENCES startup_plans(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS export_history (
                id          TEXT PRIMARY KEY,
                plan_id     TEXT NOT NULL,
                export_type TEXT NOT NULL,
                export_url  TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(plan_id) REFERENCES startup_plans(id) ON DELETE CASCADE
            )
        """)

        # Migrations
        # Migration 1: audio_generations details
        cursor.execute("PRAGMA table_info(audio_generations)")
        audio_cols = {r[1] for r in cursor.fetchall()}
        for col, col_type in [
            ("reason", "TEXT"),
            ("duration_seconds", "REAL"),
            ("provider", "TEXT"),
            ("voice", "TEXT"),
        ]:
            if col not in audio_cols:
                cursor.execute(f"ALTER TABLE audio_generations ADD COLUMN {col} {col_type}")

        # Migration 2: startup_plans run_summary & owner_id
        cursor.execute("PRAGMA table_info(startup_plans)")
        plan_cols = {r[1] for r in cursor.fetchall()}
        if "run_summary" not in plan_cols:
            cursor.execute("ALTER TABLE startup_plans ADD COLUMN run_summary TEXT")
        if "owner_id" not in plan_cols:
            cursor.execute("ALTER TABLE startup_plans ADD COLUMN owner_id TEXT")

        # Migration 3: export_history status & reason
        cursor.execute("PRAGMA table_info(export_history)")
        export_cols = {r[1] for r in cursor.fetchall()}
        if "status" not in export_cols:
            cursor.execute("ALTER TABLE export_history ADD COLUMN status TEXT DEFAULT 'ok'")
        if "reason" not in export_cols:
            cursor.execute("ALTER TABLE export_history ADD COLUMN reason TEXT")

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
        logger.info("[DB] SQLite database initialized and migrations applied.")


# Alias for backward compatibility
init_database = init_db


def save_startup_plan(
    plan_id: str,
    idea: str,
    title: str,
    plan_data: dict,
    run_summary: Optional[dict] = None,
    owner_id: Optional[str] = None
) -> bool:
    """Save a completed startup plan to SQLite."""
    try:
        summary_json = json.dumps(run_summary) if run_summary else None
        data_json = json.dumps(plan_data, ensure_ascii=False)
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO startup_plans (id, idea, title, plan_data, run_summary, owner_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    idea = excluded.idea,
                    title = excluded.title,
                    plan_data = excluded.plan_data,
                    run_summary = COALESCE(excluded.run_summary, startup_plans.run_summary),
                    owner_id = COALESCE(excluded.owner_id, startup_plans.owner_id)
                """,
                (plan_id, idea, title, data_json, summary_json, owner_id),
            )
        return True
    except Exception as e:
        logger.error(f"[DB] Save plan error: {e}")
        return False


def get_all_plans(owner_id: Optional[str] = None) -> list:
    """Retrieve all startup plans from history (summary only). If owner_id given, filter by owner."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if owner_id:
                cursor.execute("""
                    SELECT id, idea, title, created_at, owner_id
                    FROM startup_plans
                    WHERE owner_id = ? OR owner_id IS NULL
                    ORDER BY created_at DESC
                    LIMIT 50
                """, (owner_id,))
            else:
                cursor.execute("""
                    SELECT id, idea, title, created_at, owner_id
                    FROM startup_plans
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
            rows = cursor.fetchall()
            return [
                {"id": r[0], "idea": r[1], "title": r[2], "created_at": r[3], "owner_id": r[4]}
                for r in rows
            ]
    except Exception as e:
        logger.error(f"[DB] Get all plans error: {e}")
        return []


def get_plan_by_id(plan_id: str, owner_id: Optional[str] = None) -> Optional[dict]:
    """Retrieve a specific startup plan by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if owner_id:
                cursor.execute(
                    "SELECT id, idea, title, plan_data, created_at, run_summary, owner_id FROM startup_plans WHERE id = ? AND (owner_id = ? OR owner_id IS NULL)",
                    (plan_id, owner_id),
                )
            else:
                cursor.execute(
                    "SELECT id, idea, title, plan_data, created_at, run_summary, owner_id FROM startup_plans WHERE id = ?",
                    (plan_id,),
                )
            row = cursor.fetchone()
            if row:
                plan = json.loads(row[3]) if row[3] else {}
                plan["id"] = row[0]
                plan["idea"] = row[1]
                plan["title"] = row[2]
                plan["created_at"] = row[4]
                plan["run_summary"] = json.loads(row[5]) if row[5] else None
                plan["owner_id"] = row[6]
                return plan
            return None
    except Exception as e:
        logger.error(f"[DB] Get plan by ID error: {e}")
        return None


def save_audio_generation(plan_id: str, status_obj: dict) -> bool:
    """Save audio generation status object to SQLite."""
    try:
        gen_id = str(uuid.uuid4())
        file_path = status_obj.get("path") or ""
        status = status_obj.get("status") or "failed"
        reason = status_obj.get("reason")
        duration = status_obj.get("duration_seconds")
        provider = status_obj.get("provider") or ""
        voice = status_obj.get("voice") or ""

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audio_generations 
                (id, plan_id, file_path, status, reason, duration_seconds, provider, voice)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (gen_id, plan_id, file_path, status, reason, duration, provider, voice),
            )
        return True
    except Exception as e:
        logger.error(f"[DB] Save audio generation error: {e}")
        return False


def get_audio_generation(plan_id: str) -> Optional[dict]:
    """Retrieve the latest audio generation for a plan."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, plan_id, file_path, status, reason, duration_seconds, provider, voice, created_at
                FROM audio_generations
                WHERE plan_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (plan_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "plan_id": row[1],
                    "file_path": row[2],
                    "status": row[3],
                    "reason": row[4],
                    "duration_seconds": row[5],
                    "provider": row[6],
                    "voice": row[7],
                    "created_at": row[8],
                }
            return None
    except Exception as e:
        logger.error(f"[DB] Get audio generation error: {e}")
        return None


def save_export_record(plan_id: str, export_type: str, export_url: str, status: str = "ok", reason: Optional[str] = None) -> bool:
    """Record an export result in the database."""
    try:
        rec_id = str(uuid.uuid4())
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO export_history (id, plan_id, export_type, export_url, status, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rec_id, plan_id, export_type, export_url, status, reason),
            )
        return True
    except Exception as e:
        logger.error(f"[DB] Save export record error: {e}")
        return False


def get_export_history(plan_id: str) -> list:
    """Retrieve all export history records for a plan."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, plan_id, export_type, export_url, status, reason, created_at
                FROM export_history
                WHERE plan_id = ?
                ORDER BY created_at DESC
                """,
                (plan_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "plan_id": r[1],
                    "export_type": r[2],
                    "export_url": r[3],
                    "status": r[4],
                    "reason": r[5],
                    "created_at": r[6],
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"[DB] Get export history error: {e}")
        return []


