# agent/workflow.py
# LangGraph-powered autonomous agent workflow for AutoStartup AI

import asyncio
import json
import uuid
import os
import logging
from typing import TypedDict, List, Optional, Dict, Any
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from agent.llm_client import llm_call, LLMCallError, LLMResult, reset_circuit_breaker
from agent.sanitizer import sanitize_html
from agent.language import validate_language
from agent.models_pydantic import (
    TaskDecompositionModel,
    ResearchBriefModel,
    CompetitorSwotModel,
    MarketSizingModel,
    PricingModel,
    FinancialProjectionModel,
    CapTableModel,
    CritiqueModel,
    InvestorMatchModel,
    BrandKitModel,
    ArchitectureModel,
)
from agent.tools import (
    research_market, research_competitors, select_tool, AVAILABLE_TOOLS,
    search_crunchbase, search_google_trends, search_sentiment
)
from agent.memory import store_research, retrieve_similar, save_startup_plan
from agent.prompts import (
    DECOMPOSE_PROMPT,
    MARKET_GAP_PROMPT,
    SOLUTION_PROMPT,
    FEATURES_PROMPT,
    REVENUE_PROMPT,
    ROADMAP_PROMPT,
    PITCH_PROMPT,
    COMPILE_PROMPT,
)
from agent.prompts_research_validation import (
    RESEARCH_SYNTHESIS_PROMPT,
    MARKET_SIZING_PROMPT,
    COMPETITOR_SWOT_PROMPT,
    DEVILS_ADVOCATE_PROMPT,
)
from agent.ppt_generator import generate_pitch_deck_ppt
from agent.word_generator import generate_business_plan_word
from agent.pdf_generator import generate_business_plan_pdf
from agent.image_service import fetch_images_for_startup, generate_flowchart
from agent.roadmap_generator import generate_roadmap_html
from agent.asset_manager import generate_all_assets
from agent.financial_prompts import PRICING_MODEL_PROMPT, FINANCIAL_PROJECTION_PROMPT, CAP_TABLE_PROMPT
from agent.financial_model_generator import generate_financial_model
from agent.investor_matcher import match_investors
from agent.plan_schema import validate_node_output, PLAN_SECTION_KEYS

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Global event queue registry (per session)
# ─────────────────────────────────────────────
event_queues: dict[str, asyncio.Queue] = {}


async def emit(session_id: str, event: Optional[dict]):
    """Push an event to the SSE stream for this session."""
    if session_id and session_id in event_queues:
        await event_queues[session_id].put(event)


# ─────────────────────────────────────────────
# LangGraph Agent State
# ─────────────────────────────────────────────

class StartupState(TypedDict, total=False):
    session_id: str
    idea: str
    plan_id: str
    tasks: List[str]
    market_research: str
    competitor_analysis: str
    market_gap: str
    solution_strategy: str
    core_features: str
    revenue_model: str
    business_model: str
    implementation_roadmap: str
    pitch_deck_outline: str
    startup_title: str
    research_by_source: dict
    research_brief: str
    market_sizing: str
    competitor_swot: str
    critique: str
    problem_statement: str
    target_audience: str
    executive_summary: str
    language: str
    doc_format: str
    images: List[str]
    assets: dict
    pricing_model: str
    financial_projection: str
    cap_table: str
    matched_investors: str
    narration_status: dict
    canonical_facts: Optional[dict]
    facts_block: Optional[str]
    consistency_report: Optional[dict]
    errors: List[dict]
    completed_nodes: List[str]
    failed_nodes: List[str]
    skipped_nodes: List[str]
    run_summary: dict
    owner_id: Optional[str]


# ─────────────────────────────────────────────
# Named Token Limits across Workflow Nodes
# ─────────────────────────────────────────────

MAX_TOKENS_DECOMPOSE: int = 2500
MAX_TOKENS_RESEARCH_SYNTHESIS: int = 3000
MAX_TOKENS_COMPETITOR_SWOT: int = 3500
MAX_TOKENS_MARKET_SIZING: int = 3000
MAX_TOKENS_SOLUTION: int = 2500
MAX_TOKENS_FEATURES: int = 2500
MAX_TOKENS_PRICING: int = 3000
MAX_TOKENS_FINANCIAL_PROJECTION: int = 3500
MAX_TOKENS_CAP_TABLE: int = 2500
MAX_TOKENS_REVENUE: int = 3000
MAX_TOKENS_INVESTOR_MATCHING: int = 4096
MAX_TOKENS_ROADMAP: int = 3000
MAX_TOKENS_PITCH: int = 3500
MAX_TOKENS_EXECUTIVE_SUMMARY: int = 3000
MAX_TOKENS_CRITIQUE: int = 4096
MAX_TOKENS_STUDIO_ASSETS: int = 3500

TOTAL_STEPS: int = 22


# ─────────────────────────────────────────────
# Resilient LLM Wrappers
# ─────────────────────────────────────────────

async def llm_invoke_result(
    system_prompt: str,
    user_content: str,
    language: str = "English",
    max_tokens: int = 1500,
    node: str = "workflow_node",
    session_id: Optional[str] = None
) -> LLMResult:
    """Call the LLM via unified wrapper and return the complete LLMResult."""
    system_prompt += f"\n\nCRITICAL: Respond entirely in the {language} language. Do not mix English unless the user explicitly uses English words, technical terms, or product names."
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    def retry_cb(evt):
        if session_id:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(session_id, {"type": "retry", **evt}))
            except Exception:
                pass

    return await llm_call(
        messages,
        node=node,
        max_tokens=max_tokens,
        session_id=session_id,
        retry_callback=retry_cb,
    )


async def llm_invoke(
    system_prompt: str,
    user_content: str,
    language: str = "English",
    max_tokens: int = 1500,
    node: str = "workflow_node",
    session_id: Optional[str] = None
) -> str:
    """Call the LLM via unified wrapper and return the response text."""
    res = await llm_invoke_result(system_prompt, user_content, language, max_tokens, node, session_id)
    return res.text


def extract_json_block(text: str) -> str:
    """Extract JSON from markdown code fences or raw string."""
    clean = text.strip()
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif "```" in clean:
        clean = clean.split("```")[1].split("```")[0].strip()
    return clean.strip()


class SafeJsonParseError(Exception):
    """Raised when safe_json_parse fails after repair attempt."""
    def __init__(self, node: str, message: str):
        self.node = node
        super().__init__(f"[{node}] {message}")


