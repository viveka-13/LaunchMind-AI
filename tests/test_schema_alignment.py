"""
tests/test_schema_alignment.py
Verifies that LLM prompt key names match Pydantic model fields,
required content fields enforce minimum counts and reject empty defaults,
and plan_schema output contracts reject empty / incomplete node outputs.
"""
import pytest
from pydantic import ValidationError

from agent.models_pydantic import (
    CompetitorSwotModel,
    CompetitorItem,
    SWOTAnalysis,
    MarketMetric,
    MarketSizingModel,
    PricingModel,
    PricingTier,
    FinancialProjectionModel,
    ResearchBriefModel,
    CapTableModel,
    CritiqueModel,
    TaskDecompositionModel,
)
from agent.plan_schema import validate_node_output


# ─────────────────────────────────────────────
# 1. CompetitorSwotModel — aliases, counts, and non-empty validation
# ─────────────────────────────────────────────

class TestCompetitorSwotModel:
    """Verify prompt keys (aliases), canonical keys, and >=3 requirements."""

    PROMPT_STYLE_RESPONSE = {
        "competitor_matrix": [
            {
                "name": "Life360",
                "strength": "Established family tracking base with 50M+ users",
                "weakness": "Limited to family circles, no lone-commuter emergency features",
                "price_point": "Freemium, $14.99/mo premium",
                "market_position": "Incumbent leader",
                "opportunity": "Beat with proactive AI harassment detection",
            },
            {
                "name": "Noonlight",
                "strength": "Direct 911 dispatch integration",
                "weakness": "Requires manual button trigger in danger",
                "price_point": "$4.99/mo subscription",
                "market_position": "Emergency dispatch app",
                "opportunity": "Beat with automated hands-free distress detection",
            },
            {
                "name": "bSafe",
                "strength": "Voice alarm and SOS siren capabilities",
                "weakness": "High battery drain and frequent false alarms",
                "price_point": "Free basic tier, $2.99/mo premium",
                "market_position": "Niche safety app",
                "opportunity": "Superior AI filtering to eliminate false alarms",
            },
        ],
        "swot": {
            "strengths": [
                "Real-time audio threat analysis",
                "Zero-touch automated SOS triggers",
                "Privacy-preserving local sensor processing",
            ],
            "weaknesses": [
                "Early stage brand recognition",
                "Requires background microphone and location permissions",
                "High initial compute cost for on-device neural model",
            ],
            "opportunities": [
                "Rising enterprise demand for female workforce commuter safety",
                "Government mandates and smart city transit partnerships",
                "B2B campus security and ride-hailing API integrations",
            ],
            "threats": [
                "OS-level background task execution restrictions (iOS/Android)",
                "Big tech platforms embedding native emergency tools",
                "User privacy concerns regarding persistent acoustic monitoring",
            ],
        },
    }

    CANONICAL_STYLE_RESPONSE = {
        "competitors": [
            {"name": "Comp1", "strengths": "Strong brand", "weaknesses": "Slow product iteration", "pricing": "High"},
            {"name": "Comp2", "strengths": "Low pricing", "weaknesses": "Poor customer support", "pricing": "Low"},
            {"name": "Comp3", "strengths": "Great UI", "weaknesses": "Missing enterprise features", "pricing": "Medium"},
        ],
        "swot_analysis": {
            "strengths": ["S1", "S2", "S3"],
            "weaknesses": ["W1", "W2", "W3"],
            "opportunities": ["O1", "O2", "O3"],
            "threats": ["T1", "T2", "T3"],
        },
    }

    def test_prompt_keys_accepted(self):
        """Prompt-style keys (competitor_matrix, swot, strength singular) must parse correctly."""
        model = CompetitorSwotModel.model_validate(self.PROMPT_STYLE_RESPONSE)
        assert len(model.competitors) == 3
        assert model.competitors[0].name == "Life360"
        assert model.competitors[0].strengths == "Established family tracking base with 50M+ users"
        assert model.competitors[0].weaknesses == "Limited to family circles, no lone-commuter emergency features"
        assert len(model.swot_analysis.strengths) == 3
        assert len(model.swot_analysis.threats) == 3

    def test_canonical_keys_accepted(self):
        """Canonical keys (competitors, swot_analysis, strengths plural) must also parse."""
        model = CompetitorSwotModel.model_validate(self.CANONICAL_STYLE_RESPONSE)
        assert len(model.competitors) == 3
        assert model.competitors[0].name == "Comp1"
        assert len(model.swot_analysis.strengths) == 3

    def test_empty_response_rejected(self):
        """Required content fields must NOT default to empty — empty dict must raise ValidationError."""
        with pytest.raises(ValidationError):
            CompetitorSwotModel.model_validate({})

    def test_fewer_than_3_competitors_rejected(self):
        """Competitors list with fewer than 3 items must fail validation."""
        bad_data = {
            "competitors": [{"name": "Comp1", "strengths": "S", "weaknesses": "W"}],
            "swot_analysis": {
                "strengths": ["S1", "S2", "S3"],
                "weaknesses": ["W1", "W2", "W3"],
                "opportunities": ["O1", "O2", "O3"],
                "threats": ["T1", "T2", "T3"],
            },
        }
        with pytest.raises(ValidationError) as exc:
            CompetitorSwotModel.model_validate(bad_data)
        assert "at least 3 competitors" in str(exc.value)

    def test_fewer_than_3_swot_items_rejected(self):
        """SWOT quadrant with fewer than 3 items must fail validation."""
        bad_data = {
            "competitors": [
                {"name": "C1", "strengths": "S", "weaknesses": "W"},
                {"name": "C2", "strengths": "S", "weaknesses": "W"},
                {"name": "C3", "strengths": "S", "weaknesses": "W"},
            ],
            "swot_analysis": {
                "strengths": ["S1"],  # only 1
                "weaknesses": ["W1", "W2", "W3"],
                "opportunities": ["O1", "O2", "O3"],
                "threats": ["T1", "T2", "T3"],
            },
        }
        with pytest.raises(ValidationError) as exc:
            CompetitorSwotModel.model_validate(bad_data)
        assert "at least 3 items" in str(exc.value)


