# agent/prompts.py
# All prompts used by the LangGraph agent nodes

from datetime import datetime

DECOMPOSE_PROMPT = """You are an expert startup analyst and business strategist.

A user has submitted the following startup idea: "{idea}"

Your task is to decompose this idea into 10 specific research and analysis subtasks that an AI agent will execute.

CRITICAL RULE FOR AUTONOMOUS EXECUTION:
All 10 tasks must be desk-research, data-synthesis, or AI-executable analysis tasks (e.g. TAM calculation, competitor benchmarking, tech stack design, pricing strategy).
DO NOT assign manual offline fieldwork to the autonomous agent (such as 'interview 30+ farmers', 'conduct physical in-person surveys', or 'call local suppliers').
If any offline field validation is needed, label it explicitly as:
"Recommended Founder Validation Step (Post-AI): [Fieldwork description]"

Return ONLY a JSON array of exactly 10 task strings. No explanations, no markdown, just the JSON array.

Example format:
["Task 1: Market size analysis...", "Task 2: Competitor research...", "Task 3: Recommended Founder Validation Step (Post-AI): Survey target users in local markets..."]
"""

GAP_ANALYSIS_PROMPT = """You are an elite product strategist and market analyst.

Startup Idea: {idea}

Synthesized Research Findings:
{research_brief}

Market Sizing Data:
{market_sizing}

Analyze the market data and identify:
1. 3 critical gaps in the existing market that competitors are ignoring.
2. The specific unmet need for the target audience.
3. Why NOW is the right time for this solution (market timing / technological inflection).

CRITICAL CONSISTENCY INSTRUCTION:
Do NOT state that the company has existing customers if it does not.
If citing market sizing figures, use ONLY the numbers provided above in Market Sizing Data. DO NOT invent contradictory market size estimates.
Maximum 250 words."""

SOLUTION_PROMPT = """You are an innovative startup founder and product architect.

Startup Idea: {idea}
Market Gap Identified: {market_gap}
Competitor Weaknesses: {competitor_analysis}

Design a compelling, differentiated product solution that:
1. Directly addresses the identified market gap
2. Exploits competitors' weaknesses
3. Has a clear unfair advantage / moat (e.g., proprietary data, network effects, switching costs)
4. Defines the Minimum Viable Product (MVP) scope

CRITICAL ANTI-HALLUCINATION RULE: DO NOT invent fake customers, fake revenue traction, fake team members, or fake partnerships. If data is unavailable, generate a validation plan, list required MVP milestones, or state that roles are TBD.

Be concrete, innovative, and focused. Maximum 300 words."""

FEATURES_PROMPT = """You are a Principal Product Manager.

Startup Idea: {idea}
Proposed Solution: {solution}

Define the 8 core features for this product.
Split them into:
- 4 MVP Features (essential for launch — Phase 1)
- 4 Post-MVP Features (growth and differentiation — Phase 2)

Format as a clean list:
1. [Feature Name]: [Brief description]
2. [Feature Name]: [Brief description]
...and so on for 8 features.

Make features specific, valuable, and directly tied to solving the market problem."""

REVENUE_PROMPT = """You are a startup financial strategist.

Startup Idea: {idea}
Solution: {solution}
Target Market: {market_research}

CANONICAL PROJECT FACTS (MANDATORY SINGLE SOURCE OF TRUTH):
{canonical_facts}

Generate a comprehensive revenue model narrative including:
- Primary revenue stream(s) referencing the EXACT canonical tiers and monthly prices above
- Secondary revenue opportunities (e.g. enterprise add-ons, API access)
- Projected unit economics: cite the EXACT blended ARPU, LTV, and CAC payback period from canonical facts
- Path to profitability: cite the EXACT deterministic milestone revenues (500 users, 5,000 users, 20,000 users) and break-even user count

CRITICAL RULES:
1. DO NOT invent different prices, tier names, or contradictory revenue numbers. Use the canonical numbers verbatim.
2. DO NOT state that the company has existing paying customers if it is pre-launch.
Maximum 250 words."""

ROADMAP_PROMPT = """You are a startup CTO and project manager.

Startup Idea: {idea}
Core Features: {features}
Revenue Model: {revenue}

CANONICAL PROJECT FACTS:
{canonical_facts}

Create a 12-month implementation roadmap with 4 phases:
- Phase 1 (Months 1-3): Foundation & MVP
- Phase 2 (Months 4-6): Beta Launch & Learning  
- Phase 3 (Months 7-9): Growth & Optimization
- Phase 4 (Months 10-12): Scale & Expand

CRITICAL DATE DIRECTIVE:
The current date is {current_date}. All future roadmap phases and milestones must be scheduled for {current_year} onwards (e.g. Q1 {current_year} through 2028). NEVER mention past years.
For each phase list exactly 3 specific milestones. Use concise bullet points (maximum 1 sentence per milestone)."""

PITCH_PROMPT = """You are a startup pitch coach who has helped companies raise millions.

Startup Idea: {idea}
Solution: {solution}
Revenue Model: {revenue}
Market Research: {market_research}

CANONICAL PROJECT FACTS (MANDATORY SINGLE SOURCE OF TRUTH):
{canonical_facts}

Create a 10-slide pitch deck outline. For each slide include:
- Slide title
- 2-3 concise bullet points of what to cover

Structure:
1. Title / Vision Hook
2. Problem (grounded in target audience pain points)
3. Solution (differentiated product moat)
4. Market Sizing (cite EXACT TAM/SAM/SOM from canonical facts)
5. Product & Core Features
6. Business Model (cite EXACT canonical pricing tiers and blended ARPU)
7. Go-to-Market & Validation Strategy
8. Milestones & Timeline (future dates starting from {current_year})
9. Financial Projections (cite EXACT 500, 5,000, and 20,000 user milestones and break-even)
10. The Ask (cite EXACT funding ask: {funding_ask}, valuation, and use of proceeds from canonical facts)

CRITICAL RULE: Adhere 100% to the canonical facts. Do NOT invent different funding asks, different tiers, or past dates."""

COMPILE_PROMPT = """You are a senior business analyst compiling a complete startup report.

Startup Idea: {idea}
All Research and Analysis: {all_context}

CANONICAL PROJECT FACTS:
{canonical_facts}

Generate the following in a structured format:

STARTUP_TITLE: [Catchy name for this startup, max 5 words]

PROBLEM_STATEMENT: [2-3 sentences describing the core problem being solved for the target customer]

TARGET_AUDIENCE: [Specific description of who the primary customer is, 2-3 sentences]

EXECUTIVE_SUMMARY: [A compelling 4-5 sentence executive summary that an investor would read. Accurately reflect the problem, solution, canonical market sizing, canonical pricing, and canonical raise ask of {funding_ask}.]

Return ONLY these 4 sections with exactly these labels. No other text."""
