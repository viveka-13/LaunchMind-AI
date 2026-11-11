# agent/prompts_research_validation.py
# Additional prompts for advanced research and validation nodes

RESEARCH_SYNTHESIS_PROMPT = """You are a Principal Research Analyst. 
Synthesize the provided research data from multiple sources into a cohesive brief.

Idea: {idea}

Data Sources:
[DuckDuckGo (General Web)]:
{duckduckgo}

[Crunchbase (Funding & Companies)]:
{crunchbase}

[Google Trends (Search Interest)]:
{google_trends}

[Sentiment (Social/Public)]:
{sentiment}

Your output MUST be ONLY valid JSON in this exact format:
{{
  "executive_summary": "High-level summary of the research (max 3 sentences)",
  "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
  "market_sentiment": "Positive/Neutral/Negative with a brief reason",
  "data_gaps": ["List what is missing if any of the sources (like Crunchbase or Trends) returned 'source_unavailable' or had no data"]
}}
"""

MARKET_SIZING_PROMPT = """You are a Startup Financial Modeler.
Calculate the TAM (Total Addressable Market), SAM (Serviceable Available Market), and SOM (Serviceable Obtainable Market) for this startup idea based on the research.

Idea: {startup_idea}

Research Brief:
{research_brief}

RULES FOR MARKET SIZING:
1. For each of TAM, SAM, and SOM, provide an object with:
   - "value": A concise dollar figure with market scope, e.g. "$10B (Global female safety tech)". Set to null if and only if completely unknowable and unjustified.
   - "basis": Must be one of:
       * "sourced" (if explicit market size numbers are provided in the research brief)
       * "estimate" (if derived through a logical calculation chain, e.g. target population * ARPU)
       * "unavailable" (if research contains no data and a realistic estimate cannot be justified)
   - "assumptions": When basis is "estimate", you MUST state the step-by-step calculation chain (e.g. "50M female commuters in Tier 1 cities * $4/month app subscription = $2.4B"). If basis is "sourced", cite the source.
   - "confidence": "high", "medium", or "low".
   - "reason_if_null": If "value" is null, explain specifically why an estimate could not be justified. Otherwise null.
2. If the research brief has no market figures, DO NOT invent wild numbers without a calculation chain. Provide a bottom-up estimate with a clear calculation chain and mark "basis": "estimate", OR return "value": null with a clear reason in "reason_if_null".
3. "methodology": Detailed step-by-step calculation explanation (at least 20 words).
4. "assumptions": List at least 2 core assumptions.

Your output MUST be ONLY valid JSON in this exact format:
{{
  "tam": {{
    "value": "$10B",
    "basis": "sourced",
    "assumptions": "Industry report from Research Brief",
    "confidence": "high",
    "reason_if_null": null
  }},
  "sam": {{
    "value": "$2B",
    "basis": "estimate",
    "assumptions": "Calculation: 40M target addressable users in target region * $50/yr",
    "confidence": "medium",
    "reason_if_null": null
  }},
  "som": {{
    "value": "$50M",
    "basis": "estimate",
    "assumptions": "Calculation: 2.5% market share capture of SAM within Years 1-3",
    "confidence": "medium",
    "reason_if_null": null
  }},
  "methodology": "Step-by-step explanation of sizing methodology and data sources used.",
  "assumptions": ["Assumption 1 (e.g. Target market size and adoption rate)", "Assumption 2 (e.g. Annual contract value or ARPU)"],
  "growth_rate": "e.g., 14% CAGR"
}}
"""

COMPETITOR_SWOT_PROMPT = """You are a Competitive Strategy Expert.
Build a competitor matrix and SWOT analysis based on the research.
DO NOT return an empty competitor list or an empty SWOT. If direct competitors are not named in the research brief, identify indirect competitors, legacy solutions, or substitute workflows.

Idea: {startup_idea}

Research Brief:
{research_brief}

REQUIREMENTS:
1. "competitor_matrix" MUST contain at least 3 distinct competitors (between 3 and 5).
2. Each competitor MUST have non-empty "name", "strength", and "weakness".
3. "swot" MUST contain at least 3 distinct, specific items in EVERY quadrant (strengths >= 3, weaknesses >= 3, opportunities >= 3, threats >= 3).

Your output MUST be ONLY valid JSON in this exact format:
{{
  "competitor_matrix": [
    {{
      "name": "Competitor 1",
      "strength": "Their primary advantage in the market",
      "weakness": "Their primary limitation or customer pain point",
      "price_point": "High / Moderate / Freemium",
      "market_position": "e.g. Incumbent market leader",
      "opportunity": "How our startup wins against them"
    }},
    {{
      "name": "Competitor 2",
      "strength": "Their advantage",
      "weakness": "Their limitation",
      "price_point": "Pricing info",
      "market_position": "Market position",
      "opportunity": "Differentiation angle"
    }},
    {{
      "name": "Competitor 3",
      "strength": "Their advantage",
      "weakness": "Their limitation",
      "price_point": "Pricing info",
      "market_position": "Market position",
      "opportunity": "Differentiation angle"
    }}
  ],
  "swot": {{
    "strengths": [
      "Internal strength 1 (e.g. proprietary tech)",
      "Internal strength 2 (e.g. low-cost structure)",
      "Internal strength 3 (e.g. superior UX)"
    ],
    "weaknesses": [
      "Internal weakness 1 (e.g. early stage lack of brand)",
      "Internal weakness 2 (e.g. capital constraints)",
      "Internal weakness 3 (e.g. dependency on third-party APIs)"
    ],
    "opportunities": [
      "External opportunity 1 (e.g. growing regulatory requirement)",
      "External opportunity 2 (e.g. untapped SMB segment)",
      "External opportunity 3 (e.g. enterprise integrations)"
    ],
    "threats": [
      "External threat 1 (e.g. incumbent feature copy)",
      "External threat 2 (e.g. customer churn risk)",
      "External threat 3 (e.g. platform privacy changes)"
    ]
  }}
}}
"""