async def safe_json_parse(
    prompt: str,
    language: str = "English",
    system_prompt: str = "You are an AI assistant. Always respond with valid JSON only.",
    max_tokens: int = 1500,
    model_cls: Optional[Any] = None,
    node: str = "json_node",
    session_id: Optional[str] = None,
) -> dict:
    """
    Execute an LLM call, parse JSON, and validate against Pydantic model.
    - If response was truncated due to length/token limit, retries once with higher limit and concise instructions.
    - If parsing/validation fails, attempts 1 repair call.
    - NEVER returns an empty default model — raises SafeJsonParseError on failure.
    """
    safe_system = system_prompt + "\n\nCRITICAL: Keep all JSON keys exactly as requested in English. ONLY translate the VALUES into the target language."
    
    def _validate_raw(raw):
        if model_cls:
            if isinstance(raw, list) and hasattr(model_cls, "model_fields") and "tasks" in model_cls.model_fields:
                raw = {"tasks": raw}
            validated = model_cls.model_validate(raw, from_attributes=False)
            return validated.model_dump(by_alias=False)
        return raw if isinstance(raw, dict) else {}

    res = await llm_invoke_result(safe_system, prompt, language, max_tokens, node=node, session_id=session_id)
    response_text = res.text
    finish_reason = getattr(res, "finish_reason", None)

    # 1. Truncation handling: If finished due to length/token limits, retry with higher limit & concise prompt
    if finish_reason in ("length", "max_tokens"):
        logger.warning(
            f"[Workflow] Response truncated (finish_reason='{finish_reason}') on node '{node}'. "
            f"Retrying once with higher token limit and concise instructions..."
        )
        retry_limit = min(max_tokens * 2, 8000)
        concise_prompt = (
            f"{prompt}\n\n"
            f"CRITICAL: The previous output was cut off because it exceeded the output limit. "
            f"Be concise, keep explanations brief, and output complete, valid JSON matching the exact schema."
        )
        try:
            res_retry = await llm_invoke_result(
                safe_system,
                concise_prompt,
                language,
                retry_limit,
                node=f"{node}_truncation_retry",
                session_id=session_id,
            )
            raw_dict = json.loads(extract_json_block(res_retry.text))
            return _validate_raw(raw_dict)
        except Exception as retry_err:
            logger.warning(f"[Workflow] Truncation retry did not produce valid JSON on node '{node}': {retry_err}. Falling back to standard parse/repair.")

    # 2. Standard parse & Pydantic validation with 1 repair attempt
    try:
        raw_dict = json.loads(extract_json_block(response_text))
        return _validate_raw(raw_dict)
    except Exception as e:
        logger.warning(f"[Workflow] JSON parse/validate error on node '{node}': {e}. Attempting 1 repair...")
        retry_prompt = f"{prompt}\n\nYOUR LAST RESPONSE WAS NOT VALID JSON OR FAILED VALIDATION.\nError: {str(e)}\nReturn ONLY valid JSON matching the requested schema."
        try:
            retry_res = await llm_invoke_result(safe_system, retry_prompt, language, max_tokens, node=f"{node}_repair", session_id=session_id)
            repaired_dict = json.loads(extract_json_block(retry_res.text))
            return _validate_raw(repaired_dict)
        except Exception as repair_err:
            logger.error(f"[Workflow] JSON repair also failed on node '{node}': {repair_err}. Raising error.")
            raise SafeJsonParseError(node, f"Parse+repair both failed: {repair_err}")


# ─────────────────────────────────────────────
# Node-level Boundary & Isolation Decorator
# ─────────────────────────────────────────────

def node_boundary(node_name: str, required_fields: Optional[List[str]] = None):
    """
    Wraps each LangGraph node for isolation:
    1. Checks required dependencies. If missing, cleanly skips the node.
    2. Catches LLMCallError and unexpected exceptions, records in state['errors'], emits events, and continues graph.
    """
    def decorator(fn):
        @wraps(fn)
        async def wrapped(state: StartupState) -> dict:
            sid = state.get("session_id", "")
            # Dependency check
            if required_fields:
                for req in required_fields:
                    val = state.get(req)
                    if val is None or (isinstance(val, (str, list, dict)) and len(val) == 0):
                        reason = f"skipped_missing_dependency: {req}"
                        logger.warning(f"[Graph] Node '{node_name}' skipped: {reason}")
                        await emit(sid, {
                            "type": "node_skipped",
                            "node": node_name,
                            "reason": reason,
                        })
                        skipped_list = list(state.get("skipped_nodes", []))
                        if node_name not in skipped_list:
                            skipped_list.append(node_name)
                        return {"skipped_nodes": skipped_list}

            try:
                out = await fn(state)
                # Output Contract Validation
                is_valid, validation_err = validate_node_output(node_name, out)
                if not is_valid:
                    logger.error(f"[Graph] Output validation failed for node '{node_name}': {validation_err}")
                    err_record = {
                        "node": node_name,
                        "reason": f"Output validation failed: {validation_err}",
                        "attempts": 1,
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                    errors = list(state.get("errors", []))
                    errors.append(err_record)
                    failed_list = list(state.get("failed_nodes", []))
                    if node_name not in failed_list:
                        failed_list.append(node_name)
                    await emit(sid, {
                        "type": "node_error",
                        "node": node_name,
                        "reason": validation_err,
                        "retryable": False,
                    })
                    return {"errors": errors, "failed_nodes": failed_list}

                completed_list = list(state.get("completed_nodes", []))
                if node_name not in completed_list:
                    completed_list.append(node_name)
                out["completed_nodes"] = completed_list
                return out
            except LLMCallError as err:
                logger.error(f"[Graph] LLMCallError in node '{node_name}': {err.reason}")
                err_record = {
                    "node": node_name,
                    "reason": err.reason,
                    "attempts": err.attempts,
                    "timestamp": asyncio.get_event_loop().time(),
                }
                errors = list(state.get("errors", []))
                errors.append(err_record)
                failed_list = list(state.get("failed_nodes", []))
                if node_name not in failed_list:
                    failed_list.append(node_name)
                await emit(sid, {
                    "type": "node_error",
                    "node": node_name,
                    "reason": err.reason,
                    "retryable": err.retryable,
                })
                return {"errors": errors, "failed_nodes": failed_list}
            except Exception as err:
                logger.error(f"[Graph] Unexpected exception in node '{node_name}': {err}")
                err_record = {
                    "node": node_name,
                    "reason": str(err),
                    "attempts": 1,
                    "timestamp": asyncio.get_event_loop().time(),
                }
                errors = list(state.get("errors", []))
                errors.append(err_record)
                failed_list = list(state.get("failed_nodes", []))
                if node_name not in failed_list:
                    failed_list.append(node_name)
                await emit(sid, {
                    "type": "node_error",
                    "node": node_name,
                    "reason": str(err),
                    "retryable": False,
                })
                return {"errors": errors, "failed_nodes": failed_list}
        return wrapped
    return decorator


UI_LABELS = {
    "English": {
        "Executive Summary": "Executive Summary",
        "Key Findings": "Key Findings",
        "Market Sentiment": "Market Sentiment",
        "Competitors": "Competitors",
        "SWOT Analysis": "SWOT Analysis",
        "Strengths": "Strengths",
        "Weaknesses": "Weaknesses",
        "TAM": "TAM (Total Addressable Market)",
        "SAM": "SAM (Serviceable Available Market)",
        "SOM": "SOM (Serviceable Obtainable Market)",
        "Growth Rate": "Growth Rate (CAGR)",
        "Overall Feasibility Score": "Overall Feasibility Score",
        "Final Verdict": "Final Verdict",
        "Why": "Why",
        "Key Score Breakdown": "Key Score Breakdown",
        "Opportunities": "Opportunities",
        "Threats": "Threats",
    },
    "Telugu": {
        "Executive Summary": "కార్యనిర్వాహక సారాంశం",
        "Key Findings": "ముఖ్య అన్వేషణలు",
        "Market Sentiment": "మార్కెట్ సెంటిమెంట్",
        "Competitors": "పోటీదారులు",
        "SWOT Analysis": "SWOT విశ్లేషణ",
        "Strengths": "బలాలు",
        "Weaknesses": "బలహీనతలు",
        "TAM": "TAM (మొత్తం మార్కెట్ పరిమాణం)",
        "SAM": "SAM (సేవ చేయగల మార్కెట్)",
        "SOM": "SOM (సాధించగల మార్కెట్)",
        "Growth Rate": "వృద్ది రేటు (CAGR)",
        "Overall Feasibility Score": "మొత్తం సాధ్యత స్కోర్",
        "Final Verdict": "తుది తీర్పు",
        "Why": "ఎందుకు",
        "Key Score Breakdown": "ముఖ్య స్కోర్ విశ్లేషణ",
        "Opportunities": "అవకాశాలు",
        "Threats": "ప్రమాదాలు",
    }
}

def _t(label: str, lang: str) -> str:
    return UI_LABELS.get(lang, UI_LABELS["English"]).get(label, label)


# ─────────────────────────────────────────────
# LangGraph Node Functions (21 steps)
# ─────────────────────────────────────────────

@node_boundary("decompose", required_fields=["idea"])
async def node_decompose_idea(state: StartupState) -> dict:
    """
    Node 1: Task Decomposition
    Break the startup idea into 10 specific subtasks.
    """
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 1,
        "total": TOTAL_STEPS,
        "icon": "🧠",
        "title": "Decomposing Idea into Subtasks",
        "message": f"Analyzing '{state['idea']}' and breaking it into research subtasks...",
    })

    prompt = DECOMPOSE_PROMPT.format(idea=state["idea"])
    res = await safe_json_parse(
        prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_DECOMPOSE,
        model_cls=TaskDecompositionModel,
        node="decompose",
        session_id=sid,
    )
    tasks = res.get("tasks", [])
    if not tasks:
        raise LLMCallError("decompose", "Task decomposition returned empty or invalid tasks", False, 1)

    # Filter/relabel impossible offline human fieldwork tasks
    cleaned_tasks = []
    fieldwork_triggers = ["interview", "field survey", "in-person survey", "on-ground", "door-to-door", "physical visit", "call 30", "interview 30"]
    for t in tasks:
        t_str = str(t).strip()
        t_lower = t_str.lower()
        if any(trig in t_lower for trig in fieldwork_triggers):
            if not t_str.startswith("Recommended Founder Validation Step"):
                t_sub = re.sub(r"^Task\s*\d+\s*:\s*", "", t_str, flags=re.IGNORECASE).strip()
                t_str = f"Recommended Founder Validation Step (Post-AI): {t_sub}"
        cleaned_tasks.append(t_str)
    tasks = cleaned_tasks

    await emit(sid, {
        "type": "tasks",
        "tasks": tasks,
        "message": f"Identified {len(tasks)} subtasks to execute autonomously.",
    })

    return {"tasks": tasks, "plan_id": state.get("plan_id") or str(uuid.uuid4())}