# ─────────────────────────────────────────────
# 2. MarketSizingModel — Structured metric & null handling
# ─────────────────────────────────────────────

class TestMarketSizingModel:
    def test_structured_metric_with_estimate_basis(self):
        """Estimate with calculation chain must parse into MarketMetric."""
        data = {
            "tam": {
                "value": "$5.2B",
                "basis": "estimate",
                "assumptions": "Calculation: 65M women commuters in target metro areas * $80/yr service fee",
                "confidence": "medium",
                "reason_if_null": None,
            },
            "sam": {
                "value": "$1.2B",
                "basis": "estimate",
                "assumptions": "Calculation: 15M smartphone users in top 10 cities * $80/yr",
                "confidence": "medium",
                "reason_if_null": None,
            },
            "som": {
                "value": "$36M",
                "basis": "estimate",
                "assumptions": "Calculation: 3% adoption of SAM in 3 years",
                "confidence": "medium",
                "reason_if_null": None,
            },
            "methodology": "Top-down demographic projection cross-referenced with smartphone commuter surveys.",
            "assumptions": ["$80/yr average annual subscription", "3% capture of addressable segment"],
        }
        model = MarketSizingModel.model_validate(data)
        assert model.tam.value == "$5.2B"
        assert model.tam.basis == "estimate"
        assert "Calculation" in model.tam.assumptions
        assert model.som.value == "$36M"

    def test_null_metric_with_reason_accepted(self):
        """When research lacks data, null with reason is accepted."""
        data = {
            "tam": {
                "value": None,
                "basis": "unavailable",
                "assumptions": "",
                "confidence": "low",
                "reason_if_null": "Research data lacked global market sizing benchmarks for this niche",
            },
            "sam": None,
            "som": None,
            "methodology": "No quantitative sizing data found in research sources.",
            "assumptions": ["Assumption 1", "Assumption 2"],
        }
        model = MarketSizingModel.model_validate(data)
        assert model.tam.value is None
        assert model.tam.basis == "unavailable"
        assert "lacked global market sizing" in model.tam.reason_if_null
        assert model.sam is None

    def test_string_metric_backwards_compatible(self):
        """Legacy string values must parse cleanly into MarketMetric."""
        data = {
            "tam": "$10B (Global market)",
            "sam": "$2B (US market)",
            "som": "$50M (5% capture)",
            "methodology": "Top-down market calculation from industry reports.",
            "assumptions": ["ARPU $100/yr", "10% target share"],
        }
        model = MarketSizingModel.model_validate(data)
        assert model.tam.value == "$10B (Global market)"
        assert model.tam.basis == "estimate"


# ─────────────────────────────────────────────
# 3. PricingModel — Exactly 3 tiers with non-empty features
# ─────────────────────────────────────────────

