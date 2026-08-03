# agent/workflow.py
# LangGraph-powered autonomous agent workflow for AutoStartup AI

import asyncio
import json
import uuid
import os
from typing import TypedDict, List, Optional

from dotenv import load_dotenv
load_dotenv()  # Force load .env file

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

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
from agent.roadmap_generator import generate_roadmap_svg

# ─────────────────────────────────────────────
# Global event queue registry (per session)
# ─────────────────────────────────────────────
event_queues: dict[str, asyncio.Queue] = {}


async def emit(session_id: str, event: dict):
    """Push an event to the SSE stream for this session."""
    if session_id in event_queues:
        await event_queues[session_id].put(event)


# ─────────────────────────────────────────────
# LangGraph Agent State
# ─────────────────────────────────────────────

class StartupState(TypedDict):
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


# ─────────────────────────────────────────────
# LLM Setup
# ─────────────────────────────────────────────

def get_llm(max_tokens: int = 1500) -> ChatGroq:
    api_key = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        # Try loading from .env as last resort
        from dotenv import load_dotenv
        load_dotenv(override=False)
        api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found. Run: $env:GROQ_API_KEY='your_key_here'")
    return ChatGroq(
        model="llama-3.1-8b-instant",
        groq_api_key=api_key,
        max_tokens=max_tokens,
    )


async def llm_invoke(system_prompt: str, user_content: str, language: str = "English", max_tokens: int = 1500) -> str:
    """Call the LLM and return the response text."""
    llm = get_llm(max_tokens)
    system_prompt += f"\n\nCRITICAL: Respond entirely in the {language} language. Do not mix English unless the user explicitly uses English words, technical terms, or product names."
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    response = await llm.ainvoke(messages)
    return response.content.strip()


async def safe_json_parse(prompt: str, language: str = "English", system_prompt: str = "You are an AI assistant. Always respond with valid JSON only.", max_tokens: int = 1500) -> dict:
    """
    Helper to execute an LLM call and parse JSON safely.
    Implements 1 retry if the initial JSON is malformed.
    """
    response_text = await llm_invoke(system_prompt, prompt, language, max_tokens)
    
    def extract_json(text):
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()
        
    try:
        return json.loads(extract_json(response_text))
    except Exception as e:
        # Retry once
        retry_prompt = f"{prompt}\n\nYOUR LAST RESPONSE WAS NOT VALID JSON. Return ONLY valid JSON this time. Error: {str(e)}"
        retry_response = await llm_invoke(system_prompt, retry_prompt, language, max_tokens)
        try:
            return json.loads(extract_json(retry_response))
        except Exception:
            return {}

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
# LangGraph Node Functions (16 steps)
# ─────────────────────────────────────────────

