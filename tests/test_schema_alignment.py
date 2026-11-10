"""
tests/test_schema_alignment.py
Verifies that LLM prompt key names match Pydantic model fields.
If a prompt drifts, this test fails BEFORE users see empty sections.
"""
import json
import pytest
from pydantic import ValidationError

from agent.models_pydantic import (
    CompetitorSwotModel,
    CompetitorItem,
    SWOTAnalysis,
    MarketSizingModel,
    PricingModel,
    PricingTier,
    FinancialProjectionModel,
    ResearchBriefModel,
    CapTableModel,
    CritiqueModel,
    TaskDecompositionModel,
)


# ─────────────────────────────────────────────
# 1. CompetitorSwotModel — prompt returns competitor_matrix/swot
# ─────────────────────────────────────────────

class TestCompetitorSwotModel:
    """Verify both prompt keys (alias) and canonical keys are accepted."""

    PROMPT_STYLE_RESPONSE = {
        "competitor_matrix": [
            {
                "name": "Life360",
                "strength": "Established user base with 50M+ users",
                "weakness": "Limited to family safety, not personal safety",
                "price_point": "Freemium, $14.99/mo premium",
                "market_position": "Market leader in family tracking",
                "opportunity": "They don't cover personal threat detection",
            }
        ],
        "swot": {
            "strengths": ["AI-powered real-time threat detection", "Multi-modal sensor fusion"],
            "weaknesses": ["No brand recognition", "Dependency on smartphone sensors"],
            "opportunities": ["Growing women's safety market", "Government initiatives"],
            "threats": ["Privacy regulation risks", "Established players pivoting"],
        },
    }

    CANONICAL_STYLE_RESPONSE = {
        "competitors": [
            {
                "name": "Life360",
                "strengths": "Established user base",
                "weaknesses": "Limited scope",
                "pricing": "Freemium",
                "market_position": "Market leader",
            }
        ],
        "swot_analysis": {
            "strengths": ["AI-powered detection"],
            "weaknesses": ["No brand"],
            "opportunities": ["Growing market"],
            "threats": ["Privacy risks"],
        },
    }

    def test_prompt_keys_accepted(self):
        """Prompt-style keys (competitor_matrix, swot, strength singular) must parse correctly."""
        model = CompetitorSwotModel.model_validate(self.PROMPT_STYLE_RESPONSE)
        assert len(model.competitors) == 1
        assert model.competitors[0].name == "Life360"
        assert model.competitors[0].strengths == "Established user base with 50M+ users"
        assert model.competitors[0].weaknesses == "Limited to family safety, not personal safety"
        assert model.competitors[0].pricing == "Freemium, $14.99/mo premium"
        assert model.competitors[0].opportunity == "They don't cover personal threat detection"
        assert len(model.swot_analysis.strengths) == 2
        assert len(model.swot_analysis.threats) == 2

    def test_canonical_keys_accepted(self):
        """Canonical keys (competitors, swot_analysis, strengths plural) must also parse."""
        model = CompetitorSwotModel.model_validate(self.CANONICAL_STYLE_RESPONSE)
        assert len(model.competitors) == 1
        assert model.competitors[0].name == "Life360"
        assert len(model.swot_analysis.strengths) == 1

    def test_model_dump_uses_canonical_keys(self):
        """After validation, model_dump must use canonical keys (not aliases)."""
        model = CompetitorSwotModel.model_validate(self.PROMPT_STYLE_RESPONSE)
        d = model.model_dump(by_alias=False)
        assert "competitors" in d
        assert "swot_analysis" in d
        assert "competitor_matrix" not in d
        assert "swot" not in d

    def test_empty_response_has_empty_lists(self):
        """An empty dict should produce empty lists, not crash."""
        model = CompetitorSwotModel.model_validate({})
        assert model.competitors == []
        assert model.swot_analysis.strengths == []


# ─────────────────────────────────────────────
# 2. MarketSizingModel — null handling
# ─────────────────────────────────────────────

class TestMarketSizingModel:
    def test_null_tam_sam_som_accepted(self):
        """LLM can return null for TAM/SAM/SOM when data is thin."""
        data = {
            "tam": None,
            "sam": None,
            "som": None,
            "methodology": "Insufficient data for estimation.",
            "assumptions": [],
        }
        model = MarketSizingModel.model_validate(data)
        assert model.tam is None
        assert model.sam is None
        assert model.methodology == "Insufficient data for estimation."

    def test_string_values_accepted(self):
        """Normal string values work."""
        data = {
            "tam": "$10B (Global market)",
            "sam": "$2B (US market)",
            "som": "$50M (5% capture)",
            "methodology": "Top-down from industry reports",
            "assumptions": ["ARPU $100/yr"],
            "growth_rate": "15% CAGR",
        }
        model = MarketSizingModel.model_validate(data)
        assert model.tam == "$10B (Global market)"
        assert model.growth_rate == "15% CAGR"
        assert len(model.assumptions) == 1


# ─────────────────────────────────────────────
# 3. PricingTier — must accept financial fields from prompt
# ─────────────────────────────────────────────

