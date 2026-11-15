# agent/memory.py
# Contextual memory using ChromaDB (RAG) + SQLite (history)

import sqlite3
import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Optional, List, Tuple

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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "data", "startup_history.db"))
DB_PATH = DEFAULT_DB_PATH

def get_db_path() -> str:
    """Return the active database path, allowing runtime environment overrides or patched DB_PATH."""
    import agent.memory as m
    if getattr(m, "DB_PATH", None) != DEFAULT_DB_PATH:
        return m.DB_PATH
    return os.environ.get("DB_PATH", DEFAULT_DB_PATH)


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class NotFoundError(DatabaseError):
    """Resource not found."""
    pass


@contextmanager
def get_db_connection():
    """Context-managed SQLite connection with foreign keys and WAL mode enabled."""
    db_file = get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
    conn = sqlite3.connect(db_file)
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS practice_turns (
                id              TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL,
                turn_index      INTEGER NOT NULL,
                question        TEXT NOT NULL,
                answer          TEXT,
                evaluation_json TEXT,
                score           INTEGER,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(session_id) REFERENCES pitch_sessions(id) ON DELETE CASCADE
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

        # Migration 2: startup_plans run_summary & owner_id & research_plan
        cursor.execute("PRAGMA table_info(startup_plans)")
        plan_cols = {r[1] for r in cursor.fetchall()}
        if "run_summary" not in plan_cols:
            cursor.execute("ALTER TABLE startup_plans ADD COLUMN run_summary TEXT")
        if "owner_id" not in plan_cols:
            cursor.execute("ALTER TABLE startup_plans ADD COLUMN owner_id TEXT")
        if "research_plan" not in plan_cols:
            cursor.execute("ALTER TABLE startup_plans ADD COLUMN research_plan TEXT")

        # Migration 3: export_history status & reason
        cursor.execute("PRAGMA table_info(export_history)")
        export_cols = {r[1] for r in cursor.fetchall()}
        if "status" not in export_cols:
            cursor.execute("ALTER TABLE export_history ADD COLUMN status TEXT DEFAULT 'ok'")
        if "reason" not in export_cols:
            cursor.execute("ALTER TABLE export_history ADD COLUMN reason TEXT")

        # Migration 4: pitch_sessions extensions
        cursor.execute("PRAGMA table_info(pitch_sessions)")
        pitch_cols = {r[1] for r in cursor.fetchall()}
        for col, col_def in [
            ("status", "TEXT DEFAULT 'active'"),
            ("num_questions", "INTEGER DEFAULT 5"),
            ("language", "TEXT DEFAULT 'en'"),
            ("transcript_path", "TEXT"),
            ("summary_json", "TEXT"),
            ("finished_at", "TEXT"),
        ]:
            if col not in pitch_cols:
                cursor.execute(f"ALTER TABLE pitch_sessions ADD COLUMN {col} {col_def}")

        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
        cursor.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (4)")
        logger.info("[DB] SQLite database initialized and migrations applied.")


# Alias for backward compatibility
init_database = init_db


def save_startup_plan(
    plan_id: str,
    idea: str,
    title: str,
    plan_data: dict,
    run_summary: Optional[dict] = None,
    owner_id: Optional[str] = None,
    research_plan: Optional[dict] = None
) -> bool:
    """Save a completed startup plan to SQLite."""
    try:
        summary_json = json.dumps(run_summary) if run_summary else None
        data_json = json.dumps(plan_data, ensure_ascii=False)
        r_plan = research_plan if research_plan is not None else plan_data.get("research_plan")
        research_plan_json = json.dumps(r_plan, ensure_ascii=False) if isinstance(r_plan, (dict, list)) else (str(r_plan) if r_plan else None)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO startup_plans (id, idea, title, plan_data, run_summary, owner_id, research_plan)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    idea = excluded.idea,
                    title = excluded.title,
                    plan_data = excluded.plan_data,
                    run_summary = COALESCE(excluded.run_summary, startup_plans.run_summary),
                    owner_id = COALESCE(excluded.owner_id, startup_plans.owner_id),
                    research_plan = COALESCE(excluded.research_plan, startup_plans.research_plan)
                """,
                (plan_id, idea, title, data_json, summary_json, owner_id, research_plan_json),
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
            # Check if research_plan column exists in this connection
            cursor.execute("PRAGMA table_info(startup_plans)")
            cols = {r[1] for r in cursor.fetchall()}
            has_research_plan = "research_plan" in cols

            if has_research_plan:
                select_sql = "SELECT id, idea, title, plan_data, created_at, run_summary, owner_id, research_plan FROM startup_plans WHERE id = ?"
            else:
                select_sql = "SELECT id, idea, title, plan_data, created_at, run_summary, owner_id, NULL FROM startup_plans WHERE id = ?"

            if owner_id:
                select_sql += " AND (owner_id = ? OR owner_id IS NULL)"
                cursor.execute(select_sql, (plan_id, owner_id))
            else:
                cursor.execute(select_sql, (plan_id,))

            row = cursor.fetchone()
            if row:
                plan = json.loads(row[3]) if row[3] else {}
                plan["id"] = row[0]
                plan["idea"] = row[1]
                plan["title"] = row[2]
                plan["created_at"] = row[4]
                plan["run_summary"] = json.loads(row[5]) if row[5] else None
                plan["owner_id"] = row[6]
                if row[7]:
                    try:
                        plan["research_plan"] = json.loads(row[7])
                    except Exception:
                        plan["research_plan"] = row[7]
                elif "research_plan" not in plan:
                    plan["research_plan"] = None
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


def create_pitch_session(
    session_id: str,
    plan_id: str,
    persona: str,
    messages: list,
    num_questions: int = 5,
    language: str = "en",
) -> bool:
    """Create a new pitch practice session record."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pitch_sessions (id, plan_id, persona, messages, score, status, num_questions, language)
                VALUES (?, ?, ?, ?, 0, 'active', ?, ?)
                """,
                (session_id, plan_id, persona, json.dumps(messages, ensure_ascii=False), num_questions, language),
            )
        return True
    except Exception as e:
        logger.error(f"[DB] Create pitch session error: {e}")
        return False


def get_pitch_session(session_id: str) -> Optional[dict]:
    """Retrieve a pitch session record by id."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, plan_id, persona, messages, score, created_at, status, num_questions, language, transcript_path, summary_json, finished_at
                FROM pitch_sessions
                WHERE id = ?
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "plan_id": row[1],
                "persona": row[2],
                "messages": json.loads(row[3]) if row[3] else [],
                "score": row[4],
                "created_at": row[5],
                "status": row[6] or "active",
                "num_questions": row[7] or 5,
                "language": row[8] or "en",
                "transcript_path": row[9],
                "summary": json.loads(row[10]) if row[10] else None,
                "finished_at": row[11],
            }
    except Exception as e:
        logger.error(f"[DB] Get pitch session error: {e}")
        return None