async def node_decompose_idea(state: StartupState) -> dict:
    """
    Node 1: Task Decomposition
    Break the startup idea into 10 specific subtasks.
    Demonstrates: Task decomposition, planning & orchestration
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 1,
        "total": 16,
        "icon": "🧠",
        "title": "Decomposing Idea into Subtasks",
        "message": f"Analyzing '{state['idea']}' and breaking it into research subtasks...",
    })

    prompt = DECOMPOSE_PROMPT.format(idea=state["idea"])
    response = await llm_invoke(
        "You are an expert startup strategist. Always respond with valid JSON only.",
        prompt,
        state.get("language", "English")
    )

    try:
        # Clean and parse JSON
        clean = response.strip().strip("```json").strip("```").strip()
        tasks = json.loads(clean)
        if not isinstance(tasks, list):
            raise ValueError("Not a list")
    except Exception:
        tasks = [
            "Task 1: Analyze market size and growth potential",
            "Task 2: Identify primary and secondary target audiences",
            "Task 3: Research top 5 direct competitors",
            "Task 4: Identify unmet needs and pain points",
            "Task 5: Design core solution architecture",
            "Task 6: Define minimum viable product features",
            "Task 7: Model revenue streams and pricing",
            "Task 8: Plan go-to-market strategy",
            "Task 9: Assess technical requirements",
            "Task 10: Evaluate risks and mitigation strategies",
        ]

    await emit(sid, {
        "type": "tasks",
        "tasks": tasks,
        "message": f"Identified {len(tasks)} subtasks to execute autonomously.",
    })

    return {"tasks": tasks, "plan_id": str(uuid.uuid4())}


async def node_research_market(state: StartupState) -> dict:
    """
    Node 2: Market Research
    Uses the research_market tool to gather real market data.
    Demonstrates: Tool selection, tool calling/function calling
    """
    sid = state["session_id"]
    selected_tool = select_tool("market size demand trends")

    await emit(sid, {
        "type": "step",
        "step": 2,
        "total": 16,
        "icon": "🔍",
        "title": "Researching Market",
        "message": f"Selecting tool: [{selected_tool}] → Searching market data for '{state['idea']}'...",
        "tool": selected_tool,
    })

    # Execute tool in thread pool (blocking I/O)
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


async def node_research_competitors(state: StartupState) -> dict:
    """
    Node 3: Competitor Analysis
    Uses the research_competitors tool.
    Demonstrates: Tool selection, multi-step execution
    """
    sid = state["session_id"]
    selected_tool = select_tool("competitors existing companies")

    await emit(sid, {
        "type": "step",
        "step": 3,
        "total": 16,
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


async def node_store_research(state: StartupState) -> dict:
    """
    Node 4: Store in ChromaDB (RAG Memory)
    Stores all research in vector DB for contextual retrieval.
    Demonstrates: RAG retrieval, contextual memory
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 6,
        "total": 16,
        "icon": "💾",
        "title": "Storing Research in Vector Memory",
        "message": "Embedding research data into ChromaDB for RAG retrieval...",
    })

    loop = asyncio.get_event_loop()
    # Store market research
    await loop.run_in_executor(
        None, store_research,
        state["session_id"], state["idea"], "market", state["market_research"]
    )
    # Store competitor analysis
    await loop.run_in_executor(
        None, store_research,
        state["session_id"], state["idea"], "competitors", state["competitor_analysis"]
    )

    await emit(sid, {
        "type": "memory",
        "message": "Research stored in ChromaDB. RAG retrieval enabled for downstream nodes.",
    })

    return {}


