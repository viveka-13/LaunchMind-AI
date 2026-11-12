import pytest
from agent.canonical_facts import build_canonical_facts

def test_canonical_calculator_exact_math():
    """Verify deterministic calculations for ARPU, milestone revenues, break-even, runway, and ownership."""
    state = {
        "idea": "AgroMind AI",
        "target_audience": "Smallholder farmers in India",
        "pricing_tiers": {
            "tiers": [
                {"name": "Starter", "price": 29.0, "billing": "monthly", "features": ["Diagnostic AI"]},
                {"name": "Professional", "price": 79.0, "billing": "monthly", "features": ["Yield forecasting"]},
                {"name": "Enterprise", "price": 199.0, "billing": "monthly", "features": ["Custom satellite feeds"]},
            ]
        },
        "financial_projection": {
            "monthly_burn_rate": 25000,
            "cogs_percentage": 20.0,
            "gross_margin_percentage": 80.0,
        },
        "cap_table": {
            "target_raise": 150000,
            "pre_money_valuation": 3000000,
            "use_of_funds": {
                "Engineering": 45,
                "Sales & Marketing": 25,
                "Operations": 15,
                "Legal": 15
            }
        },
        "market_sizing": {
            "tam": {"value": "$10 B", "basis": "estimate"},
            "sam": {"value": "$2 B", "basis": "estimate"},
            "som": {"value": "$100 M", "basis": "estimate"},
            "cagr": "15%"
        }
    }

    res = build_canonical_facts(state)
    facts = res["facts"]

    # 1. Blended ARPU: 0.60 * 29 + 0.30 * 79 + 0.10 * 199 = 17.4 + 23.7 + 19.9 = 61.0
    expected_arpu = 61.0
    assert abs(facts["blended_arpu"] - expected_arpu) < 0.01

    # 2. Milestones
    assert facts["milestones"]["500_users"]["monthly_rev"] == 500 * expected_arpu
    assert facts["milestones"]["5000_users"]["monthly_rev"] == 5000 * expected_arpu
    assert facts["milestones"]["20000_users"]["monthly_rev"] == 20000 * expected_arpu

    # 3. Break-even: 25000 / (61.0 * 0.80) = 25000 / 48.8 = 512.29 -> 512 users
    assert facts["breakeven"]["users"] == int(25000 / (61.0 * 0.80))

    # 4. Runway: 150000 / 25000 = 6.0 months
    assert facts["runway_months"] == 6.0

    # 5. Investor Equity: 150000 / (3000000 + 150000) = 150000 / 3150000 = 4.76% -> 4.8%
    assert facts["investor_equity_pct"] == 4.8

    # 6. Facts block output
    block = res["facts_block"]
    assert "Starter: $29" in block
    assert "Professional: $79" in block
    assert "Enterprise: $199" in block
    assert "Target Capital Raise: $150,000" in block