def update_pitch_session(
    session_id: str,
    messages: list,
    score: int = 0,
    status: str = "active",
    summary: Optional[dict] = None,
    transcript_path: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> bool:
    """Update messages, score, status, and summary of a pitch session."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            summary_json = json.dumps(summary, ensure_ascii=False) if summary else None
            cursor.execute(
                """
                UPDATE pitch_sessions
                SET messages = ?, score = ?, status = ?, summary_json = COALESCE(?, summary_json),
                    transcript_path = COALESCE(?, transcript_path), finished_at = COALESCE(?, finished_at)
                WHERE id = ?
                """,
                (
                    json.dumps(messages, ensure_ascii=False),
                    score,
                    status,
                    summary_json,
                    transcript_path,
                    finished_at,
                    session_id,
                ),
            )
        return True
    except Exception as e:
        logger.error(f"[DB] Update pitch session error: {e}")
        return False


def save_practice_turn(
    turn_id: str,
    session_id: str,
    turn_index: int,
    question: str,
    answer: str,
    evaluation: dict,
    score: int,
) -> bool:
    """Record a normalized turn in practice_turns table."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO practice_turns (id, session_id, turn_index, question, answer, evaluation_json, score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, turn_index, question, answer, json.dumps(evaluation, ensure_ascii=False), score),
            )
        return True
    except Exception as e:
        logger.error(f"[DB] Save practice turn error: {e}")
        return False


