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
# SQLite — History Storage
# ─────────────────────────────────────────────

DB_PATH = "./data/startup_history.db"


def init_database():
    """Initialize SQLite database and create tables."""
    os.makedirs("./data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS startup_plans (
            id          TEXT PRIMARY KEY,
            idea        TEXT NOT NULL,
            title       TEXT,
            plan_data   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] SQLite initialized.")


def save_startup_plan(plan_id: str, idea: str, title: str, plan_data: dict) -> bool:
    """Save a completed startup plan to SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO startup_plans (id, idea, title, plan_data)
            VALUES (?, ?, ?, ?)
            """,
            (plan_id, idea, title, json.dumps(plan_data)),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] Save error: {e}")
        return False


def get_all_plans() -> list:
    """Retrieve all startup plans from history (summary only)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, idea, title, created_at
            FROM startup_plans
            ORDER BY created_at DESC
            LIMIT 20
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "idea": r[1], "title": r[2], "created_at": r[3]}
            for r in rows
        ]
    except Exception as e:
        print(f"[DB] Get all error: {e}")
        return []


def get_plan_by_id(plan_id: str) -> Optional[dict]:
    """Retrieve a specific startup plan by ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, idea, title, plan_data, created_at FROM startup_plans WHERE id = ?",
            (plan_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            plan = json.loads(row[3])
            plan["id"] = row[0]
            plan["idea"] = row[1]
            plan["created_at"] = row[4]
            return plan
        return None
    except Exception as e:
        print(f"[DB] Get by ID error: {e}")
        return None