@node_boundary("research_market", required_fields=["idea"])
async def node_research_market(state: StartupState) -> dict:
    """Node 2: Market Research"""
    sid = state.get("session_id", "")
    selected_tool = select_tool("market size demand trends")

    await emit(sid, {
        "type": "step",
        "step": 2,
        "total": TOTAL_STEPS,
        "icon": "🔍",
        "title": "Researching Market",
        "message": f"Selecting tool: [{selected_tool}] → Searching market data for '{state['idea']}'...",
        "tool": selected_tool,
    })

    loop = asyncio.get_event_loop()
    market_data = await loop.run_in_executor(
        None, AVAILABLE_TOOLS[selected_tool]["function"], state["idea"]
    )

    await emit(sid, {
        "type": "data",
        "label": "Market Research",
        "preview": market_data[:300] + "..." if len(market_data) > 300 else market_data,
    })

    return {"market_research": market_data}


@node_boundary("research_competitors", required_fields=["idea"])
async def node_research_competitors(state: StartupState) -> dict:
    """Node 3: Competitor Analysis"""
    sid = state.get("session_id", "")
    selected_tool = select_tool("competitors existing companies")

    await emit(sid, {
        "type": "step",
        "step": 3,
        "total": TOTAL_STEPS,
        "icon": "⚔️",
        "title": "Analyzing Competitors",
        "message": f"Selecting tool: [{selected_tool}] → Finding competitors for '{state['idea']}'...",
        "tool": selected_tool,
    })

    loop = asyncio.get_event_loop()
    competitor_data = await loop.run_in_executor(
        None, AVAILABLE_TOOLS[selected_tool]["function"], state["idea"]
    )

    await emit(sid, {
        "type": "data",
        "label": "Competitor Analysis",
        "preview": competitor_data[:300] + "..." if len(competitor_data) > 300 else competitor_data,
    })

    return {"competitor_analysis": competitor_data}


@node_boundary("synthesize_research", required_fields=["market_research", "competitor_analysis"])
async def node_synthesize_research(state: StartupState) -> dict:
    """Node 4: Multi-Source Research Synthesizer"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 4,
        "total": TOTAL_STEPS,
        "icon": "🧠",
        "title": "Synthesizing Research",
        "message": "Aggregating data from DuckDuckGo, Crunchbase, Google Trends, and Sentiment APIs...",
    })

    loop = asyncio.get_event_loop()
    idea = state.get("idea", "")
    cb_data = await loop.run_in_executor(None, search_crunchbase, idea)
    gt_data = await loop.run_in_executor(None, search_google_trends, idea)
    sent_data = await loop.run_in_executor(None, search_sentiment, idea)

    research_sources = {
        "duckduckgo": (state.get("market_research", "") + "\n" + state.get("competitor_analysis", ""))[:1000],
        "crunchbase": cb_data,
        "google_trends": gt_data,
        "sentiment": sent_data,
    }

    prompt = RESEARCH_SYNTHESIS_PROMPT.format(
        idea=idea,
        duckduckgo=research_sources["duckduckgo"],
        crunchbase=research_sources["crunchbase"],
        google_trends=research_sources["google_trends"],
        sentiment=research_sources["sentiment"],
    )

    brief = await safe_json_parse(
        prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_RESEARCH_SYNTHESIS,
        model_cls=ResearchBriefModel,
        node="synthesize_research",
        session_id=sid,
    )
    lang = state.get("language", "English")
    
    brief_html = f"<b>{_t('Executive Summary', lang)}:</b><br/>{sanitize_html(brief.get('executive_summary', ''))}<br/><br/>"
    brief_html += f"<b>{_t('Key Findings', lang)}:</b><ul>"
    for f in brief.get('key_findings', []): brief_html += f"<li>{sanitize_html(str(f))}</li>"
    brief_html += "</ul><br/>"
    brief_html += f"<b>{_t('Market Sentiment', lang)}:</b> {sanitize_html(brief.get('market_sentiment', ''))}"

    await emit(sid, {
        "type": "section",
        "label": "Research Brief",
        "content": brief_html,
    })

    return {"research_by_source": research_sources, "research_brief": json.dumps(brief, ensure_ascii=False)}


@node_boundary("competitor_swot", required_fields=["idea"])
async def node_competitor_swot(state: StartupState) -> dict:
    """Node 5: Competitor Matrix & SWOT Analysis"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 5,
        "total": TOTAL_STEPS,
        "icon": "📊",
        "title": "Building Competitor Analysis",
        "message": "Generating Competitor Matrix and SWOT Analysis...",
    })

    prompt = COMPETITOR_SWOT_PROMPT.format(
        startup_idea=state.get("idea", ""),
        research_brief=state.get("research_brief", "{}"),
    )

    swot_data = await safe_json_parse(
        prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_COMPETITOR_SWOT,
        model_cls=CompetitorSwotModel,
        node="competitor_swot",
        session_id=sid,
    )
    lang = state.get("language", "English")

    swot_html = f"<b>{_t('Competitors', lang)}:</b><ul>"
    for c in swot_data.get('competitors', []):
        c_name = sanitize_html(str(c.get('name', '')))
        c_str = sanitize_html(str(c.get('strengths', '')))
        c_wk = sanitize_html(str(c.get('weaknesses', '')))
        swot_html += f"<li><b>{c_name}</b>: {c_str} / {c_wk}</li>"
    swot_html += f"</ul><br/><b>{_t('SWOT Analysis', lang)}:</b><ul>"
    swot_analysis = swot_data.get('swot_analysis', {})
    swot_html += f"<li><b>{_t('Strengths', lang)}:</b> {sanitize_html(', '.join(swot_analysis.get('strengths', [])))}</li>"
    swot_html += f"<li><b>{_t('Weaknesses', lang)}:</b> {sanitize_html(', '.join(swot_analysis.get('weaknesses', [])))}</li>"
    swot_html += f"<li><b>{_t('Opportunities', lang)}:</b> {sanitize_html(', '.join(swot_analysis.get('opportunities', [])))}</li>"
    swot_html += f"<li><b>{_t('Threats', lang)}:</b> {sanitize_html(', '.join(swot_analysis.get('threats', [])))}</li></ul>"

    await emit(sid, {
        "type": "section",
        "label": "Competitor SWOT",
        "content": swot_html,
    })

    return {"competitor_swot": json.dumps(swot_data, ensure_ascii=False)}


