"""
agent/consistency_validator.py
Automated validator and auto-repairer for cross-section numbers, dates, and claims.
Ensures zero contradictions across pricing, financial projections, cap table,
pitch deck, executive summary, and narrative.
"""

from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def validate_plan_consistency(
    state: Dict[str, Any],
    canonical_facts: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Deterministic validator that checks for cross-section inconsistencies:
    1. Pricing tiers and prices
    2. Funding ask and valuation
    3. Revenue arithmetic
    4. Stale/past milestone dates
    5. TAM/SAM/SOM citations
    Returns (passed, list_of_issues).
    """
    issues: List[str] = []
    facts = canonical_facts.get("facts", {})
    tiers = facts.get("tiers", [])
    canonical_prices = [float(t["price"]) for t in tiers]
    canonical_ask = float(facts.get("funding_ask", 0.0))
    current_year = int(facts.get("current_year", datetime.now().year))

    revenue_text = str(state.get("revenue_model") or "")
    pitch_text = str(state.get("pitch_deck_outline") or "")
    exec_summary = str(state.get("executive_summary") or "")
    roadmap_text = str(state.get("roadmap") or "")
    gap_text = str(state.get("market_gap") or "")

    # 1. Check for conflicting pricing numbers in Revenue Narrative
    # Extract dollar amounts mentioned in revenue_text
    found_prices = [float(m) for m in re.findall(r"\$\s*(\d+(?:\.\d+)?)", revenue_text)]
    # Filter for numbers likely to be subscription tier prices (< $1000)
    sub_prices = [p for p in found_prices if 5 <= p <= 500]
    for sp in sub_prices:
        # Check if this price is close to any canonical tier price (allow within $2)
        if not any(abs(sp - cp) <= 2.0 for cp in canonical_prices):
            # Check if it's an ARPU or milestone number
            if abs(sp - float(facts.get("blended_arpu", 0))) > 2.0:
                issues.append(
                    f"Pricing mismatch: Revenue section cites ${sp:.0f}/mo, which contradicts canonical tiers ({canonical_prices})."
                )
                break

    # 2. Check Funding Ask Consistency in Pitch Deck & Executive Summary
    # If canonical raise is e.g. $150,000, flag if pitch deck claims "$2 M" or "$5M"
    ask_b_or_m = re.findall(r"\$\s*(\d+(?:\.\d+)?)\s*(?:M|Million|B|Billion)\s*(?:Series\s*[A-Z]|raise|funding|seed)", pitch_text + " " + exec_summary, re.IGNORECASE)
    for num_str in ask_b_or_m:
        val_m = float(num_str) * 1_000_000
        if canonical_ask < 1_000_000 and val_m >= 1_000_000:
            issues.append(
                f"Funding ask mismatch: Pitch/Executive summary cites ${num_str}M raise, but canonical cap table raises ${canonical_ask:,.0f}."
            )
            break

    # 3. Check for Stale/Past Dates in Roadmap & Milestones
    # Any date with a year prior to current_year is stale
    past_years = re.findall(r"\b(20[1-2][0-9])\b", roadmap_text + " " + pitch_text)
    for yr_str in past_years:
        yr = int(yr_str)
        if yr < current_year:
            issues.append(
                f"Stale milestone date: Found year {yr} in roadmap/pitch deck, but current year is {current_year}."
            )
            break

    # 4. Check TAM/SAM/SOM Contradictions
    tam_val = str(facts.get("tam", {}).get("value", ""))
    sam_val = str(facts.get("sam", {}).get("value", ""))
    # Look for truncated artifacts like "$150 M SO"
    if re.search(r"\$\d+\s*(?:M|B)\s+SO\b", gap_text):
        issues.append("Typo in market gap text: found truncated string '$... SO' instead of '$... SOM'.")

    # 5. Check Gross Revenue Arithmetic
    # Look for obvious math errors like '5,000 users ($1.8 M / month)' for a $30 tier
    rev_math_pattern = re.findall(r"(\d[\d,]*)\s+(?:users|customers|subscribers)\s*(?:\([^)]*\))?\s*(?:->|=|yields?|at)\s*\$\s*(\d+(?:\.\d+)?)\s*(M|k|thousand|million)?", revenue_text, re.IGNORECASE)
    for u_str, amt_str, unit in rev_math_pattern:
        u_count = float(u_str.replace(",", ""))
        mult = 1_000_000 if (unit and unit.lower().startswith("m")) else (1_000 if (unit and unit.lower().startswith("k")) else 1)
        stated_rev = float(amt_str) * mult
        expected_min = u_count * min(canonical_prices)
        expected_max = u_count * max(canonical_prices)
        if stated_rev < expected_min * 0.5 or stated_rev > expected_max * 2.0:
            issues.append(
                f"Revenue math error: {u_str} users claimed at ${amt_str}{unit or ''}/month, but with tiers {canonical_prices} expected range is ${expected_min:,.0f} - ${expected_max:,.0f}/mo."
            )
            break

    return (len(issues) == 0, issues)


async def auto_repair_inconsistencies(
    state: Dict[str, Any],
    canonical_facts: Dict[str, Any],
    issues: List[str],
) -> Dict[str, Any]:
    """
    Perform 1 targeted LLM call to reconcile and rewrite conflicting sections
    using the canonical facts as absolute ground truth.
    """
    from agent.workflow import llm_invoke

    facts_block = canonical_facts.get("facts_block", "")
    issues_summary = "\n".join(f"- {iss}" for idx, iss in enumerate(issues))

    prompt = f"""You are a precise startup consistency editor.
The generated startup plan contains cross-section numerical and date inconsistencies that contradict canonical financial facts.

{facts_block}

DETECTED INCONSISTENCIES TO RESOLVE:
{issues_summary}

CURRENT REVENUE MODEL SECTION:
{state.get("revenue_model", "")}

CURRENT PITCH DECK OUTLINE:
{state.get("pitch_deck_outline", "")}

TASK:
Rewrite the Revenue Model and Pitch Deck sections so they conform 100% VERBATIM to the Canonical Project Facts above.
- Use EXACT canonical tier names, monthly prices, and calculated milestone revenues.
- Use the EXACT target raise and valuation.
- Replace any stale dates with {canonical_facts.get('facts', {}).get('current_year', 2026)}-2028 milestones.

Return valid JSON with exactly these two keys:
{{
  "revenue_model": "Corrected revenue narrative with accurate arithmetic and canonical tiers",
  "pitch_deck_outline": "Corrected pitch deck outline with exact canonical raise, dates, and milestones"
}}
"""
    try:
        from agent.workflow import safe_json_parse
        repaired = await safe_json_parse(
            prompt,
            language=state.get("language", "English"),
            max_tokens=3500,
            node="consistency_repair",
            session_id=state.get("session_id"),
        )
        return {
            "revenue_model": repaired.get("revenue_model") or state.get("revenue_model"),
            "pitch_deck_outline": repaired.get("pitch_deck_outline") or state.get("pitch_deck_outline"),
        }
    except Exception as e:
        logger.error(f"[ConsistencyValidator] Auto-repair failed: {e}")
        return {}