async def node_synthesize_research(state: StartupState) -> dict:
    """
    Node 3.5a: Multi-Source Research Synthesizer
    Aggregates DuckDuckGo, Crunchbase, Google Trends, and Sentiment data.
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 4,
        "total": 16,
        "icon": "🧠",
        "title": "Synthesizing Research",
        "message": "Aggregating data from DuckDuckGo, Crunchbase, Google Trends, and Sentiment APIs...",
    })

    loop = asyncio.get_event_loop()
    idea = state["idea"]
    cb_data = await loop.run_in_executor(None, search_crunchbase, idea)
    gt_data = await loop.run_in_executor(None, search_google_trends, idea)
    sent_data = await loop.run_in_executor(None, search_sentiment, idea)

    research_sources = {
        "duckduckgo": state["market_research"] + "\n" + state["competitor_analysis"],
        "crunchbase": cb_data,
        "google_trends": gt_data,
        "sentiment": sent_data,
    }

    prompt = RESEARCH_SYNTHESIS_PROMPT.format(
        idea=idea,
        duckduckgo=research_sources["duckduckgo"][:1000],
        crunchbase=research_sources["crunchbase"],
        google_trends=research_sources["google_trends"],
        sentiment=research_sources["sentiment"],
    )

    brief = await safe_json_parse(prompt, state.get("language", "English"))
    lang = state.get("language", "English")
    
    brief_html = f"<b>{_t('Executive Summary', lang)}:</b><br/>{brief.get('executive_summary', '')}<br/><br/>"
    brief_html += f"<b>{_t('Key Findings', lang)}:</b><ul>"
    for f in brief.get('key_findings', []): brief_html += f"<li>{f}</li>"
    brief_html += "</ul><br/>"
    brief_html += f"<b>{_t('Market Sentiment', lang)}:</b> {brief.get('market_sentiment', '')}"

    
    await emit(sid, {
        "type": "section",
        "label": "Research Brief",
        "content": brief_html,
    })

    return {"research_by_source": research_sources, "research_brief": json.dumps(brief, ensure_ascii=False)}


async def node_competitor_swot(state: StartupState) -> dict:
    """
    Node 3.5b: Competitor Matrix & SWOT Analysis
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 5,
        "total": 16,
        "icon": "📊",
        "title": "Building Competitor Analysis",
        "message": "Generating Competitor Matrix and SWOT Analysis...",
    })

    prompt = COMPETITOR_SWOT_PROMPT.format(
        startup_idea=state["idea"],
        research_brief=state.get("research_brief", "{}"),
    )

    swot_data = await safe_json_parse(prompt, state.get("language", "English"))
    lang = state.get("language", "English")

    swot_html = f"<b>{_t('Competitors', lang)}:</b><ul>"
    for c in swot_data.get('competitors', []):
        swot_html += f"<li><b>{c.get('name', '')}</b>: {c.get('strengths', '')} / {c.get('weaknesses', '')}</li>"
    swot_html += f"</ul><br/><b>{_t('SWOT Analysis', lang)}:</b><ul>"
    swot_html += f"<li><b>{_t('Strengths', lang)}:</b> {', '.join(swot_data.get('swot_analysis', {}).get('strengths', []))}</li>"
    swot_html += f"<li><b>{_t('Weaknesses', lang)}:</b> {', '.join(swot_data.get('swot_analysis', {}).get('weaknesses', []))}</li>"
    # Just skipping opportunities/threats in HTML layout to keep it clean, or keep them if present.
    swot_html += f"<li><b>{_t('Opportunities', lang)}:</b> {', '.join(swot_data.get('swot_analysis', {}).get('opportunities', []))}</li>"
    swot_html += f"<li><b>{_t('Threats', lang)}:</b> {', '.join(swot_data.get('swot_analysis', {}).get('threats', []))}</li></ul>"

    await emit(sid, {
        "type": "section",
        "label": "Competitor SWOT",
        "content": swot_html,
    })

    return {"competitor_swot": json.dumps(swot_data, ensure_ascii=False)}


async def node_analyze_gaps(state: StartupState) -> dict:
    """
    Node 5: Identify Market Gaps
    Uses stored RAG context + LLM to find market gaps.
    Demonstrates: RAG retrieval, LLM usage
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 7,
        "total": 16,
        "icon": "🎯",
        "title": "Identifying Market Gaps",
        "message": "Retrieving context from ChromaDB → Analyzing gaps with LLM...",
    })

    # RAG: Retrieve relevant context
    loop = asyncio.get_event_loop()
    rag_context = await loop.run_in_executor(
        None, retrieve_similar,
        f"market gap opportunity {state['idea']}", state["session_id"]
    )

    # Augment with retrieved context and new research brief
    full_market = state["market_research"]
    research_brief = state.get("research_brief", "")
    if rag_context:
        full_market = f"[RAG Retrieved Context]\n{rag_context}\n\n[Research Brief]\n{research_brief}\n\n[Full Research]\n{full_market}"

    gap_prompt = MARKET_GAP_PROMPT.format(
        idea=state["idea"],
        market_research=full_market[:800],
        competitor_analysis=state.get("competitor_swot", state["competitor_analysis"])[:600],
    )

    market_gap = await llm_invoke(
        "You are a strategic market analyst. Be specific and insightful.",
        gap_prompt,
        state.get("language", "English")
    )

    await emit(sid, {
        "type": "section",
        "label": "Market Gap Analysis",
        "content": market_gap,
    })

    return {"market_gap": market_gap}


async def node_calculate_market_size(state: StartupState) -> dict:
    """
    Node 5.5: TAM / SAM / SOM Calculator
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 8,
        "total": 16,
        "icon": "📈",
        "title": "Calculating Market Size",
        "message": "Estimating TAM, SAM, and SOM...",
    })

    prompt = MARKET_SIZING_PROMPT.format(
        startup_idea=state["idea"],
        research_brief=state.get("research_brief", "{}"),
    )

    market_sizing = await safe_json_parse(prompt, state.get("language", "English"))
    lang = state.get("language", "English")

    size_html = f"<b>{_t('TAM', lang)}:</b> {market_sizing.get('tam', '')}<br/>"
    size_html += f"<b>{_t('SAM', lang)}:</b> {market_sizing.get('sam', '')}<br/>"
    size_html += f"<b>{_t('SOM', lang)}:</b> {market_sizing.get('som', '')}<br/><br/>"
    size_html += f"<b>{_t('Growth Rate', lang)}:</b> {market_sizing.get('methodology', '')}"


    await emit(sid, {
        "type": "section",
        "label": "Market Sizing",
        "content": size_html,
    })

    return {"market_sizing": json.dumps(market_sizing, ensure_ascii=False)}