class TestPricingModel:
    PROMPT_RESPONSE = {
        "tiers": [
            {
                "name": "Basic",
                "monthly_price": 9.99,
                "target_segment": "Individual users",
                "features": ["Personal SOS trigger", "3 trusted contacts", "Live GPS sharing"],
                "adoption_pct": 0.05,
                "monthly_growth_rate": 0.08,
                "churn_rate": 0.03,
            },
            {
                "name": "Pro",
                "monthly_price": 24.99,
                "target_segment": "Frequent commuters",
                "features": ["AI acoustic threat detection", "Unlimited contacts", "24/7 incident response dispatch"],
                "adoption_pct": 0.03,
                "monthly_growth_rate": 0.06,
                "churn_rate": 0.02,
            },
            {
                "name": "Family / Enterprise",
                "monthly_price": 79.99,
                "target_segment": "Corporate employers & families",
                "features": ["Multi-user dashboard", "Enterprise duty of care reporting", "Dedicated dispatcher hotline"],
                "adoption_pct": 0.01,
                "monthly_growth_rate": 0.04,
                "churn_rate": 0.01,
            },
        ],
        "total_addressable_customers": 50000,
        "currency": "USD",
    }

    def test_valid_3_tiers_with_features(self):
        model = PricingModel.model_validate(self.PROMPT_RESPONSE)
        assert len(model.tiers) == 3
        for tier in model.tiers:
            assert len(tier.features) >= 1
            assert tier.monthly_price > 0

    def test_less_than_3_tiers_fails(self):
        bad_data = {
            "tiers": [
                {"name": "Basic", "monthly_price": 10, "features": ["F1"]},
                {"name": "Pro", "monthly_price": 20, "features": ["F2"]},
            ],
        }
        with pytest.raises(ValidationError) as exc:
            PricingModel.model_validate(bad_data)
        assert "exactly 3 tiers" in str(exc.value)

    def test_tier_with_empty_features_fails(self):
        bad_data = {
            "tiers": [
                {"name": "Basic", "monthly_price": 10, "features": []},  # empty features
                {"name": "Pro", "monthly_price": 20, "features": ["F1"]},
                {"name": "Enterprise", "monthly_price": 30, "features": ["F2"]},
            ],
        }
        with pytest.raises(ValidationError) as exc:
            PricingModel.model_validate(bad_data)
        assert "features" in str(exc.value)


# ─────────────────────────────────────────────
# 4. Plan Schema Contract Validation
# ─────────────────────────────────────────────

class TestPlanSchemaContracts:
    def test_competitor_swot_contract_validation(self):
        # Valid output passes
        valid_out = {
            "competitor_swot": json_dump({
                "competitors": [
                    {"name": "C1", "strengths": "S", "weaknesses": "W"},
                    {"name": "C2", "strengths": "S", "weaknesses": "W"},
                    {"name": "C3", "strengths": "S", "weaknesses": "W"},
                ],
                "swot_analysis": {
                    "strengths": ["S1", "S2", "S3"],
                    "weaknesses": ["W1", "W2", "W3"],
                    "opportunities": ["O1", "O2", "O3"],
                    "threats": ["T1", "T2", "T3"],
                },
            })
        }
        is_valid, err = validate_node_output("competitor_swot", valid_out)
        assert is_valid, err

        # Incomplete SWOT fails
        bad_swot = {
            "competitor_swot": json_dump({
                "competitors": [{"name": "C1", "strengths": "S", "weaknesses": "W"}],
                "swot_analysis": {"strengths": []},
            })
        }
        is_valid, err = validate_node_output("competitor_swot", bad_swot)
        assert not is_valid
        assert ">= 3" in err

    def test_pricing_model_contract_validation(self):
        # Valid 3 tiers with features passes
        valid_out = {
            "pricing_model": json_dump({
                "tiers": [
                    {"name": "T1", "monthly_price": 10, "features": ["F1"]},
                    {"name": "T2", "monthly_price": 20, "features": ["F2"]},
                    {"name": "T3", "monthly_price": 30, "features": ["F3"]},
                ]
            })
        }
        is_valid, err = validate_node_output("pricing_model", valid_out)
        assert is_valid, err

        # Missing features fails
        bad_pricing = {
            "pricing_model": json_dump({
                "tiers": [
                    {"name": "T1", "monthly_price": 10, "features": []},
                    {"name": "T2", "monthly_price": 20, "features": ["F2"]},
                    {"name": "T3", "monthly_price": 30, "features": ["F3"]},
                ]
            })
        }
        is_valid, err = validate_node_output("pricing_model", bad_pricing)
        assert not is_valid
        assert "non-empty features" in err

    def test_roadmap_contract_validation(self):
        # Valid roadmap with 4 phases passes
        valid_roadmap = {
            "implementation_roadmap": (
                "Phase 1 (Months 1-3): MVP development and testing.\n"
                "Phase 2 (Months 4-6): Beta launch with 500 pilots.\n"
                "Phase 3 (Months 7-9): Commercial rollout and marketing.\n"
                "Phase 4 (Months 10-12): Enterprise scaling and expansion."
            )
        }
        is_valid, err = validate_node_output("generate_roadmap", valid_roadmap)
        assert is_valid, err

        # Roadmap missing Phase 4 fails
        bad_roadmap = {
            "implementation_roadmap": (
                "Phase 1: MVP.\nPhase 2: Beta.\nPhase 3: Launch."
            )
        }
        is_valid, err = validate_node_output("generate_roadmap", bad_roadmap)
        assert not is_valid
        assert "Phase 4" in err


def json_dump(d):
    import json
    return json.dumps(d)
