# agent/models_pydantic.py
# Pydantic models for structured node output validation

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TaskDecompositionModel(BaseModel):
    tasks: List[str] = Field(default_factory=list)


class ResearchBriefModel(BaseModel):
    executive_summary: str = ""
    key_findings: List[str] = Field(default_factory=list)
    market_sentiment: str = ""


class CompetitorItem(BaseModel):
    name: str = ""
    strengths: str = ""
    weaknesses: str = ""
    pricing: Optional[str] = ""
    market_position: Optional[str] = ""


class SWOTAnalysis(BaseModel):
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    threats: List[str] = Field(default_factory=list)


class CompetitorSwotModel(BaseModel):
    competitors: List[CompetitorItem] = Field(default_factory=list)
    swot_analysis: SWOTAnalysis = Field(default_factory=SWOTAnalysis)


class MarketSizingModel(BaseModel):
    tam: str = ""
    sam: str = ""
    som: str = ""
    methodology: str = ""
    growth_rate: Optional[str] = ""


class PricingTier(BaseModel):
    name: str
    monthly_price: float
    target_segment: Optional[str] = ""
    features: Optional[List[str]] = Field(default_factory=list)


class PricingModel(BaseModel):
    tiers: List[PricingTier] = Field(default_factory=list)
    currency: str = "USD"
    total_addressable_customers: Optional[int] = None


class FinancialProjectionModel(BaseModel):
    cogs_pct: Optional[float] = 0.2
    cac: Optional[float] = 100.0
    operating_expenses: Optional[Dict[str, float]] = Field(default_factory=dict)
    expense_growth_rate: Optional[float] = 0.05
    revenue_assumptions: Optional[str] = ""
    initial_cash: Optional[float] = 100000.0


class CapTableModel(BaseModel):
    funding_amount: Optional[float] = 500000.0
    pre_money_valuation: Optional[float] = 2500000.0
    option_pool_pct: Optional[float] = 0.1
    use_of_funds: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class ActionItem(BaseModel):
    problem: str = ""
    solution: str = ""
    expected_impact: str = ""


class ActionPlan(BaseModel):
    priority_1: List[ActionItem] = Field(default_factory=list)
    priority_2: Optional[List[ActionItem]] = Field(default_factory=list)
    priority_3: Optional[List[ActionItem]] = Field(default_factory=list)


class Verdict(BaseModel):
    verdict: str = "Investable"
    why: str = ""


class CritiqueModel(BaseModel):
    scores: Dict[str, Any] = Field(default_factory=dict)
    action_plan: ActionPlan = Field(default_factory=ActionPlan)
    final_verdict: Verdict = Field(default_factory=Verdict)


class InvestorItem(BaseModel):
    investor_name: str
    match_percentage: int
    investment_stage: str
    sector_focus: str
    why_this_investor_matches: str
    expected_cheque_size: Optional[str] = ""
    portfolio_examples: Optional[str] = ""


class InvestorMatchModel(BaseModel):
    matched_investors: List[InvestorItem] = Field(default_factory=list)


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
    components: List[ArchitectureComponent] = Field(default_factory=list)


class ArchitectureModel(BaseModel):
    layers: List[ArchitectureLayer] = Field(default_factory=list)
