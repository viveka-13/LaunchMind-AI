import pytest
from agent.canonical_facts import build_canonical_facts
from agent.consistency_validator import validate_plan_consistency

def test_consistency_validator_detects_all_issues():
    """Verify that inconsistencies in price, funding ask, stale dates, and arithmetic are caught."""
    base_state = {
        "idea": "AgroMind AI",
        "pricing_tiers": {
            "tiers": [
                {"name": "Starter", "price": 29.0, "billing": "monthly"},
                {"name": "Professional", "price": 79.0, "billing": "monthly"},
                {"name": "Enterprise", "price": 199.0, "billing": "monthly"},
            ]
        },
        "financial_projection": {"monthly_burn_rate": 20000},
        "cap_table": {"target_raise": 150000, "pre_money_valuation": 3000000},
        "market_sizing": {"tam": {"value": "$10 B"}, "sam": {"value": "$2 B"}, "som": {"value": "$100 M"}},
    }
    canon = build_canonical_facts(base_state)

    # Inconsistent state matching observed defects
    bad_state = {
        **base_state,
        "revenue_model": "We offer Tier A at $30, Tier B at $80, and Tier C at $200. At 5,000 users yields $1.8 M / month.",
        "pitch_deck_outline": "Slide 10: Ask for $2 M Series A funding to scale across India.",
        "roadmap": "Phase 1: Foundation (Q1 2024). Phase 2: Launch (Q2 2024).",
        "market_gap": "Targeting the $150 M SO opportunity.",
    }

    is_valid, issues = validate_plan_consistency(bad_state, canon)
    assert not is_valid
    assert len(issues) >= 4

    issue_text = " ".join(issues).lower()
    assert "pricing mismatch" in issue_text or "$30" in issue_text
    assert "funding ask mismatch" in issue_text or "$2m" in issue_text
    assert "stale milestone date" in issue_text or "2024" in issue_text
    assert "revenue math error" in issue_text or "typo" in issue_text


def test_consistency_validator_passes_consistent_plan():
    """Verify that a plan strictly matching canonical facts passes with 0 issues."""
    base_state = {
        "idea": "AgroMind AI",
        "pricing_tiers": {
            "tiers": [
                {"name": "Starter", "price": 29.0, "billing": "monthly"},
                {"name": "Professional", "price": 79.0, "billing": "monthly"},
                {"name": "Enterprise", "price": 199.0, "billing": "monthly"},
            ]
        },
        "financial_projection": {"monthly_burn_rate": 20000},
        "cap_table": {"target_raise": 150000, "pre_money_valuation": 3000000},
        "market_sizing": {"tam": {"value": "$10 B"}, "sam": {"value": "$2 B"}, "som": {"value": "$100 M"}},
    }
    canon = build_canonical_facts(base_state)

    clean_state = {
        **base_state,
        "revenue_model": "We offer Starter at $29/mo, Professional at $79/mo, and Enterprise at $199/mo. At 5,000 users yields $305,000/month.",
        "pitch_deck_outline": "Slide 10: Seeking $150,000 seed raise at $3M pre-money valuation.",
        "roadmap": "Phase 1: Foundation (Q1 2027). Phase 2: Scale (Q3 2027).",
        "market_gap": "Targeting the $100 M SOM underserved smallholder segment.",
    }

    is_valid, issues = validate_plan_consistency(clean_state, canon)
    assert is_valid
    assert len(issues) == 0

