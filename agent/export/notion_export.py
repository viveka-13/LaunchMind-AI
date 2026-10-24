# agent/export/notion_export.py
# Real Notion workspace export using official notion-client
# Respects 100 blocks per request limit and 2000 character block limit

import os
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def _chunk_text(text: str, max_chars: int = 1900) -> List[str]:
    """Split text into chunks under the 2000 character limit."""
    if not text:
        return [""]
    chunks = []
    while len(text) > max_chars:
        # Split on newline or space near limit
        split_idx = text.rfind("\n", 0, max_chars)
        if split_idx == -1:
            split_idx = text.rfind(" ", 0, max_chars)
        if split_idx == -1:
            split_idx = max_chars
        chunks.append(text[:split_idx].strip())
        text = text[split_idx:].strip()
    if text:
        chunks.append(text)
    return chunks


def _create_heading_block(text: str, level: int = 2) -> dict:
    block_type = f"heading_{level}"
    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": [{"type": "text", "text": {"content": text[:2000]}}],
        },
    }


def _create_paragraph_blocks(text: str) -> List[dict]:
    blocks = []
    chunks = _chunk_text(text)
    for c in chunks:
        if c:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": c}}],
                },
            })
    return blocks


def export_to_notion(
    plan_id: str,
    plan_data: dict,
    user_context: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Export startup plan to Notion.
    Returns status object: {"status": "ok" | "skipped" | "failed", "reason": str | None, "url": str | None}
    """
    api_key = os.environ.get("NOTION_API_KEY")
    parent_page_id = os.environ.get("NOTION_PARENT_PAGE_ID")

    if not api_key or not parent_page_id:
        return {
            "status": "skipped",
            "reason": (
                "Notion API credentials not configured. "
                "Set NOTION_API_KEY and NOTION_PARENT_PAGE_ID in your .env file, "
                "and ensure the parent page is shared with your Notion integration."
            ),
            "url": None,
        }

    title = plan_data.get("startup_title", "Startup Plan")

    try:
        from notion_client import Client
        from notion_client.errors import APIResponseError

        notion = Client(auth=api_key)

        # 1. Build all content blocks
        all_blocks: List[dict] = []

        all_blocks.append(_create_heading_block("1. Executive Summary", 2))
        all_blocks.extend(_create_paragraph_blocks(plan_data.get("executive_summary", "N/A")))

        all_blocks.append(_create_heading_block("2. Problem & Audience", 2))
        all_blocks.extend(_create_paragraph_blocks(f"Problem:\n{plan_data.get('problem_statement', 'N/A')}\n\nTarget Audience:\n{plan_data.get('target_audience', 'N/A')}"))

        all_blocks.append(_create_heading_block("3. Solution & Features", 2))
        all_blocks.extend(_create_paragraph_blocks(f"Solution Strategy:\n{plan_data.get('solution', 'N/A')}\n\nCore Features:\n{plan_data.get('core_features', 'N/A')}"))

        all_blocks.append(_create_heading_block("4. Market & Competitors", 2))
        all_blocks.extend(_create_paragraph_blocks(f"Market Gap:\n{plan_data.get('market_gap', 'N/A')}\n\nCompetitor Analysis:\n{plan_data.get('competitor_analysis', 'N/A')[:1000]}"))

        all_blocks.append(_create_heading_block("5. Revenue Model", 2))
        all_blocks.extend(_create_paragraph_blocks(plan_data.get("revenue_model", "N/A")))

        all_blocks.append(_create_heading_block("6. Implementation Roadmap", 2))
        all_blocks.extend(_create_paragraph_blocks(plan_data.get("implementation_roadmap", "N/A")))

        # 2. Create Page with first batch (<= 100 blocks)
        first_batch = all_blocks[:100]
        remaining_blocks = all_blocks[100:]

        parent_payload = {"page_id": parent_page_id.replace("-", "")}
        properties = {
            "title": {
                "title": [{"text": {"content": title[:2000]}}],
            }
        }

        try:
            page = notion.pages.create(
                parent=parent_payload,
                properties=properties,
                children=first_batch,
            )
        except Exception as api_err:
            err_status = getattr(api_err, "status", None)
            err_str = str(api_err)
            if err_status == 404 or "404" in err_str or "Could not find" in err_str:
                return {
                    "status": "failed",
                    "reason": (
                        "Notion parent page not found or access denied (HTTP 404). "
                        "Make sure the parent page is shared with the Notion integration."
                    ),
                    "url": None,
                }
            logger.error(f"[Notion] Export error: {api_err}")
            return {
                "status": "failed",
                "reason": f"Notion API error: {api_err}",
                "url": None,
            }

        new_page_id = page.get("id")
        page_url = page.get("url") or f"https://notion.so/{new_page_id.replace('-', '')}"

        # 3. Paginate remaining blocks in chunks of 100
        while remaining_blocks:
            chunk = remaining_blocks[:100]
            remaining_blocks = remaining_blocks[100:]
            notion.blocks.children.append(
                block_id=new_page_id,
                children=chunk,
            )

        return {
            "status": "ok",
            "reason": None,
            "url": page_url,
        }

    except Exception as e:
        logger.error(f"[Notion] Export error: {e}")
        return {
            "status": "failed",
            "reason": f"Notion API error: {e}",
            "url": None,
        }
