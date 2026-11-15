# agent/tools.py
# Research tools used by the AutoStartup AI agent

import time
import random
import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Union, Optional, Tuple
from agent.research_filter import filter_and_rank_results


def search_web_items(query: str, max_results: int = 4) -> List[Dict[str, Any]]:
    """
    Search DuckDuckGo and return structured item dictionaries.
    Handles exceptions per query safely so a single failure never crashes research.
    """
    try:
        from ddgs import DDGS
        time.sleep(random.uniform(0.3, 0.8))  # polite delay
        results = list(DDGS().text(query, max_results=max_results))
        items = []
        for r in results:
            items.append({
                "query": query,
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
        return items
    except Exception as e:
        print(f"[Tools] search_web_items error for query '{query}': {e}")
        return []


def search_web(query: str, max_results: int = 4) -> str:
    """
    Search the web using DuckDuckGo (no API key needed).
    Returns formatted search results as a string.
    """
    items = search_web_items(query, max_results=max_results)
    if not items:
        return f"No results found for: {query}"
    formatted = []
    for r in items:
        formatted.append(
            f"Title: {r.get('title', 'N/A')}\n"
            f"URL: {r.get('url', 'N/A')}\n"
            f"Summary: {r.get('snippet', 'N/A')}"
        )
    return "\n\n---\n\n".join(formatted)


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
    elif any(k in lower for k in ("safe", "guard", "protect", "women", "female", "security")):
        domain_hints.append("personal safety emergency alert wearable security")
    elif any(k in lower for k in ("invoice", "bill", "pay", "finance", "fintech", "b2b", "accounting")):
        domain_hints.append("B2B invoice automation accounts payable fintech SaaS")
    elif any(k in lower for k in ("health", "med", "doctor", "clinic", "patient", "clinical")):
        domain_hints.append("digital healthcare telemedicine medical software")
    elif any(k in lower for k in ("edu", "learn", "tutor", "school", "student", "teach")):
        domain_hints.append("edtech online learning education platforms")

    # Remove generic brand suffixes (AI, App, SaaS, Platform, Tool)
    base_terms = re.sub(r"\b(ai|app|saas|platform|tool|startup|inc|tech|technologies)\b", "", cleaned, flags=re.IGNORECASE).strip()

    if domain_hints:
        return f"{domain_hints[0]} {base_terms}".strip()
    return base_terms if len(base_terms) >= 3 else cleaned


def research_market(
    idea_or_queries: Union[str, List[str]],
    understanding: Optional[dict] = None,
    return_meta: bool = False
) -> Union[str, Tuple[str, bool, List[str]]]:
    """
    Tool: Research market size, trends, and demand.
    Accepts explicit market_queries list from idea understanding, or falls back to category keywords.
    Filters and ranks results using agent.research_filter.
    Returns formatted_text, or (formatted_text, is_thin, data_gaps) if return_meta=True.
    """
    current_year = datetime.now().year
    if isinstance(idea_or_queries, list) and len(idea_or_queries) > 0:
        queries = [q for q in idea_or_queries if str(q).strip()]
    else:
        cat = derive_market_keywords(str(idea_or_queries))
        queries = [
            f"{cat} market size {current_year}",
            f"{cat} industry growth CAGR report",
            f"{cat} market demand forecasts",
        ]

    raw_items = []
    for q in queries:
        try:
            items = search_web_items(q, max_results=3)
            raw_items.extend(items)
        except Exception as e:
            print(f"[Tools] search_web_items error on '{q}': {e}")

    und = understanding or {}
    if not und and isinstance(idea_or_queries, str):
        und = {"category": derive_market_keywords(idea_or_queries), "problem_domain": idea_or_queries}

    filtered, is_thin, data_gaps = filter_and_rank_results(raw_items, und, max_keep=8)

    if not filtered:
        # Fallback if strict filter caught everything or offline
        if raw_items:
            filtered = raw_items[:5]
        else:
            text = f"Limited market research data available for this sector ({current_year})."
            return (text, True, [f"No empirical search data retrieved for {und.get('category', 'sector')}."]) if return_meta else text

    formatted = []
    for r in filtered:
        formatted.append(
            f"Query: {r.get('query', 'N/A')}\n"
            f"Source: {r.get('source', 'web')}\n"
            f"Title: {r.get('title', 'N/A')}\n"
            f"URL: {r.get('url', 'N/A')}\n"
            f"Summary: {r.get('snippet', 'N/A')}"
        )
    out_text = "\n\n===\n\n".join(formatted)
    return (out_text, is_thin, data_gaps) if return_meta else out_text


def research_competitors(
    idea_or_queries: Union[str, List[str]],
    understanding: Optional[dict] = None,
    competitor_name_check: Optional[str] = None,
    return_meta: bool = False
) -> Union[str, Tuple[str, bool, List[str]]]:
    """
    Tool: Research competitors using category queries and same-name brand check.
    Returns formatted_text, or (formatted_text, is_thin, data_gaps) if return_meta=True.
    """
    current_year = datetime.now().year
    und = understanding or {}
    same_name_note = ""

    if isinstance(idea_or_queries, list) and len(idea_or_queries) > 0:
        queries = [q for q in idea_or_queries if str(q).strip()]
    else:
        cat = derive_market_keywords(str(idea_or_queries))
        queries = [
            f"{cat} top competitors companies startups",
            f"best platforms alternatives for {cat}",
            f"{cat} market leaders software",
        ]

    # Add same-name check query if provided
    name_check = competitor_name_check or und.get("competitor_name_check")
    if name_check and name_check.lower() not in [q.lower() for q in queries]:
        queries.append(f"{name_check} company startup product")

    # If understanding already identified a known company with same name
    known_co = und.get("known_company_with_same_name")
    if known_co:
        same_name_note = f"Note: An existing company named '{name_check}' already operates in this space: {known_co}.\n\n"

    raw_items = []
    for q in queries:
        try:
            items = search_web_items(q, max_results=3)
            raw_items.extend(items)
        except Exception as e:
            print(f"[Tools] search_web_items error on '{q}': {e}")

    filtered, is_thin, data_gaps = filter_and_rank_results(raw_items, und, max_keep=8)

    if not filtered:
        if raw_items:
            filtered = raw_items[:5]
        else:
            text = same_name_note + f"Limited competitor research data found for this category ({current_year})."
            return (text, True, ["No empirical competitor results retrieved."]) if return_meta else text

    # Check if any search result confirms same name
    if name_check and not same_name_note:
        for r in raw_items:
            title_lower = r.get("title", "").lower()
            snip_lower = r.get("snippet", "").lower()
            if name_check.lower() in title_lower and any(w in (title_lower + " " + snip_lower) for w in ("company", "app", "platform", "software", "startup", "inc", "ltd")):
                same_name_note = f"Note: An existing product/company named '{name_check}' was discovered: '{r.get('title')} - {r.get('url')}'.\n\n"
                break

    formatted = []
    for r in filtered:
        formatted.append(
            f"Query: {r.get('query', 'N/A')}\n"
            f"Source: {r.get('source', 'web')}\n"
            f"Title: {r.get('title', 'N/A')}\n"
            f"URL: {r.get('url', 'N/A')}\n"
            f"Summary: {r.get('snippet', 'N/A')}"
        )
    out_text = same_name_note + "\n\n===\n\n".join(formatted)
    return (out_text, is_thin, data_gaps) if return_meta else out_text


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