async def node_generate_solution(state: StartupState) -> dict:
    """
    Node 6: Generate Solution Strategy
    LLM generates solution based on all gathered context.
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 9,
        "total": 16,
        "icon": "💡",
        "title": "Generating Solution Strategy",
        "message": "Designing solution based on market gap analysis...",
    })

    solution_prompt = SOLUTION_PROMPT.format(
        idea=state["idea"],
        market_gap=state["market_gap"][:500],
        market_research=state["market_research"][:600] + "\nCompetitors: " + state.get("competitor_swot", "")[:300],
    )

    solution = await llm_invoke(
        "You are a visionary product strategist. Be compelling and specific.",
        solution_prompt,
        state.get("language", "English")
    )

    await emit(sid, {
        "type": "section",
        "label": "Solution Strategy",
        "content": solution,
    })

    return {"solution_strategy": solution}


async def node_generate_features(state: StartupState) -> dict:
    """Node 7: Generate Core Product Features"""
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 10,
        "total": 16,
        "icon": "⚡",
        "title": "Designing Core Features",
        "message": "Generating product features based on solution strategy...",
    })

    features_prompt = FEATURES_PROMPT.format(
        idea=state["idea"],
        solution=state["solution_strategy"][:600] + "\nCompetitors: " + state.get("competitor_swot", "")[:300],
    )

    features = await llm_invoke(
        "You are a senior product manager. Create practical, valuable features.",
        features_prompt,
        state.get("language", "English")
    )

    await emit(sid, {
        "type": "section",
        "label": "Core Features",
        "content": features,
    })

    return {"core_features": features}


async def node_generate_revenue(state: StartupState) -> dict:
    """Node 8: Generate Revenue Model"""
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 11,
        "total": 16,
        "icon": "💰",
        "title": "Modeling Revenue Streams",
        "message": "Creating revenue model and business model...",
    })

    revenue_prompt = REVENUE_PROMPT.format(
        idea=state["idea"],
        solution=state["solution_strategy"][:500],
        market_research=state["market_research"][:500] + "\nSizing: " + state.get("market_sizing", "")[:300],
    )

    revenue = await llm_invoke(
        "You are a startup financial strategist. Be specific with numbers.",
        revenue_prompt,
        state.get("language", "English")
    )

    await emit(sid, {
        "type": "section",
        "label": "Revenue Model",
        "content": revenue,
    })

    return {"revenue_model": revenue, "business_model": revenue}


async def node_generate_roadmap(state: StartupState) -> dict:
    """Node 9: Generate Implementation Roadmap"""
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 12,
        "total": 16,
        "icon": "🗺️",
        "title": "Building Implementation Roadmap",
        "message": "Planning 12-month execution roadmap...",
    })

    roadmap_prompt = ROADMAP_PROMPT.format(
        idea=state["idea"],
        features=state["core_features"][:400],
        revenue=state["revenue_model"][:400],
    )

    roadmap = await llm_invoke(
        "You are a startup CTO. Create realistic, achievable milestones.",
        roadmap_prompt,
        state.get("language", "English")
    )

    await emit(sid, {
        "type": "section",
        "label": "Implementation Roadmap",
        "content": roadmap,
    })

    return {"implementation_roadmap": roadmap}


async def node_generate_pitch(state: StartupState) -> dict:
    """Node 10: Generate Pitch Deck Outline"""
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 13,
        "total": 16,
        "icon": "🎤",
        "title": "Creating Pitch Deck Outline",
        "message": "Structuring investor pitch deck...",
    })

    pitch_prompt = PITCH_PROMPT.format(
        idea=state["idea"],
        solution=state["solution_strategy"][:400],
        revenue=state["revenue_model"][:400],
        market_research=state["market_research"][:500],
    )

    pitch = await llm_invoke(
        "You are a top startup pitch coach. Create a compelling narrative.",
        pitch_prompt,
        state.get("language", "English")
    )

    await emit(sid, {
        "type": "section",
        "label": "Pitch Deck Outline",
        "content": pitch,
    })

    return {"pitch_deck_outline": pitch}


async def node_compile_plan(state: StartupState) -> dict:
    """
    Node 11: Compile Final Plan
    Generates title, problem statement, target audience, executive summary.
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 14,
        "total": 16,
        "icon": "📋",
        "title": "Compiling Executive Summary",
        "message": "Synthesizing all research into final startup report...",
    })

    all_context = f"""
Market Research: {state['market_research'][:400]}
Competitor Analysis: {state['competitor_analysis'][:400]}
Market Gap: {state['market_gap'][:300]}
Solution: {state['solution_strategy'][:300]}
Features: {state['core_features'][:300]}
Revenue: {state['revenue_model'][:300]}
Roadmap: {state['implementation_roadmap'][:300]}
"""

    compile_prompt = COMPILE_PROMPT.format(
        idea=state["idea"],
        all_context=all_context,
    )

    compiled = await llm_invoke(
        "You are a senior business analyst. Be compelling and precise.",
        compile_prompt,
        state.get("language", "English")
    )

    # Parse the structured response
    startup_title = state["idea"].title()
    problem_statement = ""
    target_audience = ""
    executive_summary = ""

    lines = compiled.split("\n")
    current_key = None
    buffer = []

    def flush(key, buf):
        text = " ".join(buf).strip()
        nonlocal startup_title, problem_statement, target_audience, executive_summary
        if key == "STARTUP_TITLE":
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

    # Fallbacks
    if not problem_statement:
        problem_statement = f"The {state['idea']} sector lacks modern, AI-powered solutions that address user needs effectively."
    if not target_audience:
        target_audience = f"Primary users of {state['idea']} solutions seeking improved efficiency and outcomes."
    if not executive_summary:
        executive_summary = f"Our startup addresses the growing demand in the {state['idea']} space by providing an innovative AI-powered platform that solves key market gaps identified through extensive research."

    return {
        "startup_title": startup_title,
        "problem_statement": problem_statement,
        "target_audience": target_audience,
        "executive_summary": executive_summary,
    }


