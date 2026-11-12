"""
agent/canonical_facts.py
Single Source of Truth and Deterministic Calculator for AutoStartup AI.
Computes all financial milestones, revenue arithmetic, break-even, runway,
and ownership deterministically in code.
"""

from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _parse_currency_num(val: Any) -> float:
    """Extract numeric value from string (e.g. '$150,000', '150k', '3M')."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "")
    match = re.search(r"([\d\.]+)\s*([kmbKMB])?", s)
    if not match:
        return 0.0
    num = float(match.group(1))
    mult = match.group(2)
    if mult:
        mult = mult.lower()
        if mult == "k":
            num *= 1_000
        elif mult == "m":
            num *= 1_000_000
        elif mult == "b":
            num *= 1_000_000_000
    return num


def _format_currency(amount: float, currency_symbol: str = "$") -> str:
    """Format numeric amount into human-friendly currency string."""
    if amount >= 1_000_000_000:
        return f"{currency_symbol}{amount / 1_000_000_000:.2f} B".rstrip("0").rstrip(".")
    if amount >= 1_000_000:
        return f"{currency_symbol}{amount / 1_000_000:.2f} M".rstrip("0").rstrip(".")
    if amount >= 1_000:
        return f"{currency_symbol}{amount:,.0f}"
    return f"{currency_symbol}{amount:.2f}".rstrip("0").rstrip(".")


def build_canonical_facts(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construct canonical facts dictionary and formatted prompt block.
    """
    now = datetime.now()
    current_date_str = now.strftime("%B %Y")  # e.g. "November 2026"
    current_year = now.year

    # 1. Currency & Pricing Tiers
    pricing_data = state.get("pricing_tiers") or state.get("pricing_model") or {}
    if isinstance(pricing_data, str):
        try:
            pricing_data = json.loads(pricing_data)
        except Exception:
            pricing_data = {}

    raw_tiers = pricing_data.get("tiers") or []
    currency_symbol = "$"
    tiers: List[Dict[str, Any]] = []

    if raw_tiers:
        for idx, t in enumerate(raw_tiers):
            t_name = t.get("name") or f"Tier {chr(65 + idx)}"
            t_price_raw = t.get("price") or 0.0
            t_price = _parse_currency_num(t_price_raw)
            if "$" in str(t_price_raw):
                currency_symbol = "$"
            elif "₹" in str(t_price_raw):
                currency_symbol = "₹"
            elif "€" in str(t_price_raw):
                currency_symbol = "€"
            tiers.append({
                "name": t_name,
                "price": t_price,
                "billing": t.get("billing") or "monthly",
                "features": t.get("features") or [],
            })
    else:
        # Fallback default canonical tiers if pricing was somehow empty
        tiers = [
            {"name": "Starter", "price": 29.0, "billing": "monthly", "features": ["Core features", "Standard support"]},
            {"name": "Professional", "price": 79.0, "billing": "monthly", "features": ["Advanced analytics", "Priority support"]},
            {"name": "Enterprise", "price": 199.0, "billing": "monthly", "features": ["Custom integrations", "Dedicated SLA"]},
        ]

    # Blended ARPU: 60% tier 1, 30% tier 2, 10% tier 3 (or evenly distributed)
    if len(tiers) >= 3:
        blended_arpu = 0.60 * tiers[0]["price"] + 0.30 * tiers[1]["price"] + 0.10 * tiers[2]["price"]
    elif len(tiers) == 2:
        blended_arpu = 0.70 * tiers[0]["price"] + 0.30 * tiers[1]["price"]
    elif len(tiers) == 1:
        blended_arpu = tiers[0]["price"]
    else:
        blended_arpu = 49.0
    blended_arpu = max(blended_arpu, 1.0)

    # 2. Financial Projection Facts
    fin_data = state.get("financial_projection") or {}
    if isinstance(fin_data, str):
        try:
            fin_data = json.loads(fin_data)
        except Exception:
            fin_data = {}

    monthly_burn = _parse_currency_num(fin_data.get("monthly_burn_rate") or fin_data.get("fixed_monthly_burn") or 25_000)
    if monthly_burn <= 0:
        monthly_burn = 25_000.0

    cogs_pct = float(fin_data.get("cogs_percentage") or 20.0)
    gross_margin_pct = float(fin_data.get("gross_margin_percentage") or (100.0 - cogs_pct))

    # 3. Cap Table & Funding Ask
    cap_data = state.get("cap_table") or {}
    if isinstance(cap_data, str):
        try:
            cap_data = json.loads(cap_data)
        except Exception:
            cap_data = {}

    funding_ask = _parse_currency_num(cap_data.get("target_raise") or cap_data.get("initial_cash") or 150_000)
    if funding_ask <= 0:
        funding_ask = 150_000.0

    pre_money = _parse_currency_num(cap_data.get("pre_money_valuation") or (funding_ask * 10))
    if pre_money <= 0:
        pre_money = funding_ask * 10

    post_money = pre_money + funding_ask
    equity_pct = (funding_ask / post_money) * 100.0

    use_of_funds = cap_data.get("use_of_funds") or {
        "Product & Engineering": 45,
        "Go-to-Market & Sales": 25,
        "Operations & Data Infrastructure": 15,
        "Legal & Regulatory Compliance": 15,
    }

    # 4. Market Sizing Facts
    ms_data = state.get("market_sizing") or {}
    if isinstance(ms_data, str):
        try:
            ms_data = json.loads(ms_data)
        except Exception:
            ms_data = {}

    def _extract_ms_field(val: Any, default_val: str) -> Dict[str, Any]:
        if isinstance(val, dict):
            return {
                "value": str(val.get("value") or default_val),
                "basis": str(val.get("basis") or "estimate"),
                "assumptions": str(val.get("assumptions") or ""),
            }
        return {"value": str(val or default_val), "basis": "estimate", "assumptions": ""}

    tam_info = _extract_ms_field(ms_data.get("tam"), "$10 B")
    sam_info = _extract_ms_field(ms_data.get("sam"), "$2 B")
    som_info = _extract_ms_field(ms_data.get("som"), "$100 M")
    cagr_str = str(ms_data.get("cagr") or "14.5%")

    # 5. Deterministic Unit Economics & Milestones
    rev_500 = 500 * blended_arpu
    rev_5000 = 5_000 * blended_arpu
    rev_20000 = 20_000 * blended_arpu

    breakeven_users = int(monthly_burn / (blended_arpu * (gross_margin_pct / 100.0)))
    breakeven_rev = breakeven_users * blended_arpu

    runway_months = round(funding_ask / monthly_burn, 1) if monthly_burn > 0 else 18.0

    monthly_churn_pct = 3.0
    ltv = blended_arpu * (100.0 / monthly_churn_pct)  # 33.3 months lifespan
    cac = blended_arpu * 3.5  # ~3.5 month payback target
    cac_payback_months = round(cac / (blended_arpu * (gross_margin_pct / 100.0)), 1)

    target_audience = state.get("target_audience") or "Target commercial users and businesses"

    facts = {
        "current_date": current_date_str,
        "current_year": current_year,
        "currency_symbol": currency_symbol,
        "tiers": tiers,
        "blended_arpu": round(blended_arpu, 2),
        "monthly_burn": monthly_burn,
        "gross_margin_pct": gross_margin_pct,
        "cogs_pct": cogs_pct,
        "funding_ask": funding_ask,
        "pre_money_valuation": pre_money,
        "post_money_valuation": post_money,
        "investor_equity_pct": round(equity_pct, 1),
        "use_of_funds": use_of_funds,
        "tam": tam_info,
        "sam": sam_info,
        "som": som_info,
        "cagr": cagr_str,
        "milestones": {
            "500_users": {"monthly_rev": rev_500, "annual_arr": rev_500 * 12},
            "5000_users": {"monthly_rev": rev_5000, "annual_arr": rev_5000 * 12},
            "20000_users": {"monthly_rev": rev_20000, "annual_arr": rev_20000 * 12},
        },
        "breakeven": {
            "users": breakeven_users,
            "monthly_rev": breakeven_rev,
        },
        "runway_months": runway_months,
        "ltv": round(ltv, 2),
        "cac": round(cac, 2),
        "cac_payback_months": cac_payback_months,
        "target_audience": target_audience,
    }

    # Build Prompt Block
    tier_lines = [
        f"  - {t['name']}: {_format_currency(t['price'], currency_symbol)} / {t['billing']}"
        for t in tiers
    ]
    use_funds_lines = [f"  - {k}: {v}%" for k, v in use_of_funds.items()]

    block = f"""
================================================================================
CANONICAL PROJECT FACTS (SINGLE SOURCE OF TRUTH - MANDATORY VERBATIM ADHERENCE)
================================================================================
Current Date: {current_date_str} (All future milestones must be scheduled for {current_year} onwards)
Target Audience: {target_audience}

PRICING TIERS:
{chr(10).join(tier_lines)}
- Blended Monthly ARPU: {_format_currency(blended_arpu, currency_symbol)}/user/month

DETERMINISTIC REVENUE MILESTONES (DO NOT INVENT DIFFERENT NUMBERS):
- 500 active users:   {_format_currency(rev_500, currency_symbol)} / month  ({_format_currency(rev_500 * 12, currency_symbol)} ARR)
- 5,000 active users: {_format_currency(rev_5000, currency_symbol)} / month  ({_format_currency(rev_5000 * 12, currency_symbol)} ARR)
- 20,000 active users: {_format_currency(rev_20000, currency_symbol)} / month  ({_format_currency(rev_20000 * 12, currency_symbol)} ARR)
- Unit Economics: LTV = {_format_currency(ltv, currency_symbol)}, CAC = {_format_currency(cac, currency_symbol)} (Payback in {cac_payback_months} months)
- Break-Even: {breakeven_users:,} paying users = {_format_currency(breakeven_rev, currency_symbol)} / month

FUNDING & CAPITALIZATION:
- Target Capital Raise: {_format_currency(funding_ask, currency_symbol)}
- Pre-Money Valuation:  {_format_currency(pre_money, currency_symbol)}
- Investor Ownership:   {equity_pct:.1f}% equity post-money
- Monthly Burn Rate:    {_format_currency(monthly_burn, currency_symbol)}
- Cash Runway:          {runway_months} months
- Use of Proceeds:
{chr(10).join(use_funds_lines)}

MARKET SIZING (SOURCE OF TRUTH):
- TAM: {tam_info['value']} ({tam_info['basis']})
- SAM: {sam_info['value']} ({sam_info['basis']})
- SOM: {som_info['value']} ({som_info['basis']})
- CAGR: {cagr_str}

CRITICAL CONSISTENCY DIRECTIVES:
1. Every section you produce MUST cite these EXACT tier names, prices, and revenue milestones.
2. DO NOT contradict the {_format_currency(funding_ask, currency_symbol)} raise or invent a different funding stage.
3. DO NOT cite outdated dates (anything before {current_year} is historic; roadmap milestones must be Q1 {current_year} through 2028).
================================================================================
"""
    return {
        "facts": facts,
        "facts_block": block.strip(),
    }

