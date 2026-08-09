"""
agent/financial_prompts.py
Prompt templates for the 3 AI-powered financial modeling nodes.
"""

PRICING_MODEL_PROMPT = """You are a SaaS pricing strategist.

Startup Idea: {idea}
Revenue Model: {revenue_model}
Market Size Data: {market_sizing}
Competitor Info: {competitor_analysis}

Design a tiered pricing model for this startup.

Return ONLY valid JSON in this EXACT format:
{{
  "tiers": [
    {{
      "name": "Basic",
      "monthly_price": 29,
      "target_segment": "Small businesses",
      "adoption_pct": 0.05,
      "monthly_growth_rate": 0.08,
      "churn_rate": 0.03
    }},
    {{
      "name": "Pro",
      "monthly_price": 79,
      "target_segment": "Medium businesses",
      "adoption_pct": 0.03,
      "monthly_growth_rate": 0.06,
      "churn_rate": 0.02
    }},
    {{
      "name": "Enterprise",
      "monthly_price": 199,
      "target_segment": "Large companies",
      "adoption_pct": 0.01,
      "monthly_growth_rate": 0.04,
      "churn_rate": 0.01
    }}
  ],
  "total_addressable_customers": 50000,
  "currency": "USD"
}}

Rules:
- Generate 2-3 tiers with realistic prices for this specific market.
- adoption_pct is the percentage of total_addressable_customers that sign up in month 1.
- monthly_growth_rate is the month-over-month customer acquisition growth rate (decimal, e.g. 0.08 = 8%).
- churn_rate is the monthly customer churn rate (decimal, e.g. 0.02 = 2%).
- total_addressable_customers must be a realistic number for this startup's first-year target market.
- All numbers must be plain numbers, NOT strings.
"""

FINANCIAL_PROJECTION_PROMPT = """You are a startup CFO.

Startup Idea: {idea}
Revenue Model: {revenue_model}
Core Features: {core_features}
Market Size: {market_sizing}

Create a 3-year financial projection framework.

Return ONLY valid JSON in this EXACT format:
{{
  "cogs_pct": 0.25,
  "cac": 150,
  "operating_expenses": {{
    "cloud_hosting": 500,
    "marketing": 2000,
    "tools_software": 300,
    "office_rent": 0,
    "legal_accounting": 500,
    "miscellaneous": 300
  }},
  "expense_growth_rate": 0.05,
  "revenue_assumptions": "Describe the core revenue generation assumptions (e.g. CAC recovery in 4 months, etc).",
  "hires": [
    {{
      "role": "Backend Developer",
      "monthly_salary": 8000,
      "start_month": 1
    }},
    {{
      "role": "Marketing Manager",
      "monthly_salary": 5000,
      "start_month": 4
    }}
  ],
  "initial_cash": 150000,
  "currency": "USD"
}}

Rules:
- cogs_pct is cost of goods sold as a decimal fraction of revenue.
- cac is the Customer Acquisition Cost (how much it costs to acquire 1 new customer).
- operating_expenses are MONTHLY fixed/variable costs in the currency.
- expense_growth_rate is how much operating expenses grow per quarter (decimal).
- revenue_assumptions: 1-2 sentences stating the methodology behind revenue scale.
- hires: list 3-5 key hires with monthly salary and the month they start (1-36).
- initial_cash is the starting cash before any revenue.
- All numbers must be plain numbers, NOT strings.
"""

CAP_TABLE_PROMPT = """You are a venture capital advisor.

Startup Idea: {idea}
Revenue Model: {revenue_model}
Market Size: {market_sizing}
Financial Projection Summary: Initial cash: {initial_cash}, Monthly burn estimate: {monthly_burn}

Design a seed/pre-seed funding strategy.

Return ONLY valid JSON in this EXACT format:
{{
  "funding_amount": 500000,
  "pre_money_valuation": 2000000,
  "option_pool_pct": 0.10,
  "use_of_funds": [
    {{
      "category": "Engineering & Product",
      "allocation_pct": 0.40
    }},
    {{
      "category": "Sales & Marketing",
      "allocation_pct": 0.25
    }},
    {{
      "category": "Operations",
      "allocation_pct": 0.15
    }},
    {{
      "category": "Cash Reserve",
      "allocation_pct": 0.20
    }}
  ],
  "currency": "USD"
}}

Rules:
- funding_amount should give 12-18 months of runway based on the burn rate.
- pre_money_valuation should be realistic for this stage.
- option_pool_pct is the employee option pool as a decimal (e.g. 0.10 = 10%).
- use_of_funds allocation_pct values MUST sum to exactly 1.0.
- All numbers must be plain numbers, NOT strings.
"""