@node_boundary("store_research", required_fields=["market_research", "competitor_analysis"])
async def node_store_research(state: StartupState) -> dict:
    """Node 6: Store in ChromaDB (RAG Memory)"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 6,
        "total": TOTAL_STEPS,
        "icon": "💾",
        "title": "Storing Research in Vector Memory",
        "message": "Embedding research data into ChromaDB for RAG retrieval...",
    })

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, store_research,
        state.get("session_id", ""), state.get("idea", ""), "market", state.get("market_research", "")
    )
    await loop.run_in_executor(
        None, store_research,
        state.get("session_id", ""), state.get("idea", ""), "competitors", state.get("competitor_analysis", "")
    )

    await emit(sid, {
        "type": "memory",
        "message": "Research stored in ChromaDB. RAG retrieval enabled for downstream nodes.",
    })

    return {}


@node_boundary("calculate_market_size", required_fields=["idea"])
async def node_calculate_market_size(state: StartupState) -> dict:
    """Node 7: TAM / SAM / SOM Calculator"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 7,
        "total": TOTAL_STEPS,
        "icon": "📈",
        "title": "Calculating Market Size",
        "message": "Estimating TAM, SAM, and SOM...",
    })

    prompt = MARKET_SIZING_PROMPT.format(
        startup_idea=state.get("idea", ""),
        research_brief=state.get("research_brief", "{}"),
    )

    market_sizing = await safe_json_parse(
        prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_MARKET_SIZING,
        model_cls=MarketSizingModel,
        node="calculate_market_size",
        session_id=sid,
    )
    lang = state.get("language", "English")

    def _render_metric_html(metric_data, label: str) -> str:
        if not metric_data:
            return f"<b>{_t(label, lang)}:</b> <span style='color:#94a3b8;'>Not available (no justifiable estimate)</span><br/>"
        if isinstance(metric_data, dict):
            val = metric_data.get("value")
            basis = metric_data.get("basis", "estimate")
            assumptions = metric_data.get("assumptions", "")
            confidence = metric_data.get("confidence", "")
            reason = metric_data.get("reason_if_null", "")
        else:
            val = getattr(metric_data, "value", None)
            basis = getattr(metric_data, "basis", "estimate")
            assumptions = getattr(metric_data, "assumptions", "")
            confidence = getattr(metric_data, "confidence", "")
            reason = getattr(metric_data, "reason_if_null", "")

        if not val or str(val).lower() in ("null", "none", "n/a"):
            reason_str = f": {sanitize_html(str(reason))}" if reason else ""
            return f"<b>{_t(label, lang)}:</b> <span style='color:#ef4444;'>Not available{reason_str}</span><br/>"

        if basis == "estimate":
            badge = "<span style='display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.3); margin-left:6px;'>Estimate (not from sources)</span>"
            conf_str = f" <span style='font-size:11px; color:#94a3b8;'>[Confidence: {confidence}]</span>" if confidence else ""
            calc_str = f"<br/><small style='color:#94a3b8; margin-left:14px;'>↳ Calculation chain: {sanitize_html(str(assumptions))}</small>" if assumptions else ""
            return f"<b>{_t(label, lang)}:</b> {sanitize_html(str(val))} {badge}{conf_str}{calc_str}<br/>"
        elif basis == "sourced":
            badge = "<span style='display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); margin-left:6px;'>Sourced</span>"
            src_str = f"<br/><small style='color:#94a3b8; margin-left:14px;'>↳ Source: {sanitize_html(str(assumptions))}</small>" if assumptions else ""
            return f"<b>{_t(label, lang)}:</b> {sanitize_html(str(val))} {badge}{src_str}<br/>"
        else:
            return f"<b>{_t(label, lang)}:</b> {sanitize_html(str(val))}<br/>"

    size_html = _render_metric_html(market_sizing.get("tam"), "TAM")
    size_html += _render_metric_html(market_sizing.get("sam"), "SAM")
    size_html += _render_metric_html(market_sizing.get("som"), "SOM")
    if market_sizing.get("cagr"):
        size_html += f"<b>{_t('CAGR', lang)}:</b> {sanitize_html(str(market_sizing.get('cagr')))}<br/>"

    await emit(sid, {
        "type": "section",
        "label": "Market Sizing",
        "content": size_html,
    })

    return {"market_sizing": json.dumps(market_sizing, ensure_ascii=False)}


@node_boundary("analyze_gaps", required_fields=["market_research"])
async def node_analyze_gaps(state: StartupState) -> dict:
    """Node 8: Identify Market Gaps"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 8,
        "total": TOTAL_STEPS,
        "icon": "🎯",
        "title": "Identifying Market Gaps",
        "message": "Retrieving context from ChromaDB → Analyzing gaps with LLM...",
    })

    loop = asyncio.get_event_loop()
    rag_context = await loop.run_in_executor(
        None, retrieve_similar,
        f"market gap opportunity {state.get('idea', '')}", state.get("session_id", "")
    )

    full_market = state.get("market_research", "")
    research_brief = state.get("research_brief", "")
    if rag_context:
        full_market = f"[RAG Retrieved Context]\n{rag_context}\n\n[Research Brief]\n{research_brief}\n\n[Full Research]\n{full_market}"

    gap_prompt = MARKET_GAP_PROMPT.format(
        idea=state.get("idea", ""),
        market_research=full_market[:800],
        competitor_analysis=state.get("competitor_swot", state.get("competitor_analysis", ""))[:600],
        market_sizing=state.get("market_sizing", "Not available yet")[:600],
    )

    market_gap = await llm_invoke(
        "You are a strategic market analyst. Be specific and insightful.",
        gap_prompt,
        state.get("language", "English"),
        node="analyze_gaps",
        session_id=sid,
    )

    await emit(sid, {
        "type": "section",
        "label": "Market Gap Analysis",
        "content": sanitize_html(market_gap),
    })

    return {"market_gap": market_gap}


@node_boundary("generate_solution", required_fields=["idea"])
async def node_generate_solution(state: StartupState) -> dict:
    """Node 9: Generate Solution Strategy"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 9,
        "total": TOTAL_STEPS,
        "icon": "💡",
        "title": "Generating Solution Strategy",
        "message": "Designing solution based on market gap analysis...",
    })

    solution_prompt = SOLUTION_PROMPT.format(
        idea=state.get("idea", ""),
        market_gap=state.get("market_gap", "Unaddressed customer workflow bottlenecks")[:500],
        competitor_analysis=state.get("competitor_swot", state.get("competitor_analysis", ""))[:600] or state.get("idea", ""),
    )

    solution = await llm_invoke(
        "You are a visionary product strategist. Be compelling and specific.",
        solution_prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_SOLUTION,
        node="generate_solution",
        session_id=sid,
    )

    await emit(sid, {
        "type": "section",
        "label": "Solution Strategy",
        "content": sanitize_html(solution),
    })

    # Generate startup title early so it is never missing or "Your Startup"
    startup_title = state.get("startup_title")
    if not startup_title or startup_title.lower() in ("startup", "your startup", ""):
        words = [w for w in state.get("idea", "Startup").split() if len(w) > 2]
        startup_title = " ".join(words[:3]).title() if words else "Startup"

    return {"solution_strategy": solution, "startup_title": startup_title}


