# agent/models_pydantic.py
# Pydantic models for structured node output validation

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class TaskDecompositionModel(BaseModel):
    tasks: List[str]

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, v):
        if not v or len(v) < 1:
            raise ValueError("Task decomposition must contain at least 1 task")
        return v


class ResearchBriefModel(BaseModel):
    executive_summary: str
    key_findings: List[str]
    market_sentiment: str
    data_gaps: Optional[List[str]] = Field(default_factory=list)

    @field_validator("executive_summary")
    @classmethod
    def validate_summary(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError("Executive summary must be non-empty (at least 20 characters)")
        return v

    @field_validator("key_findings")
    @classmethod
    def validate_findings(cls, v):
        if not v or len(v) < 3:
            raise ValueError(f"Research brief must have at least 3 key findings, got {len(v) if v else 0}")
        return v


class CompetitorItem(BaseModel):
    """Accepts both prompt keys (singular) and canonical keys (plural) via aliases."""
    model_config = ConfigDict(populate_by_name=True)

    name: str
    strengths: str = Field(alias="strength")
    weaknesses: str = Field(alias="weakness")
    pricing: Optional[str] = Field(default="N/A", alias="price_point")
    market_position: Optional[str] = "Competitor"
    opportunity: Optional[str] = ""

    @field_validator("name", "strengths", "weaknesses")
    @classmethod
    def check_non_empty(cls, v, info):
        if not v or not str(v).strip():
            raise ValueError(f"Competitor field '{info.field_name}' must not be empty")
        return v


class SWOTAnalysis(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    opportunities: List[str]
    threats: List[str]

    @field_validator("strengths", "weaknesses", "opportunities", "threats")
    @classmethod
    def validate_quadrant(cls, v, info):
        if not v or len(v) < 3:
            raise ValueError(f"SWOT quadrant '{info.field_name}' must have at least 3 items, got {len(v) if v else 0}")
        return v


class CompetitorSwotModel(BaseModel):
    """Accepts both prompt keys (competitor_matrix/swot) and canonical keys (competitors/swot_analysis)."""
    model_config = ConfigDict(populate_by_name=True)

    competitors: List[CompetitorItem] = Field(alias="competitor_matrix")
    swot_analysis: SWOTAnalysis = Field(alias="swot")

    @field_validator("competitors")
    @classmethod
    def validate_competitors(cls, v):
        if not v or len(v) < 3:
            raise ValueError(f"Competitor analysis must have at least 3 competitors, got {len(v) if v else 0}")
        return v


class MarketMetric(BaseModel):
    """Structured market metric with basis, assumptions, confidence, and null reason."""
    model_config = ConfigDict(populate_by_name=True)

    value: Optional[str] = None
    basis: str = Field(default="estimate")  # "sourced" | "estimate" | "unavailable"
    assumptions: Optional[str] = ""
    confidence: Optional[str] = "medium"  # "high" | "medium" | "low"
    reason_if_null: Optional[str] = None


class MarketSizingModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tam: Optional[MarketMetric] = None
    sam: Optional[MarketMetric] = None
    som: Optional[MarketMetric] = None
    methodology: str
    growth_rate: Optional[str] = ""
    assumptions: List[str]

    @field_validator("tam", "sam", "som", mode="before")
    @classmethod
    def parse_metric(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            if v.strip().lower() in ("null", "none", "n/a", ""):
                return None
            return MarketMetric(value=v.strip(), basis="estimate")
        if isinstance(v, dict):
            val = v.get("value")
            if val is None or (isinstance(val, str) and val.strip().lower() in ("null", "none", "n/a", "")):
                return MarketMetric(
                    value=None,
                    basis=v.get("basis", "unavailable"),
                    assumptions=v.get("assumptions", ""),
                    confidence=v.get("confidence", "low"),
                    reason_if_null=v.get("reason_if_null") or v.get("reason") or "No justifiable market data found in research"
                )
            return MarketMetric(**v)
        return v

    @field_validator("methodology")
    @classmethod
    def validate_methodology(cls, v):
        if not v or len(v.strip()) < 20:
            raise ValueError("Market sizing methodology must be non-empty (at least 20 characters)")
        return v

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, v):
        if not v or len(v) < 2:
            raise ValueError(f"Market sizing must have at least 2 assumptions, got {len(v) if v else 0}")
        return v


class PricingTier(BaseModel):
    name: str
    monthly_price: float
    target_segment: Optional[str] = ""
    features: List[str]  # Required! Non-empty list
    adoption_pct: Optional[float] = None
    monthly_growth_rate: Optional[float] = None
    churn_rate: Optional[float] = None

    @field_validator("features")
    @classmethod
    def validate_features(cls, v):
        if not v or len(v) < 1:
            raise ValueError("Pricing tier 'features' must be a non-empty list of features")
        return v


class PricingModel(BaseModel):
    tiers: List[PricingTier]
    currency: str = "USD"
    total_addressable_customers: Optional[int] = None

    @field_validator("tiers")
    @classmethod
    def validate_tiers(cls, v):
        if not v or len(v) != 3:
            raise ValueError(f"Pricing model must have exactly 3 tiers, got {len(v) if v else 0}")
        return v


class HireItem(BaseModel):
    role: str
    monthly_salary: float
    start_month: int = 1


class FinancialProjectionModel(BaseModel):
    cogs_pct: float
    cac: float
    operating_expenses: Dict[str, float]
    expense_growth_rate: float
    revenue_assumptions: str
    initial_cash: float
    hires: List[HireItem] = Field(default_factory=list)
    currency: Optional[str] = "USD"


class CapTableModel(BaseModel):
    funding_amount: float
    pre_money_valuation: float
    option_pool_pct: float
    use_of_funds: List[Dict[str, Any]]


class ActionItem(BaseModel):
    problem: str
    solution: str
    expected_impact: str


class ActionPlan(BaseModel):
    priority_1: List[ActionItem]
    priority_2: Optional[List[ActionItem]] = Field(default_factory=list)
    priority_3: Optional[List[ActionItem]] = Field(default_factory=list)


class Verdict(BaseModel):
    verdict: str = "Investable"
    why: str = ""


class CritiqueModel(BaseModel):
    scores: Dict[str, Any]
    action_plan: ActionPlan
    final_verdict: Verdict


class InvestorItem(BaseModel):
    investor_name: str
    match_percentage: int
    investment_stage: str
    sector_focus: str
    why_this_investor_matches: str
    expected_cheque_size: Optional[str] = ""
    portfolio_examples: Optional[str] = ""


class InvestorMatchModel(BaseModel):
    matched_investors: List[InvestorItem]


class BrandColors(BaseModel):
    primary: str = "#6366f1"
    secondary: str = "#06b6d4"
    accent: str = "#f59e0b"
    background: str = "#0f172a"


class BrandTypography(BaseModel):
    heading_font: str = "'Inter', sans-serif"
    body_font: str = "'Roboto', sans-serif"


class BrandKitModel(BaseModel):
    brand_name: str
    tagline: str
    colors: BrandColors = Field(default_factory=BrandColors)
    typography: BrandTypography = Field(default_factory=BrandTypography)
    psychology: Optional[str] = ""
    brand_strategy: Optional[str] = ""
    logo_meaning: Optional[str] = ""
    customer_personas: Optional[List[str]] = Field(default_factory=list)
    marketing_strategy: Optional[str] = ""


class ArchitectureComponent(BaseModel):
    name: str
    tech: str


class ArchitectureLayer(BaseModel):
    name: str
    color: str
    components: List[ArchitectureComponent]


class ArchitectureModel(BaseModel):
    layers: List[ArchitectureLayer]