async def node_adversarial_review(state: StartupState) -> dict:
    """
    Node 11.5: Devil's Advocate / Adversarial Review
    """
    sid = state["session_id"]
    await emit(sid, {
        "type": "step",
        "step": 15,
        "total": 16,
        "icon": "⚖️",
        "title": "Running Investor Review",
        "message": "Performing adversarial review to find critical flaws...",
    })

    compiled_plan = f"Title: {state.get('startup_title', '')}\nSummary: {state.get('executive_summary', '')}\nProblem: {state.get('problem_statement', '')}\nSolution: {state.get('solution_strategy', '')}\nRevenue: {state.get('revenue_model', '')}"

    prompt = DEVILS_ADVOCATE_PROMPT.format(
        startup_idea=state.get('startup_idea', '')[:500],
        compiled_plan=compiled_plan[:1500],
    )

    critique = await safe_json_parse(prompt, state.get("language", "English"), max_tokens=500)

    # Extract score & verdict
    scores = critique.get('scores', {})
    final = critique.get('final_verdict', {})
    action_plan = critique.get('action_plan', {})
    lang = state.get("language", "English")

    crit_html = f"<b>{_t('Overall Feasibility Score', lang)}:</b> {scores.get('overall_feasibility_score', 'N/A')}/100<br/>"
    crit_html += f"<b>{_t('Final Verdict', lang)}:</b> {final.get('verdict', 'N/A')}<br/><br/>"
    
    crit_html += f"<b>{_t('Why', lang)}:</b> {final.get('why', '')}<br/><br/>"

    crit_html += f"<b>{_t('Key Score Breakdown', lang)}:</b><ul>"

    crit_html += f"<li>Problem Validation: {scores.get('problem_validation', 'N/A')}/10</li>"
    crit_html += f"<li>Market Opportunity: {scores.get('market_opportunity', 'N/A')}/10</li>"
    crit_html += f"<li>Revenue Model: {scores.get('revenue_model', 'N/A')}/10</li>"
    crit_html += "</ul><br/>"

    crit_html += "<b>Priority 1 Actions (Critical):</b><ul>"
    for a in action_plan.get('priority_1', []):
        crit_html += f"<li><b>{a.get('problem', '')}</b>: {a.get('solution', '')} (Impact: {a.get('expected_impact', '')})</li>"
    crit_html += "</ul>"

    await emit(sid, {
        "type": "section",
        "label": "Investor Review",
        "content": crit_html,
    })

    return {"critique": json.dumps(critique, ensure_ascii=False)}


