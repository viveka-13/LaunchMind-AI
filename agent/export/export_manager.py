# agent/export/export_manager.py
# Unified export coordinator for Google Docs, Google Slides, and Notion

import uuid
import logging
from typing import Optional, Dict, Any

from agent.export.google_slides import export_to_google_slides
from agent.export.google_docs import export_to_google_docs
from agent.export.notion_export import export_to_notion
from agent.memory import get_db_connection

logger = logging.getLogger(__name__)


def log_export(plan_id: str, export_type: str, url: Optional[str], status: str, reason: Optional[str] = None):
    """Log export execution to SQLite export_history table."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO export_history (id, plan_id, export_type, export_url, status, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), plan_id, export_type, url or "", status, reason)
            )
    except Exception as e:
        logger.warning(f"[ExportManager] Failed to log export: {e}")


def handle_export(
    plan_id: str,
    plan_data: dict,
    export_type: str,
    user_context: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Execute real export to the target service.
    Returns standard status object:
    {"status": "ok" | "skipped" | "failed", "reason": str | None, "url": str | None}
    """
    export_type = export_type.lower().strip()
    if export_type == "google_slides":
        res = export_to_google_slides(plan_id, plan_data, user_context)
    elif export_type == "google_docs":
        res = export_to_google_docs(plan_id, plan_data, user_context)
    elif export_type == "notion":
        res = export_to_notion(plan_id, plan_data, user_context)
    else:
        res = {
            "status": "failed",
            "reason": f"Unsupported export target: '{export_type}'. Supported: google_docs, google_slides, notion.",
            "url": None,
        }

    log_export(
        plan_id=plan_id,
        export_type=export_type,
        url=res.get("url"),
        status=res.get("status", "failed"),
        reason=res.get("reason"),
    )
    return res