@node_boundary("generate_features", required_fields=["idea"])
async def node_generate_features(state: StartupState) -> dict:
    """Node 10: Generate Core Product Features"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 10,
        "total": TOTAL_STEPS,
        "icon": "⚡",
        "title": "Designing Core Features",
        "message": "Generating product features based on solution strategy...",
    })

    solution_context = state.get("solution_strategy") or state.get("idea", "")
    features_prompt = FEATURES_PROMPT.format(
        idea=state.get("idea", ""),
        solution=solution_context[:600] + "\nCompetitors: " + state.get("competitor_swot", "")[:300],
    )

    features = await llm_invoke(
        "You are a technical product manager. Be concise and structured.",
        features_prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_FEATURES,
        node="generate_features",
        session_id=sid,
    )

    await emit(sid, {
        "type": "section",
        "label": "Core Features",
        "content": sanitize_html(features),
    })

    return {"core_features": features}


@node_boundary("pricing_model", required_fields=["idea"])
async def node_pricing_model(state: StartupState) -> dict:
    """Node 11: Generate Pricing Model (JSON)"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 11,
        "total": TOTAL_STEPS,
        "icon": "💲",
        "title": "Simulating Pricing Model",
        "message": "Generating pricing tiers and MRR projections...",
    })

    prompt = PRICING_MODEL_PROMPT.format(
        idea=state.get("idea", ""),
        revenue_model=state.get("solution_strategy", "")[:500],
        market_sizing=state.get("market_sizing", "")[:300],
        competitor_analysis=state.get("competitor_analysis", "")[:300],
    )

    pricing_data = await safe_json_parse(
        prompt,
        language="English",
        max_tokens=MAX_TOKENS_PRICING,
        model_cls=PricingModel,
        node="pricing_model",
        session_id=sid,
    )
    
    # Build rich HTML with features
    tier_html = "<div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-top:8px;'>"
    for t in pricing_data.get("tiers", []):
        t_name = sanitize_html(str(t.get("name", "")))
        t_price = sanitize_html(str(t.get("monthly_price", 0)))
        t_seg = sanitize_html(str(t.get("target_segment", "")))
        t_feats = t.get("features", [])
        feats_list = "".join([f"<li style='margin-bottom:3px;'>{sanitize_html(str(f))}</li>" for f in t_feats])
        tier_html += f"""
        <div style='background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.1); border-radius:8px; padding:12px;'>
            <div style='font-weight:700; font-size:1.05rem; color:#818cf8;'>{t_name}</div>
            <div style='font-size:1.3rem; font-weight:800; margin:6px 0; color:#34d399;'>${t_price}<span style='font-size:0.75rem; color:#94a3b8; font-weight:400;'>/mo</span></div>
            <div style='font-size:0.8rem; color:#94a3b8; margin-bottom:8px;'>Target: {t_seg}</div>
            <div style='font-size:0.8rem; font-weight:600; color:#e2e8f0; margin-bottom:4px;'>Features:</div>
            <ul style='font-size:0.82rem; color:#cbd5e1; padding-left:16px; margin:0;'>{feats_list}</ul>
        </div>"""
    tier_html += "</div>"
    
    await emit(sid, {
        "type": "section",
        "label": "Pricing Scenarios",
        "content": tier_html,
    })

    return {"pricing_model": json.dumps(pricing_data)}


@node_boundary("financial_projection", required_fields=["idea"])
async def node_financial_projection(state: StartupState) -> dict:
    """Node 12: Generate 3-Year P&L Projection (JSON)"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 12,
        "total": TOTAL_STEPS,
        "icon": "📊",
        "title": "Building Financial Projections",
        "message": "Calculating 3-year P&L, burn rate, and hiring costs...",
    })

    pricing_ctx = state.get("pricing_model") or state.get("idea", "")
    features_ctx = state.get("core_features") or state.get("idea", "")
    prompt = FINANCIAL_PROJECTION_PROMPT.format(
        idea=state.get("idea", ""),
        revenue_model=pricing_ctx[:500],
        core_features=features_ctx[:400],
        market_sizing=state.get("market_sizing", "")[:300],
    )

    proj_data = await safe_json_parse(
        prompt,
        language="English",
        max_tokens=MAX_TOKENS_FINANCIAL_PROJECTION,
        model_cls=FinancialProjectionModel,
        node="financial_projection",
        session_id=sid,
    )
    
    await emit(sid, {
        "type": "section",
        "label": "Financial Projections",
        "content": f"<pre>{json.dumps(proj_data, indent=2)}</pre>",
    })

    return {"financial_projection": json.dumps(proj_data)}


@node_boundary("cap_table", required_fields=["idea"])
async def node_cap_table(state: StartupState) -> dict:
    """Node 13: Generate Cap Table & Funding Ask (JSON)"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 13,
        "total": TOTAL_STEPS,
        "icon": "🏦",
        "title": "Structuring Cap Table",
        "message": "Generating funding ask, equity split, and use of funds...",
    })
    
    try:
        proj_data = json.loads(state.get("financial_projection", "{}"))
        initial_cash = proj_data.get("initial_cash", 100000)
        burn = sum(proj_data.get("operating_expenses", {}).values())
    except Exception:
        initial_cash = 100000
        burn = 10000

    pricing_ctx = state.get("pricing_model") or state.get("idea", "")
    prompt = CAP_TABLE_PROMPT.format(
        idea=state.get("idea", ""),
        revenue_model=pricing_ctx[:500],
        market_sizing=state.get("market_sizing", "")[:300],
        initial_cash=initial_cash,
        monthly_burn=burn,
    )

    cap_data = await safe_json_parse(
        prompt,
        language="English",
        max_tokens=MAX_TOKENS_CAP_TABLE,
        model_cls=CapTableModel,
        node="cap_table",
        session_id=sid,
    )
    
    await emit(sid, {
        "type": "section",
        "label": "Cap Table & Funding",
        "content": f"<pre>{json.dumps(cap_data, indent=2)}</pre>",
    })

    return {"cap_table": json.dumps(cap_data)}


@node_boundary("build_canonical_facts", required_fields=["idea"])
async def node_build_canonical_facts(state: StartupState) -> dict:
    """Node 14: Construct Canonical Project Facts (Single Source of Truth)"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 14,
        "total": TOTAL_STEPS,
        "icon": "📐",
        "title": "Establishing Canonical Project Facts",
        "message": "Computing deterministic unit economics, milestone revenues, and break-even...",
    })

    from agent.canonical_facts import build_canonical_facts
    canonical_res = build_canonical_facts(state)

    return {
        "canonical_facts": canonical_res,
        "facts_block": canonical_res["facts_block"],
    }


@node_boundary("generate_revenue", required_fields=["idea"])
async def node_generate_revenue(state: StartupState) -> dict:
    """Node 15: Generate Revenue Model Narrative using Canonical Facts"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 15,
        "total": TOTAL_STEPS,
        "icon": "💰",
        "title": "Modeling Revenue Streams",
        "message": "Creating revenue narrative grounded in canonical pricing and unit economics...",
    })

    facts_block = state.get("facts_block") or ""
    if not facts_block:
        from agent.canonical_facts import build_canonical_facts
        facts_block = build_canonical_facts(state)["facts_block"]

    revenue_prompt = REVENUE_PROMPT.format(
        idea=state.get("idea", ""),
        solution=state.get("solution_strategy", "")[:500],
        market_research=state.get("market_research", "")[:500] + "\nSizing: " + state.get("market_sizing", "")[:300],
        canonical_facts=facts_block,
    )

    revenue = await llm_invoke(
        "You are a startup financial strategist. Cite the canonical pricing tiers and arithmetic verbatim.",
        revenue_prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_REVENUE,
        node="generate_revenue",
        session_id=sid,
    )

    await emit(sid, {
        "type": "section",
        "label": "Revenue Model",
        "content": sanitize_html(revenue),
    })

    return {"revenue_model": revenue, "business_model": revenue}


@node_boundary("investor_matching", required_fields=["idea"])
async def node_investor_matching(state: StartupState) -> dict:
    """Node 16: AI Investor Matching Engine"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 16,
        "total": TOTAL_STEPS,
        "icon": "🤝",
        "title": "Matching Investors",
        "message": "Finding VC and Angel investors suitable for your startup...",
    })

    try:
        cap_data = json.loads(state.get("cap_table", "{}"))
        initial_cash = cap_data.get("funding_amount", cap_data.get("funding_ask", {}).get("total_ask", "$500,000"))
    except Exception:
        initial_cash = "$500,000"

    revenue_ctx = state.get("revenue_model") or state.get("idea", "")
    features_ctx = state.get("core_features") or state.get("idea", "")
    matched = await match_investors(
        idea=state.get("idea", ""),
        revenue_model=revenue_ctx,
        core_features=features_ctx,
        initial_cash=str(initial_cash),
        language=state.get("language", "English"),
        session_id=sid,
    )
    
    return {"matched_investors": json.dumps(matched)}


@node_boundary("generate_roadmap", required_fields=["idea"])
async def node_generate_roadmap(state: StartupState) -> dict:
    """Node 17: Generate Implementation Roadmap"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 17,
        "total": TOTAL_STEPS,
        "icon": "🗺️",
        "title": "Building Implementation Roadmap",
        "message": "Planning 12-month execution roadmap...",
    })

    facts_block = state.get("facts_block") or ""
    if not facts_block:
        from agent.canonical_facts import build_canonical_facts
        facts_block = build_canonical_facts(state)["facts_block"]

    from datetime import datetime
    now = datetime.now()
    current_date = now.strftime("%B %Y")
    current_year = now.year

    features_ctx = state.get("core_features") or state.get("idea", "")
    revenue_ctx = state.get("revenue_model") or state.get("idea", "")
    roadmap_prompt = ROADMAP_PROMPT.format(
        idea=state.get("idea", ""),
        features=features_ctx[:400],
        revenue=revenue_ctx[:400],
        canonical_facts=facts_block,
        current_date=current_date,
        current_year=current_year,
    )

    roadmap = await llm_invoke(
        "You are a startup CTO. Create realistic, achievable milestones scheduled from {current_year} onwards.",
        roadmap_prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_ROADMAP,
        node="generate_roadmap",
        session_id=sid,
    )

    await emit(sid, {
        "type": "section",
        "label": "Implementation Roadmap",
        "content": sanitize_html(roadmap),
    })

    return {"implementation_roadmap": roadmap}


