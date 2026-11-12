# agent/tools.py
# Research tools used by the AutoStartup AI agent

import time
import random
import os
import json


def search_web(query: str, max_results: int = 4) -> str:
    """
    Search the web using DuckDuckGo (no API key needed).
    Returns formatted search results as a string.
    """
    try:
        from ddgs import DDGS
        time.sleep(random.uniform(0.5, 1.5))  # polite delay
        results = list(DDGS().text(query, max_results=max_results))
        if not results:
            return f"No results found for: {query}"
        formatted = []
        for r in results:
            formatted.append(
                f"Title: {r.get('title', 'N/A')}\n"
                f"URL: {r.get('href', 'N/A')}\n"
                f"Summary: {r.get('body', 'N/A')}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Search encountered an issue: {str(e)}. Using available knowledge instead."


import re

def derive_market_keywords(idea: str) -> str:
    """
    Derives industry category and domain search terms from startup idea / brand name.
    Preserves literal brand names for competitor searches while providing realistic
    industry categories for market size, growth, and demographic research.
    """
    cleaned = (idea or "").strip()
    lower = cleaned.lower()
    
    domain_hints = []
    if any(k in lower for k in ("agro", "farm", "crop", "agri", "harvest")):
        domain_hints.append("agriculture smart farming agritech crop diagnostics")
    if any(k in lower for k in ("safe", "guard", "protect", "women", "female", "security")):
        domain_hints.append("personal safety emergency alert wearable security")
    if any(k in lower for k in ("invoice", "bill", "pay", "finance", "fintech", "b2b", "accounting")):
        domain_hints.append("B2B invoice automation accounts payable fintech SaaS")
    if any(k in lower for k in ("health", "med", "doctor", "clinic", "patient", "clinical")):
        domain_hints.append("digital healthcare telemedicine medical software")
    if any(k in lower for k in ("edu", "learn", "tutor", "school", "student", "teach")):
        domain_hints.append("edtech online learning education platforms")

    # Remove generic brand suffixes (AI, App, SaaS, Platform, Tool)
    base_terms = re.sub(r"\b(ai|app|saas|platform|tool|startup|inc|tech|technologies)\b", "", cleaned, flags=re.IGNORECASE).strip()

    if domain_hints:
        return f"{domain_hints[0]} {base_terms}".strip()
    return base_terms if len(base_terms) >= 3 else cleaned


def research_market(idea: str) -> str:
    """Tool: Research market size, trends, and opportunities for an idea using category keywords."""
    cat = derive_market_keywords(idea)
    queries = [
        f"{cat} market size 2024 2026",
        f"{cat} industry growth CAGR report",
        f"{cat} target customers demand",
    ]
    all_results = []
    for q in queries:
        result = search_web(q, max_results=2)
        all_results.append(f"Query: {q}\n{result}")
    return "\n\n===\n\n".join(all_results)


def research_competitors(idea: str) -> str:
    """Tool: Research existing competitors using both category and brand name."""
    cat = derive_market_keywords(idea)
    queries = [
        f"{cat} top competitors companies startups",
        f"best platforms alternatives for {cat}",
        f"{idea} competitors",
    ]
    all_results = []
    for q in queries:
        result = search_web(q, max_results=2)
        all_results.append(f"Query: {q}\n{result}")
    return "\n\n===\n\n".join(all_results)


from agent.company_research import fetch_company_research
from agent.trends_service import fetch_google_trends
from agent.sentiment_service import analyze_sentiment
import asyncio

def search_crunchbase(query: str) -> str:
    """Real company research via Crunchbase, SEC EDGAR, or Wikidata."""
    res = fetch_company_research(query)
    return json.dumps(res, ensure_ascii=False)


def search_google_trends(query: str) -> str:
    """Real Google Trends interest and direction retrieval via pytrends."""
    res = fetch_google_trends(query)
    return json.dumps(res, ensure_ascii=False)


def search_sentiment(query: str) -> str:
    """Real sentiment analysis via Reddit PRAW and VADER scoring."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(asyncio.run, analyze_sentiment(query)).result()
        else:
            res = asyncio.run(analyze_sentiment(query))
        return json.dumps(res, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "failed",
            "reason": f"Sentiment analysis execution error: {e}",
            "data": None,
        })


# Tool registry for the agent's tool selection logic
AVAILABLE_TOOLS = {
    "research_market": {
        "function": research_market,
        "description": "Research market size, trends, and customer demand",
        "when_to_use": "Understanding market opportunity",
    },
    "research_competitors": {
        "function": research_competitors,
        "description": "Find existing competitors and their solutions",
        "when_to_use": "Competitive landscape analysis",
    },
    "search_web": {
        "function": search_web,
        "description": "General web search for any query",
        "when_to_use": "Specific fact-finding",
    },
    "search_crunchbase": {
        "function": search_crunchbase,
        "description": "Find funding and company data",
        "when_to_use": "When researching startup funding",
    },
    "search_google_trends": {
        "function": search_google_trends,
        "description": "Find search interest over time",
        "when_to_use": "When checking market demand trends",
    },
    "search_sentiment": {
        "function": search_sentiment,
        "description": "Check public sentiment on social media",
        "when_to_use": "When evaluating user sentiment",
    },
}


def select_tool(task: str) -> str:
    """
    Tool selection logic: given a task description,
    select the most appropriate tool.
    """
    task_lower = task.lower()
    if any(w in task_lower for w in ["market", "size", "demand", "trend", "customer"]):
        return "research_market"
    elif any(w in task_lower for w in ["competitor", "compan", "existing", "player"]):
        return "research_competitors"
    else:
        return "search_web"
