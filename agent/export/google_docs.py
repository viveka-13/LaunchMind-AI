# agent/export/google_docs.py
# Real Google Docs export using Google Docs API v1 and Google Drive API v3

import os
import json
import logging
from typing import Optional, Dict, Any

from googleapiclient.discovery import build
from agent.export.google_auth_helper import get_google_credentials

logger = logging.getLogger(__name__)


def export_to_google_docs(
    plan_id: str,
    plan_data: dict,
    user_context: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Export startup plan to Google Docs.
    Returns status object: {"status": "ok" | "skipped" | "failed", "reason": str | None, "url": str | None}
    """
    creds, auth_mode, instructions = get_google_credentials()
    if not creds:
        return {
            "status": "skipped",
            "reason": instructions or "Google API credentials not configured.",
            "url": None,
        }

    title = plan_data.get("startup_title", "Startup Business Plan")
    user_context = user_context or {}

    try:
        docs_service = build("docs", "v1", credentials=creds, cache_discovery=False)
        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

        # 1. Create empty document
        doc = docs_service.documents().create(body={"title": title}).execute()
        doc_id = doc.get("documentId")
        if not doc_id:
            return {
                "status": "failed",
                "reason": "Failed to retrieve documentId from Google Docs create call.",
                "url": None,
            }

        # 2. Construct text content and requests
        # We build structured content with headings and paragraphs
        sections = [
            ("TITLE", f"{title}\n\n"),
            ("HEADING_1", "1. Executive Summary\n"),
            ("NORMAL_TEXT", f"{plan_data.get('executive_summary', 'No executive summary provided.')}\n\n"),
            ("HEADING_1", "2. Problem Statement & Target Audience\n"),
            ("NORMAL_TEXT", f"Problem: {plan_data.get('problem_statement', 'N/A')}\n\nTarget Audience: {plan_data.get('target_audience', 'N/A')}\n\n"),
            ("HEADING_1", "3. Solution Strategy & Core Features\n"),
            ("NORMAL_TEXT", f"Strategy: {plan_data.get('solution', 'N/A')}\n\nFeatures:\n{plan_data.get('core_features', 'N/A')}\n\n"),
            ("HEADING_1", "4. Market Sizing & Competitor Analysis\n"),
            ("NORMAL_TEXT", f"Market Gap: {plan_data.get('market_gap', 'N/A')}\n\nCompetitors:\n{plan_data.get('competitor_analysis', 'N/A')[:1000]}\n\n"),
            ("HEADING_1", "5. Revenue Model & Financial Plan\n"),
            ("NORMAL_TEXT", f"{plan_data.get('revenue_model', 'N/A')}\n\n"),
            ("HEADING_1", "6. Implementation Roadmap\n"),
            ("NORMAL_TEXT", f"{plan_data.get('implementation_roadmap', 'N/A')}\n\n"),
        ]

        full_text = "".join(text for _, text in sections)

        requests = [
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": full_text,
                }
            }
        ]

        # Apply paragraph styles with index tracking
        current_idx = 1
        for style, text in sections:
            start_idx = current_idx
            end_idx = current_idx + len(text)
            current_idx = end_idx

            if style != "NORMAL_TEXT":
                requests.append({
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": start_idx,
                            "endIndex": end_idx,
                        },
                        "paragraphStyle": {
                            "namedStyleType": style,
                        },
                        "fields": "namedStyleType",
                    }
                })

        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests},
        ).execute()

        # 3. If service account mode and user email provided, share file
        user_email = user_context.get("email") or os.environ.get("GOOGLE_SHARE_EMAIL")
        if user_email and auth_mode == "service_account":
            try:
                drive_service.permissions().create(
                    fileId=doc_id,
                    body={"type": "user", "role": "writer", "emailAddress": user_email},
                    fields="id",
                ).execute()
            except Exception as perm_err:
                logger.warning(f"[GoogleDocs] Could not share file with {user_email}: {perm_err}")

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {
            "status": "ok",
            "reason": None,
            "url": doc_url,
        }

    except Exception as e:
        logger.error(f"[GoogleDocs] Export failed: {e}")
        return {
            "status": "failed",
            "reason": f"Google Docs API error: {e}",
            "url": None,
        }