@node_boundary("generate_pitch", required_fields=["idea"])
async def node_generate_pitch(state: StartupState) -> dict:
    """Node 18: Generate Pitch Deck Outline"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 18,
        "total": TOTAL_STEPS,
        "icon": "🎤",
        "title": "Creating Pitch Deck Outline",
        "message": "Structuring investor pitch deck...",
    })

    facts_block = state.get("facts_block") or ""
    facts = state.get("canonical_facts", {}).get("facts", {})
    if not facts_block:
        from agent.canonical_facts import build_canonical_facts
        canon = build_canonical_facts(state)
        facts_block = canon["facts_block"]
        facts = canon["facts"]

    from datetime import datetime
    current_year = facts.get("current_year", datetime.now().year)
    funding_ask_str = f"${facts.get('funding_ask', 150000):,.0f}"

    solution_ctx = state.get("solution_strategy") or state.get("idea", "")
    revenue_ctx = state.get("revenue_model") or state.get("idea", "")
    pitch_prompt = PITCH_PROMPT.format(
        idea=state.get("idea", ""),
        solution=solution_ctx[:400],
        revenue=revenue_ctx[:400],
        market_research=state.get("market_research", "")[:500],
        canonical_facts=facts_block,
        funding_ask=funding_ask_str,
        current_year=current_year,
    )

    pitch = await llm_invoke(
        "You are a top startup pitch coach. Create a compelling narrative strictly grounded in canonical facts.",
        pitch_prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_PITCH,
        node="generate_pitch",
        session_id=sid,
    )

    await emit(sid, {
        "type": "section",
        "label": "Pitch Deck Outline",
        "content": sanitize_html(pitch),
    })

    return {"pitch_deck_outline": pitch}


@node_boundary("compile_plan", required_fields=["idea"])
async def node_compile_plan(state: StartupState) -> dict:
    """Node 19: Compile Final Plan"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 19,
        "total": TOTAL_STEPS,
        "icon": "📋",
        "title": "Compiling Executive Summary",
        "message": "Synthesizing all research into final startup report...",
    })

    facts_block = state.get("facts_block") or ""
    facts = state.get("canonical_facts", {}).get("facts", {})
    if not facts_block:
        from agent.canonical_facts import build_canonical_facts
        canon = build_canonical_facts(state)
        facts_block = canon["facts_block"]
        facts = canon["facts"]

    funding_ask_str = f"${facts.get('funding_ask', 150000):,.0f}"

    all_context = f"""
Market Research: {state.get('market_research', '')[:400]}
Competitor Analysis: {state.get('competitor_analysis', '')[:400]}
Market Gap: {state.get('market_gap', '')[:300]}
Solution: {state.get('solution_strategy', '')[:300]}
Features: {state.get('core_features', '')[:300]}
Revenue: {state.get('revenue_model', '')[:300]}
Roadmap: {state.get('implementation_roadmap', '')[:300]}
"""

    compile_prompt = COMPILE_PROMPT.format(
        idea=state.get("idea", ""),
        all_context=all_context,
        canonical_facts=facts_block,
        funding_ask=funding_ask_str,
    )

    compiled = await llm_invoke(
        "You are a senior business analyst. Be compelling and precise.",
        compile_prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_EXECUTIVE_SUMMARY,
        node="compile_plan",
        session_id=sid,
    )

    # Use existing startup_title from state (generated in step 9) or idea
    startup_title = state.get("startup_title") or state.get("idea", "Smart Venture").title()
    problem_statement = ""
    target_audience = ""
    executive_summary = ""

    lines = compiled.split("\n")
    current_key = None
    buffer = []

    def flush(key, buf):
        text = " ".join(buf).strip()
        nonlocal startup_title, problem_statement, target_audience, executive_summary
        if key == "STARTUP_TITLE" and text and text.lower() not in ("your startup", "startup", "untitled startup"):
            startup_title = text
        elif key == "PROBLEM_STATEMENT":
            problem_statement = text
        elif key == "TARGET_AUDIENCE":
            target_audience = text
        elif key == "EXECUTIVE_SUMMARY":
            executive_summary = text

    for line in lines:
        line = line.strip()
        if line.startswith("STARTUP_TITLE:"):
            if current_key:
                flush(current_key, buffer)
            current_key = "STARTUP_TITLE"
            buffer = [line.replace("STARTUP_TITLE:", "").strip()]
        elif line.startswith("PROBLEM_STATEMENT:"):
            if current_key:
                flush(current_key, buffer)
            current_key = "PROBLEM_STATEMENT"
            buffer = [line.replace("PROBLEM_STATEMENT:", "").strip()]
        elif line.startswith("TARGET_AUDIENCE:"):
            if current_key:
                flush(current_key, buffer)
            current_key = "TARGET_AUDIENCE"
            buffer = [line.replace("TARGET_AUDIENCE:", "").strip()]
        elif line.startswith("EXECUTIVE_SUMMARY:"):
            if current_key:
                flush(current_key, buffer)
            current_key = "EXECUTIVE_SUMMARY"
            buffer = [line.replace("EXECUTIVE_SUMMARY:", "").strip()]
        elif line and current_key:
            buffer.append(line)

    if current_key:
        flush(current_key, buffer)

    if not startup_title or startup_title.lower() in ("your startup", "startup", "untitled startup"):
        startup_title = state.get("startup_title") or f"{state.get('idea', 'Smart Venture').title()}"

    if not problem_statement:
        problem_statement = f"The {state.get('idea', '')} sector lacks modern, AI-powered solutions that address user needs effectively."
    if not target_audience:
        target_audience = f"Primary users of {state.get('idea', '')} solutions seeking improved efficiency and outcomes."
    if not executive_summary:
        executive_summary = f"Our startup addresses the growing demand in the {state.get('idea', '')} space by providing an innovative AI-powered platform that solves key market gaps identified through extensive research."

    return {
        "startup_title": startup_title,
        "problem_statement": problem_statement,
        "target_audience": target_audience,
        "executive_summary": executive_summary,
    }