async def node_save_plan(state: StartupState) -> dict:
    """
    Node 12: Save to SQLite Memory & Generate Documents
    Routes to PPT, PDF, or Word generator based on doc_format.
    Also fetches Pexels images and a system flowchart for embedding.
    """
    sid = state["session_id"]
    doc_format = state.get("doc_format", "ppt")

    await emit(sid, {
        "type": "step",
        "step": 16,
        "total": 16,
        "icon": "[OK]",
        "title": f"Saving Plan & Generating {doc_format.upper()} Document",
        "message": "Storing complete plan in SQLite. Generating your professional document...",
    })

    plan_data = {
        "startup_title": state.get("startup_title", state["idea"].title()),
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
    }

    loop = asyncio.get_event_loop()

    # Persist plan to SQLite
    await loop.run_in_executor(
        None,
        save_startup_plan,
        state["plan_id"],
        state["idea"],
        plan_data["startup_title"],
        plan_data,
    )

    # ── Phase 4: Fetch images from Pexels (non-blocking) ──
    images = []
    flowchart_path = None
    try:
        images = await loop.run_in_executor(
            None, fetch_images_for_startup, state["idea"], 3
        )
        flowchart_path = await loop.run_in_executor(
            None, generate_flowchart, state["plan_id"]
        )
    except Exception as e:
        print(f"[Workflow] Image/flowchart fetch failed (non-fatal): {e}")

    os.makedirs("./data/documents", exist_ok=True)
    os.makedirs("./data/presentations", exist_ok=True)

    # ── Phase 5: Route to correct document generator ──
    if doc_format == "word":
        doc_path = f"./data/documents/{state['plan_id']}.docx"
        await loop.run_in_executor(
            None, generate_business_plan_word, plan_data, doc_path, images, flowchart_path
        )
    elif doc_format == "pdf":
        doc_path = f"./data/documents/{state['plan_id']}.pdf"
        await loop.run_in_executor(
            None, generate_business_plan_pdf, plan_data, doc_path, images, flowchart_path
        )
    else:  # default: ppt
        ppt_path = f"./data/presentations/{state['plan_id']}.pptx"
        await loop.run_in_executor(
            None, generate_pitch_deck_ppt, plan_data, ppt_path, images, flowchart_path
        )

    # ── Phase 6: Generate Business Roadmap SVG ──
    os.makedirs("./data/roadmaps", exist_ok=True)
    roadmap_path = f"./data/roadmaps/{state['plan_id']}.svg"
    try:
        await loop.run_in_executor(
            None, generate_roadmap_svg, plan_data, roadmap_path
        )
    except Exception as e:
        print(f"[Workflow] Roadmap SVG generation failed (non-fatal): {e}")

    # Emit the complete final plan (include doc_format so frontend shows right button)
    await emit(sid, {
        "type": "complete",
        "plan_id": state["plan_id"],
        "plan": plan_data,
    })

    # Signal end of stream
    await emit(sid, None)

    return {"images": images}