def get_session_turns(session_id: str) -> list:
    """Retrieve all turns for a practice session in sequential order."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT turn_index, question, answer, evaluation_json, score, created_at
                FROM practice_turns
                WHERE session_id = ?
                ORDER BY turn_index ASC
                """,
                (session_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "turn_index": r[0],
                    "question": r[1],
                    "answer": r[2],
                    "evaluation": json.loads(r[3]) if r[3] else {},
                    "score": r[4],
                    "created_at": r[5],
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"[DB] Get session turns error: {e}")
        return []


def cleanup_plan_files(plan_id: str, extra_paths: Optional[List[str]] = None) -> List[str]:
    """
    Safely delete all generated files associated with a plan from disk.
    Guarantees:
    - Path traversal protection: Paths must resolve strictly within DATA_DIR.
    - Files already missing are safely ignored.
    - User-supplied arbitrary paths are never accepted.
    Returns list of paths successfully removed.
    """
    removed = []
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.abspath(os.path.join(base_dir, "data"))

    # Standard known file targets for a plan
    standard_targets = [
        os.path.join(data_dir, "presentations", f"{plan_id}.pptx"),
        os.path.join(data_dir, "documents", f"{plan_id}.pdf"),
        os.path.join(data_dir, "documents", f"{plan_id}.docx"),
        os.path.join(data_dir, "documents", f"investor_report_{plan_id}.pdf"),
        os.path.join(data_dir, "architectures", f"{plan_id}.html"),
        os.path.join(data_dir, "architectures", f"{plan_id}.svg"),
        os.path.join(data_dir, "roadmaps", f"{plan_id}.html"),
        os.path.join(data_dir, "financials", f"{plan_id}.xlsx"),
        os.path.join(data_dir, "audio", f"{plan_id}_narration.mp3"),
        os.path.join(data_dir, "audio", f"{plan_id}.mp3"),
    ]

    all_targets = list(standard_targets)
    if extra_paths:
        for ep in extra_paths:
            if ep and isinstance(ep, str):
                resolved = os.path.abspath(os.path.join(base_dir, ep) if not os.path.isabs(ep) else ep)
                all_targets.append(resolved)

    # Process individual files
    for target in all_targets:
        try:
            norm_target = os.path.abspath(target)
            # Path traversal protection: target must be inside data_dir
            if os.path.commonpath([data_dir, norm_target]) != data_dir:
                logger.warning(f"[Security] Rejected deletion of path outside data root: {target}")
                continue
            if os.path.isfile(norm_target):
                os.remove(norm_target)
                removed.append(norm_target)
        except Exception as e:
            logger.warning(f"[Cleanup] Error deleting file {target}: {e}")

    # Remove plan pitch directory if it exists: ./data/pitch/{plan_id}
    pitch_dir = os.path.join(data_dir, "pitch", plan_id)
    if os.path.exists(pitch_dir):
        try:
            norm_pitch = os.path.abspath(pitch_dir)
            if os.path.commonpath([data_dir, norm_pitch]) == data_dir:
                shutil.rmtree(norm_pitch, ignore_errors=True)
                removed.append(norm_pitch)
        except Exception as e:
            logger.warning(f"[Cleanup] Error deleting directory {pitch_dir}: {e}")

    return removed


