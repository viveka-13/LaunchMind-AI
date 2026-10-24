# agent/export/google_slides.py
# Real Google Slides export using Google Slides API v1 and Google Drive API v3

import os
import json
import logging
from typing import Optional, Dict, Any, List

from googleapiclient.discovery import build
from agent.export.google_auth_helper import get_google_credentials

logger = logging.getLogger(__name__)


def export_to_google_slides(
    plan_id: str,
    plan_data: dict,
    user_context: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Export startup pitch deck to Google Slides.
    Returns status object: {"status": "ok" | "skipped" | "failed", "reason": str | None, "url": str | None}
    """
    creds, auth_mode, instructions = get_google_credentials()
    if not creds:
        return {
            "status": "skipped",
            "reason": instructions or "Google API credentials not configured.",
            "url": None,
        }

    title = plan_data.get("startup_title", "Startup Pitch Deck")
    user_context = user_context or {}

    try:
        slides_service = build("slides", "v1", credentials=creds, cache_discovery=False)
        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)

        # 1. Create blank presentation
        pres = slides_service.presentations().create(
            body={"title": f"{title} - Pitch Deck"}
        ).execute()
        pres_id = pres.get("presentationId")
        if not pres_id:
            return {
                "status": "failed",
                "reason": "Failed to retrieve presentationId from Google Slides create call.",
                "url": None,
            }

        # 2. Build slides matching the pitch structure
        slides_to_create = [
            ("The Problem", plan_data.get("problem_statement", "Key customer pain points identified.")[:400]),
            ("The Solution", plan_data.get("solution", "Our innovative solution.")[:400]),
            ("Market Opportunity", f"Target Audience: {plan_data.get('target_audience', 'N/A')}\nMarket Gap: {plan_data.get('market_gap', 'N/A')}"[:400]),
            ("Core Features", plan_data.get("core_features", "Product capabilities and benefits.")[:400]),
            ("Business & Revenue Model", plan_data.get("revenue_model", "Pricing and monetization.")[:400]),
            ("Execution Roadmap", plan_data.get("implementation_roadmap", "12-month strategic plan.")[:400]),
        ]

        requests: List[Dict[str, Any]] = []

        for i, (slide_title, slide_body) in enumerate(slides_to_create):
            slide_id = f"slide_{i+1}"
            title_box_id = f"title_box_{i+1}"
            body_box_id = f"body_box_{i+1}"

            # Create blank slide
            requests.append({
                "createSlide": {
                    "objectId": slide_id,
                    "slideLayoutReference": {"predefinedLayout": "BLANK"},
                }
            })

            # Create Title TextBox
            requests.append({
                "createShape": {
                    "objectId": title_box_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {"width": {"magnitude": 650, "unit": "PT"}, "height": {"magnitude": 60, "unit": "PT"}},
                        "transform": {
                            "scaleX": 1, "scaleY": 1,
                            "translateX": 40, "translateY": 40,
                            "unit": "PT",
                        },
                    },
                }
            })
            requests.append({
                "insertText": {
                    "objectId": title_box_id,
                    "text": slide_title,
                }
            })

            # Create Body TextBox
            requests.append({
                "createShape": {
                    "objectId": body_box_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {"width": {"magnitude": 650, "unit": "PT"}, "height": {"magnitude": 250, "unit": "PT"}},
                        "transform": {
                            "scaleX": 1, "scaleY": 1,
                            "translateX": 40, "translateY": 120,
                            "unit": "PT",
                        },
                    },
                }
            })
            requests.append({
                "insertText": {
                    "objectId": body_box_id,
                    "text": slide_body,
                }
            })

        # Execute slide generation batch
        slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={"requests": requests},
        ).execute()

        # 3. Share with user email if service account
        user_email = user_context.get("email") or os.environ.get("GOOGLE_SHARE_EMAIL")
        if user_email and auth_mode == "service_account":
            try:
                drive_service.permissions().create(
                    fileId=pres_id,
                    body={"type": "user", "role": "writer", "emailAddress": user_email},
                    fields="id",
                ).execute()
            except Exception as perm_err:
                logger.warning(f"[GoogleSlides] Could not share file with {user_email}: {perm_err}")

        pres_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
        return {
            "status": "ok",
            "reason": None,
            "url": pres_url,
        }

    except Exception as e:
        logger.error(f"[GoogleSlides] Export failed: {e}")
        return {
            "status": "failed",
            "reason": f"Google Slides API error: {e}",
            "url": None,
        }