# ─────────────────────────────────────────────
# Build the LangGraph Workflow
# ─────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the LangGraph state machine."""
    workflow = StateGraph(StartupState)

    # Add all 16 nodes
    workflow.add_node("decompose", node_decompose_idea)
    workflow.add_node("research_market", node_research_market)
    workflow.add_node("research_competitors", node_research_competitors)
    workflow.add_node("synthesize_research", node_synthesize_research)
    workflow.add_node("competitor_swot", node_competitor_swot)
    workflow.add_node("store_research", node_store_research)
    workflow.add_node("analyze_gaps", node_analyze_gaps)
    workflow.add_node("calculate_market_size", node_calculate_market_size)
    workflow.add_node("generate_solution", node_generate_solution)
    workflow.add_node("generate_features", node_generate_features)
    workflow.add_node("generate_revenue", node_generate_revenue)
    workflow.add_node("generate_roadmap", node_generate_roadmap)
    workflow.add_node("generate_pitch", node_generate_pitch)
    workflow.add_node("compile_plan", node_compile_plan)
    workflow.add_node("adversarial_review", node_adversarial_review)
    workflow.add_node("save_plan", node_save_plan)

    # Sequential edges
    workflow.set_entry_point("decompose")
    workflow.add_edge("decompose", "research_market")
    workflow.add_edge("research_market", "research_competitors")
    workflow.add_edge("research_competitors", "synthesize_research")
    workflow.add_edge("synthesize_research", "competitor_swot")
    workflow.add_edge("competitor_swot", "store_research")
    workflow.add_edge("store_research", "analyze_gaps")
    workflow.add_edge("analyze_gaps", "calculate_market_size")
    workflow.add_edge("calculate_market_size", "generate_solution")
    workflow.add_edge("generate_solution", "generate_features")
    workflow.add_edge("generate_features", "generate_revenue")
    workflow.add_edge("generate_revenue", "generate_roadmap")
    workflow.add_edge("generate_roadmap", "generate_pitch")
    workflow.add_edge("generate_pitch", "compile_plan")
    workflow.add_edge("compile_plan", "adversarial_review")
    workflow.add_edge("adversarial_review", "save_plan")
    workflow.add_edge("save_plan", END)

    return workflow.compile()


# Compile graph at module load
agent_graph = build_graph()


# ─────────────────────────────────────────────
# Main entry point for running the agent
# ─────────────────────────────────────────────

async def run_agent(idea: str, session_id: str, language: str = "English", doc_format: str = "ppt"):
    """
    Run the full 16-step autonomous agent workflow.
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
    }

    try:
        await agent_graph.ainvoke(initial_state)
    except Exception as e:
        print(f"[Agent] Error in workflow: {e}")
        if session_id in event_queues:
            await event_queues[session_id].put({
                "type": "error",
                "message": f"Agent encountered an error: {str(e)}",
            })
            await event_queues[session_id].put(None)
