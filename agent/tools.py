# agent/tools.py
# Research tools used by the AutoStartup AI agent

import time
import random


def search_web(query: str, max_results: int = 4) -> str:
    """
    Search the web using DuckDuckGo (no API key needed).
    Returns formatted search results as a string.
    """
    try:
        from duckduckgo_search import DDGS
        time.sleep(random.uniform(0.5, 1.5))  # polite delay
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
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


def research_market(idea: str) -> str:
    """Tool: Research market size, trends, and opportunities for an idea."""
    queries = [
        f"{idea} market size 2024",
        f"{idea} industry trends growth",
        f"{idea} target customers demand",
    ]
    all_results = []
    for q in queries:
        result = search_web(q, max_results=2)
        all_results.append(f"Query: {q}\n{result}")
    return "\n\n===\n\n".join(all_results)


def research_competitors(idea: str) -> str:
    """Tool: Research existing competitors and their offerings."""
    queries = [
        f"{idea} top companies startups 2024",
        f"best apps platforms for {idea}",
        f"{idea} existing solutions problems",
    ]
    all_results = []
    for q in queries:
        result = search_web(q, max_results=2)
        all_results.append(f"Query: {q}\n{result}")
    return "\n\n===\n\n".join(all_results)


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