@node_boundary("adversarial_review", required_fields=["idea"])
async def node_adversarial_review(state: StartupState) -> dict:
    """Node 20: Devil's Advocate / Adversarial Review"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 20,
        "total": TOTAL_STEPS,
        "icon": "⚖️",
        "title": "Running Investor Review",
        "message": "Performing adversarial review to find critical flaws...",
    })

    title = state.get('startup_title') or state.get('idea', 'Startup').title()
    compiled_plan = f"Title: {title}\nSummary: {state.get('executive_summary', '')}\nProblem: {state.get('problem_statement', '')}\nSolution: {state.get('solution_strategy', '')}\nRevenue: {state.get('revenue_model', '')}"

    prompt = DEVILS_ADVOCATE_PROMPT.format(
        startup_idea=state.get('idea', '')[:500],
        compiled_plan=compiled_plan[:1500],
    )

    critique = await safe_json_parse(
        prompt,
        state.get("language", "English"),
        max_tokens=MAX_TOKENS_CRITIQUE,
        model_cls=CritiqueModel,
        node="adversarial_review",
        session_id=sid,
    )

    scores = critique.get('scores', {})
    final = critique.get('final_verdict', {})
    action_plan = critique.get('action_plan', {})
    lang = state.get("language", "English")

    crit_html = f"<b>{_t('Overall Feasibility Score', lang)}:</b> {scores.get('overall_feasibility_score', 'N/A')}/100<br/>"
    crit_html += f"<b>{_t('Final Verdict', lang)}:</b> {sanitize_html(str(final.get('verdict', 'N/A')))}<br/><br/>"
    crit_html += f"<b>{_t('Why', lang)}:</b> {sanitize_html(str(final.get('why', '')))}<br/><br/>"
    crit_html += f"<b>{_t('Key Score Breakdown', lang)}:</b><ul>"
    crit_html += f"<li>Problem Validation: {scores.get('problem_validation', 'N/A')}/10</li>"
    crit_html += f"<li>Market Opportunity: {scores.get('market_opportunity', 'N/A')}/10</li>"
    crit_html += f"<li>Revenue Model: {scores.get('revenue_model', 'N/A')}/10</li>"
    crit_html += f"<li>Risk Score (Higher is better/safer): {scores.get('risk_score', 'N/A')}/10</li>"
    crit_html += "</ul><br/>"

    crit_html += "<b>Priority 1 Actions (Critical):</b><ul>"
    for a in action_plan.get('priority_1', []):
        p_text = sanitize_html(str(a.get('problem', '')))
        s_text = sanitize_html(str(a.get('solution', '')))
        i_text = sanitize_html(str(a.get('expected_impact', '')))
        crit_html += f"<li><b>{p_text}</b>: {s_text} (Impact: {i_text})</li>"
    crit_html += "</ul>"

    await emit(sid, {
        "type": "section",
        "label": "Investor Review",
        "content": crit_html,
    })

    return {"critique": json.dumps(critique, ensure_ascii=False)}


@node_boundary("validate_consistency", required_fields=["idea"])
async def node_validate_consistency(state: StartupState) -> dict:
    """Node 21: Cross-Section Consistency Validation & Auto-Repair"""
    sid = state.get("session_id", "")
    await emit(sid, {
        "type": "step",
        "step": 21,
        "total": TOTAL_STEPS,
        "icon": "⚖️",
        "title": "Validating Cross-Section Consistency",
        "message": "Auditing pricing, funding asks, milestone dates, and revenue math...",
    })

    from agent.canonical_facts import build_canonical_facts
    canonical_res = state.get("canonical_facts")
    if not canonical_res:
        canonical_res = build_canonical_facts(state)

    from agent.consistency_validator import validate_plan_consistency, auto_repair_inconsistencies
    is_valid, issues = validate_plan_consistency(state, canonical_res)

    updates = {}
    if not is_valid:
        logger.warning(f"[Consistency] Inconsistencies detected: {issues}. Performing auto-repair...")
        repaired = await auto_repair_inconsistencies(state, canonical_res, issues)
        if repaired:
            updates.update(repaired)
            new_state = {**state, **repaired}
            is_valid, issues = validate_plan_consistency(new_state, canonical_res)

    report = {
        "passed": is_valid,
        "issue_count": len(issues),
        "issues": issues,
    }

    await emit(sid, {
        "type": "consistency_report",
        "report": report,
    })

    return {**updates, "consistency_report": report}


@node_boundary("save_plan", required_fields=["plan_id"])
async def node_save_plan(state: StartupState) -> dict:
    """Node 22: Save to SQLite Memory & Generate Documents"""
    sid = state.get("session_id", "")
    doc_format = state.get("doc_format", "ppt")

    await emit(sid, {
        "type": "step",
        "step": 22,
        "total": TOTAL_STEPS,
        "icon": "[OK]",
        "title": f"Saving Plan & Generating {doc_format.upper()} Document",
        "message": "Storing complete plan in SQLite. Generating your professional document...",
    })

    plan_data = {
        "startup_title": state.get("startup_title", state.get("idea", "Startup").title()),
        "problem_statement": state.get("problem_statement", ""),
        "target_audience": state.get("target_audience", ""),
        "market_research": state.get("market_research", ""),
        "competitor_analysis": state.get("competitor_analysis", ""),
        "market_gap": state.get("market_gap", ""),
        "solution": state.get("solution_strategy", ""),
        "core_features": state.get("core_features", ""),
        "revenue_model": state.get("revenue_model", ""),
        "business_model": state.get("business_model", ""),
        "implementation_roadmap": state.get("implementation_roadmap", ""),
        "pitch_deck_outline": state.get("pitch_deck_outline", ""),
        "executive_summary": state.get("executive_summary", ""),
        "tasks": state.get("tasks", []),
        "doc_format": doc_format,
        "market_sizing": state.get("market_sizing", "{}"),
        "competitor_swot": state.get("competitor_swot", "{}"),
        "critique": state.get("critique", "{}"),
        "pricing_model": state.get("pricing_model", "{}"),
        "financial_projection": state.get("financial_projection", "{}"),
        "cap_table": state.get("cap_table", "{}"),
        "matched_investors": state.get("matched_investors", "{}"),
    }

    loop = asyncio.get_event_loop()

    # Compute run summary
    completed = state.get("completed_nodes", [])
    failed = state.get("failed_nodes", [])
    skipped = state.get("skipped_nodes", [])
    errors = state.get("errors", [])
    run_status = "completed" if not errors and not failed else ("failed" if len(completed) == 0 else "completed_with_errors")
    run_summary = {
        "status": run_status,
        "completed_count": len(completed),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "completed_nodes": completed,
        "failed_nodes": failed,
        "skipped_nodes": skipped,
        "errors": errors,
    }

    # Persist plan to SQLite with run_summary
    await loop.run_in_executor(
        None,
        save_startup_plan,
        state["plan_id"],
        state.get("idea", ""),
        plan_data["startup_title"],
        plan_data,
        run_summary,
        state.get("owner_id"),
    )

    # ── Phase 4: Fetch images from Pexels (non-blocking) ──
    images = []
    flowchart_path = None
    try:
        images = await loop.run_in_executor(
            None, fetch_images_for_startup, state.get("idea", ""), 3
        )
        flowchart_path = await loop.run_in_executor(
            None, generate_flowchart, state["plan_id"]
        )
    except Exception as e:
        logger.warning(f"[Workflow] Image/flowchart fetch failed (non-fatal): {e}")

    os.makedirs("./data/documents", exist_ok=True)
    os.makedirs("./data/presentations", exist_ok=True)

    # ── Phase 5: Generate All Document Formats (Word, PDF, PPT) ──
    doc_path_word = f"./data/documents/{state['plan_id']}.docx"
    doc_path_pdf = f"./data/documents/{state['plan_id']}.pdf"
    ppt_path = f"./data/presentations/{state['plan_id']}.pptx"
    
    await asyncio.gather(
        loop.run_in_executor(None, generate_business_plan_word, plan_data, doc_path_word, images, flowchart_path),
        loop.run_in_executor(None, generate_business_plan_pdf, plan_data, doc_path_pdf, images, flowchart_path),
        loop.run_in_executor(None, generate_pitch_deck_ppt, plan_data, ppt_path, images, flowchart_path)
    )

    # ── Phase 6: Generate Business Roadmap HTML ──
    os.makedirs("./data/roadmaps", exist_ok=True)
    roadmap_path = f"./data/roadmaps/{state['plan_id']}.html"
    try:
        await loop.run_in_executor(
            None, generate_roadmap_html, plan_data, roadmap_path
        )
    except Exception as e:
        logger.warning(f"[Workflow] Roadmap HTML generation failed (non-fatal): {e}")

    # ── Phase 7: Generate Financial Model Excel ──
    try:
        pricing = json.loads(state.get("pricing_model", "{}"))
        proj = json.loads(state.get("financial_projection", "{}"))
        cap = json.loads(state.get("cap_table", "{}"))
        await loop.run_in_executor(
            None, generate_financial_model, state["plan_id"], pricing, proj, cap
        )
    except Exception as e:
        logger.warning(f"[Workflow] Financial Model Excel generation failed: {e}")

    # ── Phase 8: Generate Voice Narration (Resilient, Non-crashing) ──
    narration_status = {}
    try:
        from agent.voice_generator import generate_voice_narration
        narration_status = await loop.run_in_executor(
            None, generate_voice_narration, state["plan_id"], plan_data, state.get("language")
        )
        if narration_status.get("status") == "ok":
            await emit(sid, {
                "type": "narration_ready",
                "status": "ok",
                "audio_url": f"/api/pitch/audio/{state['plan_id']}",
                "duration_seconds": narration_status.get("duration_seconds"),
                "script": narration_status.get("script"),
            })
        elif narration_status.get("status") == "skipped":
            await emit(sid, {
                "type": "narration_skip",
                "status": "skipped",
                "reason": narration_status.get("reason"),
            })
        else:
            await emit(sid, {
                "type": "narration_error",
                "status": "failed",
                "reason": narration_status.get("reason"),
            })
    except Exception as e:
        logger.warning(f"[Workflow] Voice narration generation failed (non-fatal): {e}")
        narration_status = {
            "status": "failed",
            "reason": str(e),
            "path": None,
            "duration_seconds": None,
            "provider": "unknown",
            "voice": "unknown",
        }
        await emit(sid, {
            "type": "narration_error",
            "status": "failed",
            "reason": str(e),
        })

    plan_data["narration_status"] = narration_status

    # Emit run summary
    await emit(sid, {
        "type": "run_summary",
        "summary": run_summary,
    })

    # Emit the complete final plan (include doc_format so frontend shows right button)
    await emit(sid, {
        "type": "complete",
        "plan_id": state["plan_id"],
        "plan": plan_data,
        "status": run_status,
    })

    return {
        "plan_id": state["plan_id"],
        "images": images,
        "narration_status": narration_status,
        "run_summary": run_summary,
    }


@node_boundary("generate_assets", required_fields=["plan_id"])
async def node_generate_assets(state: StartupState) -> dict:
    """Node 21: AI Startup Studio - Asset Generation Pipeline"""
    sid = state.get("session_id", "")
    
    await emit(sid, {
        "type": "step",
        "step": 21,
        "total": 21,
        "icon": "[OK]",
        "title": "Generating Startup Studio Assets",
        "message": "Creating Logo, Brand Kit, Marketing Poster, Landing Page, Wireframes, and Investor Report...",
    })

    async def emit_progress(msg: str):
        await emit(sid, {
            "type": "asset_progress",
            "status": sanitize_html(msg),
        })

    assets = {}
    try:
        assets = await generate_all_assets(state, emit_progress)
    except Exception as e:
        logger.error(f"[Workflow] Error during asset generation: {e}")
        assets = state.get("assets", {})

    await emit(sid, {
        "type": "dashboard",
        "assets": assets,
    })

    # Signal end of stream
    await emit(sid, None)

    return {"assets": assets}


# ─────────────────────────────────────────────
# Build the LangGraph Workflow
# ─────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the LangGraph state machine with 22 ordered, isolated nodes."""
    workflow = StateGraph(StartupState)

    # 1. Register all nodes
    workflow.add_node("decompose", node_decompose_idea)
    workflow.add_node("research_market", node_research_market)
    workflow.add_node("research_competitors", node_research_competitors)
    workflow.add_node("synthesize_research", node_synthesize_research)
    workflow.add_node("competitor_swot", node_competitor_swot)
    workflow.add_node("store_research", node_store_research)
    workflow.add_node("calculate_market_size", node_calculate_market_size)
    workflow.add_node("analyze_gaps", node_analyze_gaps)
    workflow.add_node("generate_solution", node_generate_solution)
    workflow.add_node("generate_features", node_generate_features)
    workflow.add_node("pricing_model", node_pricing_model)
    workflow.add_node("financial_projection", node_financial_projection)
    workflow.add_node("cap_table", node_cap_table)
    workflow.add_node("build_canonical_facts", node_build_canonical_facts)
    workflow.add_node("generate_revenue", node_generate_revenue)
    workflow.add_node("investor_matching", node_investor_matching)
    workflow.add_node("generate_roadmap", node_generate_roadmap)
    workflow.add_node("generate_pitch", node_generate_pitch)
    workflow.add_node("compile_plan", node_compile_plan)
    workflow.add_node("adversarial_review", node_adversarial_review)
    workflow.add_node("validate_consistency", node_validate_consistency)
    workflow.add_node("save_plan", node_save_plan)
    workflow.add_node("generate_assets", node_generate_assets)

    # 2. Sequential edges: numeric first -> canonical facts -> narratives -> validation -> save -> studio
    workflow.set_entry_point("decompose")
    workflow.add_edge("decompose", "research_market")
    workflow.add_edge("research_market", "research_competitors")
    workflow.add_edge("research_competitors", "synthesize_research")
    workflow.add_edge("synthesize_research", "competitor_swot")
    workflow.add_edge("competitor_swot", "store_research")
    workflow.add_edge("store_research", "calculate_market_size")
    workflow.add_edge("calculate_market_size", "analyze_gaps")
    workflow.add_edge("analyze_gaps", "generate_solution")
    workflow.add_edge("generate_solution", "generate_features")
    workflow.add_edge("generate_features", "pricing_model")
    workflow.add_edge("pricing_model", "financial_projection")
    workflow.add_edge("financial_projection", "cap_table")
    workflow.add_edge("cap_table", "build_canonical_facts")
    workflow.add_edge("build_canonical_facts", "generate_revenue")
    workflow.add_edge("generate_revenue", "investor_matching")
    workflow.add_edge("investor_matching", "generate_roadmap")
    workflow.add_edge("generate_roadmap", "generate_pitch")
    workflow.add_edge("generate_pitch", "compile_plan")
    workflow.add_edge("compile_plan", "adversarial_review")
    workflow.add_edge("adversarial_review", "validate_consistency")
    workflow.add_edge("validate_consistency", "save_plan")
    workflow.add_edge("save_plan", "generate_assets")
    workflow.add_edge("generate_assets", END)

    return workflow.compile()