class TestPricingModel:
    PROMPT_RESPONSE = {
        "tiers": [
            {
                "name": "Basic",
                "monthly_price": 29,
                "target_segment": "Small businesses",
                "adoption_pct": 0.05,
                "monthly_growth_rate": 0.08,
                "churn_rate": 0.03,
            },
            {
                "name": "Pro",
                "monthly_price": 79,
                "target_segment": "Medium businesses",
                "adoption_pct": 0.03,
                "monthly_growth_rate": 0.06,
                "churn_rate": 0.02,
            },
        ],
        "total_addressable_customers": 50000,
        "currency": "USD",
    }

    def test_financial_fields_preserved(self):
        """adoption_pct, monthly_growth_rate, churn_rate must NOT be dropped."""
        model = PricingModel.model_validate(self.PROMPT_RESPONSE)
        assert len(model.tiers) == 2
        assert model.tiers[0].adoption_pct == 0.05
        assert model.tiers[0].monthly_growth_rate == 0.08
        assert model.tiers[0].churn_rate == 0.03
        assert model.total_addressable_customers == 50000

    def test_model_dump_includes_financial_fields(self):
        """After dump, financial fields must be in the dict."""
        model = PricingModel.model_validate(self.PROMPT_RESPONSE)
        d = model.model_dump()
        tier = d["tiers"][0]
        assert tier["adoption_pct"] == 0.05
        assert tier["monthly_growth_rate"] == 0.08
        assert tier["churn_rate"] == 0.03


# ─────────────────────────────────────────────
# 4. FinancialProjectionModel — must accept hires and currency
# ─────────────────────────────────────────────

class TestFinancialProjectionModel:
    def test_hires_and_currency_preserved(self):
        data = {
            "cogs_pct": 0.25,
            "cac": 150,
            "operating_expenses": {"cloud_hosting": 500, "marketing": 2000},
            "expense_growth_rate": 0.05,
            "revenue_assumptions": "CAC recovery in 4 months",
            "initial_cash": 150000,
            "hires": [
                {"role": "Backend Developer", "monthly_salary": 8000, "start_month": 1},
                {"role": "Marketing Manager", "monthly_salary": 5000, "start_month": 4},
            ],
            "currency": "USD",
        }
        model = FinancialProjectionModel.model_validate(data)
        assert len(model.hires) == 2
        assert model.hires[0].role == "Backend Developer"
        assert model.currency == "USD"


# ─────────────────────────────────────────────
# 5. ResearchBriefModel — must accept data_gaps
# ─────────────────────────────────────────────

class TestResearchBriefModel:
    def test_data_gaps_accepted(self):
        data = {
            "executive_summary": "Summary",
            "key_findings": ["Finding 1"],
            "market_sentiment": "Positive",
            "data_gaps": ["No Crunchbase data", "Trends unavailable"],
        }
        model = ResearchBriefModel.model_validate(data)
        assert len(model.data_gaps) == 2


# ─────────────────────────────────────────────
# 6. Generic: every node's prompt-style response must validate non-empty
# ─────────────────────────────────────────────

PROMPT_STYLE_RESPONSES = {
    "competitor_swot": {
        "model_cls": CompetitorSwotModel,
        "response": {
            "competitor_matrix": [
                {"name": "Comp1", "strength": "Strong brand", "weakness": "Slow", "price_point": "High", "market_position": "Leader", "opportunity": "Beat on price"}
            ],
            "swot": {
                "strengths": ["Fast", "Cheap"],
                "weaknesses": ["New"],
                "opportunities": ["Growing market"],
                "threats": ["Regulation"],
            },
        },
        "check_keys": ["competitors", "swot_analysis"],
    },
    "market_sizing": {
        "model_cls": MarketSizingModel,
        "response": {"tam": "$5B", "sam": "$1B", "som": "$50M", "methodology": "Top-down"},
        "check_keys": ["tam", "sam", "som"],
    },
    "pricing_model": {
        "model_cls": PricingModel,
        "response": {
            "tiers": [{"name": "Basic", "monthly_price": 29, "target_segment": "SMB", "adoption_pct": 0.05, "monthly_growth_rate": 0.08, "churn_rate": 0.03}],
            "total_addressable_customers": 10000,
            "currency": "USD",
        },
        "check_keys": ["tiers"],
    },
    "financial_projection": {
        "model_cls": FinancialProjectionModel,
        "response": {
            "cogs_pct": 0.25, "cac": 150,
            "operating_expenses": {"cloud": 500},
            "expense_growth_rate": 0.05,
            "revenue_assumptions": "Revenue from subscriptions",
            "initial_cash": 100000,
            "hires": [{"role": "Dev", "monthly_salary": 8000, "start_month": 1}],
            "currency": "USD",
        },
        "check_keys": ["cogs_pct", "cac", "hires"],
    },
    "decompose": {
        "model_cls": TaskDecompositionModel,
        "response": {"tasks": ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"]},
        "check_keys": ["tasks"],
    },
    "synthesize_research": {
        "model_cls": ResearchBriefModel,
        "response": {"executive_summary": "Brief summary", "key_findings": ["Finding"], "market_sentiment": "Positive"},
        "check_keys": ["executive_summary", "key_findings"],
    },
}


@pytest.mark.parametrize("node_name", list(PROMPT_STYLE_RESPONSES.keys()))
def test_prompt_response_validates_nonempty(node_name):
    """For every node, a realistic LLM response using the prompt's key names must validate to non-empty output."""
    spec = PROMPT_STYLE_RESPONSES[node_name]
    model = spec["model_cls"].model_validate(spec["response"])
    d = model.model_dump(by_alias=False)

    for key in spec["check_keys"]:
        val = d.get(key)
        assert val is not None, f"Node '{node_name}': key '{key}' is None after validation"
        if isinstance(val, (list, dict)):
            assert len(val) > 0, f"Node '{node_name}': key '{key}' is empty after validation"
        elif isinstance(val, str):
            assert len(val.strip()) > 0, f"Node '{node_name}': key '{key}' is empty string after validation"

