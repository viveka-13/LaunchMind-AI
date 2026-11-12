import json
from typing import Optional
from agent.investor_database import get_all_investors
from agent.models_pydantic import InvestorMatchModel

MAX_TOKENS_INVESTOR_MATCHING: int = 4096

INVESTOR_MATCH_PROMPT = """You are an elite VC matchmaker. Your task is to analyze the startup details and the list of available investors, and return the top 3 matching investors with concise reasoning.

[Startup Idea]: {idea}
[Revenue Model]: {revenue_model}
[Core Features]: {core_features}
[Required Funding (from Cap Table)]: {initial_cash}

[Available Investors (JSON)]:
{investors}

Scoring Algorithm Instructions:
- Sector compatibility: 40% weight
- Startup stage compatibility: 30% weight
- Investment size compatibility: 20% weight
- Location compatibility: 10% weight

Return ONLY valid JSON matching this schema:
{{
  "matched_investors": [
    {{
      "investor_name": "Name of the investor",
      "match_percentage": 85,
      "investment_stage": "e.g., Seed / Series A",
      "sector_focus": "e.g., Fintech / AI",
      "why_this_investor_matches": "Keep to 2 concise sentences explaining the fit.",
      "portfolio_examples": "e.g., They invested in X and Y",
      "expected_cheque_size": "e.g., $500K - $1M"
    }}
  ]
}}
"""

async def match_investors(
    idea: str,
    revenue_model: str,
    core_features: str,
    initial_cash: str,
    language: str = "English",
    session_id: Optional[str] = None,
) -> dict:
    from agent.workflow import safe_json_parse
    investors = get_all_investors()
    # Strip unnecessary fields for token saving
    slim_investors = [
        {
            "name": inv["name"],
            "type": inv["type"],
            "sector_focus": inv["sector_focus"],
            "stage_focus": inv["stage_focus"],
            "investment_range": inv["investment_range"],
            "portfolio_companies": inv["portfolio_companies"]
        } for inv in investors
    ]
    
    prompt = INVESTOR_MATCH_PROMPT.format(
        idea=idea,
        revenue_model=revenue_model[:300],
        core_features=core_features[:300],
        initial_cash=initial_cash,
        investors=json.dumps(slim_investors, indent=2)
    )
    
    result = await safe_json_parse(
        prompt,
        language,
        max_tokens=MAX_TOKENS_INVESTOR_MATCHING,
        model_cls=InvestorMatchModel,
        node="investor_matching",
        session_id=session_id,
    )
    return result