# Compile graph at module load
agent_graph = build_graph()


# ─────────────────────────────────────────────
# Main entry point for running the agent
# ─────────────────────────────────────────────

async def run_agent(
    idea: str,
    session_id: str,
    language: str = "en",
    doc_format: str = "ppt",
    owner_id: Optional[str] = None
):
    """
    Run the full 21-step autonomous agent workflow.
    Events are streamed via the global event_queues dict.
    """
    initial_state: StartupState = {
        "session_id": session_id,
        "idea": idea,
        "plan_id": str(uuid.uuid4()),
        "tasks": [],
        "market_research": "",
        "competitor_analysis": "",
        "market_gap": "",
        "solution_strategy": "",
        "core_features": "",
        "revenue_model": "",
        "business_model": "",
        "implementation_roadmap": "",
        "pitch_deck_outline": "",
        "startup_title": "",
        "research_by_source": {},
        "research_brief": "",
        "market_sizing": "",
        "competitor_swot": "",
        "critique": "",
        "problem_statement": "",
        "target_audience": "",
        "executive_summary": "",
        "language": language,
        "doc_format": doc_format,
        "images": [],
        "pricing_model": "",
        "financial_projection": "",
        "cap_table": "",
        "matched_investors": "",
        "narration_status": {},
        "assets": {},
        "errors": [],
        "completed_nodes": [],
        "failed_nodes": [],
        "skipped_nodes": [],
        "run_summary": {},
        "owner_id": owner_id,
    }

    reset_circuit_breaker(session_id)
    try:
        await agent_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"[Agent] Error in workflow: {e}")
        if session_id in event_queues:
            await event_queues[session_id].put({
                "type": "error",
                "message": f"Agent encountered an error: {str(e)}",
            })
    finally:
        if session_id in event_queues:
            await event_queues[session_id].put(None)
        reset_circuit_breaker(session_id)