def cleanup_plan_chroma(plan_id: str) -> bool:
    """Safely delete vector memory chunks for this plan/session."""
    try:
        collection = get_chroma_collection()
        if collection.count() > 0:
            collection.delete(where={"session_id": plan_id})
        return True
    except Exception as e:
        logger.warning(f"[Memory] Failed to delete ChromaDB docs for plan {plan_id}: {e}")
        return False


def delete_plan_by_id(plan_id: str, owner_id: Optional[str] = None) -> Tuple[bool, str]:
    """
    Delete a plan and all related records in one atomic DB transaction,
    then clean up ChromaDB vectors and generated files on disk.
    Returns (success: bool, message: str).
    """
    if not plan_id or not isinstance(plan_id, str):
        return False, "Invalid plan ID"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # 1. Verify plan exists and check ownership if owner_id provided
            cursor.execute("SELECT id, owner_id FROM startup_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return False, "Plan not found"

            plan_owner = row[1]
            if owner_id and plan_owner and plan_owner != owner_id:
                return False, "Plan not found"

            # 2. Collect DB-recorded file paths for disk cleanup
            extra_files = []
            try:
                cursor.execute("SELECT file_path FROM audio_generations WHERE plan_id = ?", (plan_id,))
                for (fp,) in cursor.fetchall():
                    if fp:
                        extra_files.append(fp)
            except Exception:
                pass

            try:
                cursor.execute("SELECT transcript_path FROM pitch_sessions WHERE plan_id = ?", (plan_id,))
                for (tp,) in cursor.fetchall():
                    if tp:
                        extra_files.append(tp)
            except Exception:
                pass

            # 3. Explicitly delete child rows in cascade order to satisfy FK constraints
            cursor.execute("""
                DELETE FROM practice_turns 
                WHERE session_id IN (SELECT id FROM pitch_sessions WHERE plan_id = ?)
            """, (plan_id,))
            cursor.execute("DELETE FROM pitch_sessions WHERE plan_id = ?", (plan_id,))
            cursor.execute("DELETE FROM audio_generations WHERE plan_id = ?", (plan_id,))
            cursor.execute("DELETE FROM export_history WHERE plan_id = ?", (plan_id,))

            # 4. Delete the parent plan
            cursor.execute("DELETE FROM startup_plans WHERE id = ?", (plan_id,))
            if cursor.rowcount == 0:
                return False, "Plan not found"

    except Exception as e:
        logger.error(f"[DB] Delete plan transaction error for {plan_id}: {e}")
        return False, f"Database error deleting plan: {str(e)}"

    # 5. DB transaction committed successfully -> clean up Chroma vectors & files
    cleanup_plan_chroma(plan_id)
    cleanup_plan_files(plan_id, extra_files)

    return True, "Plan and all associated data deleted successfully."


def deduplicate_history(time_window_minutes: int = 5, owner_id: Optional[str] = None) -> int:
    """
    Remove duplicate plans that share identical trimmed idea text,
    keeping only the latest one. Calls delete_plan_by_id for each duplicate
    to ensure full cascade and file cleanup.
    Returns the number of deleted duplicate plans.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if owner_id:
                cursor.execute(
                    "SELECT id, idea, created_at FROM startup_plans WHERE owner_id = ? OR owner_id IS NULL ORDER BY created_at DESC",
                    (owner_id,)
                )
            else:
                cursor.execute("SELECT id, idea, created_at FROM startup_plans ORDER BY created_at DESC")
            rows = cursor.fetchall()

        seen = {}
        to_delete = []
        for plan_id, idea, created_at in rows:
            norm_idea = (idea or "").strip().lower()
            if norm_idea in seen:
                to_delete.append(plan_id)
            else:
                seen[norm_idea] = created_at

        deleted_count = 0
        for pid in to_delete:
            ok, _ = delete_plan_by_id(pid, owner_id=owner_id)
            if ok:
                deleted_count += 1

        return deleted_count
    except Exception as e:
        logger.error(f"[DB] Deduplicate history error: {e}")
        return 0