DEVILS_ADVOCATE_PROMPT = """You are a Senior Venture Capital Analyst, Startup Advisor, and Business Model Expert.

Your task is to review the Investor Readiness Review output generated for a startup plan and identify the problems, incorrect reasoning, missing information, and weak areas.

Startup Idea:
{startup_idea}

Compiled Plan:
{compiled_plan}

Analyze the review carefully and perform the following tasks.

====================================================
1. REVIEW QUALITY CHECK
====================================================
First check whether the Investor Review itself is logically correct.
Identify:
- Incorrect statements
- Contradictory statements
- Generic feedback
- Misleading conclusions
- Missing context
- Poorly explained red flags
If any red flag is unclear or technically incorrect, rewrite it into a professional investor-level observation.

====================================================
2. RED FLAG ANALYSIS
====================================================
For every red flag:
Provide:
- Red Flag Title
- Severity Level: (Low / Medium / High / Critical)
- Why this is a problem
- Business impact
- Evidence or reasoning behind this concern
- What an investor would think
- Recommended solution

====================================================
3. BUSINESS MODEL REVIEW
====================================================
Analyze:
- Revenue Model
- Pricing Strategy
- Customer Acquisition Strategy
- Cost Structure
- Profit Margin
- Scalability
- Recurring Revenue Potential
Identify weaknesses.
Then suggest:
- Improved revenue model
- Pricing recommendations
- Monetization opportunities
- Growth strategy

====================================================
4. MARKET VALIDATION REVIEW
====================================================
Evaluate:
- Is there a real customer problem?
- Is the market large enough?
- Is demand proven?
- Are assumptions supported by research?
Identify missing validation data.
Suggest:
- Research needed
- Customer interviews required
- Metrics to track

====================================================
5. INVESTOR PERSPECTIVE REVIEW
====================================================
Act as a skeptical VC investor.
Answer:
Why would an investor reject this startup?
What questions would investors ask?
What evidence would they require before investing?
What changes would increase investment confidence?

====================================================
6. IMPROVED INVESTOR READINESS SCORE
====================================================
Recalculate scores:
Problem Validation: /10
Market Opportunity: /10
Competition: /10
Product Differentiation: /10
Revenue Model: /10
Scalability: /10
Execution Risk: /10
Investment Readiness: /10

Calculate:
Overall Feasibility Score: /100
Explain score changes.

====================================================
7. ACTION PLAN
====================================================
Create an improvement roadmap.
Priority 1: Critical issues that must be fixed before launch.
Priority 2: Important improvements.
Priority 3: Future optimization.

For each action provide:
- Problem
- Solution
- Expected impact
- Difficulty level

====================================================
8. FINAL INVESTOR VERDICT
====================================================
Generate a final VC-style conclusion.
Choose one:
- Strong Investment Opportunity
- Investable After Improvements
- Needs More Validation
- High Risk
- Not Investment Ready

Explain:
- Why
- What needs to change
- What milestones must be achieved before investment

CRITICAL REQUIREMENT:
Generate actual scores as integers (0-10, or 0-100). Do not output "N/A" or strings for scores.
Your output MUST be ONLY valid JSON in this EXACT format (do not use markdown formatting outside the JSON block):
{{
  "scores": {{
    "problem_validation": 8,
    "market_opportunity": 7,
    "revenue_model": 6,
    "risk_score": 9,
    "overall_feasibility_score": 75
  }},
  "action_plan": {{
    "priority_1": [
      {{
        "problem": "",
        "solution": "",
        "expected_impact": ""
      }}
    ]
  }},
  "final_verdict": {{
    "verdict": "",
    "why": ""
  }}
}}
"""
