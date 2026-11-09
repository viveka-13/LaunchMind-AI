# agent/pitch_practice.py
# Interactive Pitch Practice & Investor Simulation Engine

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from agent.investor_personas import resolve_persona
from agent.language import validate_language

logger = logging.getLogger(__name__)

# Named Token Limits (generous and safe to prevent truncated_response errors, especially with reasoning models)
MAX_TOKENS_QUESTION: int = 2048
MAX_TOKENS_EVALUATION: int = 4096
MAX_TOKENS_SUMMARY: int = 3072


class PitchEvaluation(BaseModel):
    score: int = Field(ge=0, le=10, description="Evaluation score from 0 to 10")
    strengths: List[str] = Field(default_factory=list, description="Key strengths identified in the answer")
    weaknesses: List[str] = Field(default_factory=list, description="Key weaknesses, vagueness, or gaps in the answer")
    missed_points: List[str] = Field(
        default_factory=list,
        description="Specific facts, metrics, or features from the business plan that the founder should have cited",
    )
    better_answer: str = Field(
        description="A high-impact model answer grounded strictly in the plan's facts. Any unstated detail must be marked as [Assumption].",
    )
    follow_up_hint: str = Field(
        description="Strategic tip for how to handle this topic or the next follow-up question.",
    )


class PitchSessionSummary(BaseModel):
    overall_score: float = Field(ge=0.0, le=10.0, description="Average evaluation score across all turns")
    scores_per_turn: List[int] = Field(default_factory=list, description="Scores for each question in order")
    top_strengths: List[str] = Field(default_factory=list, description="Top overall pitch strengths observed")
    top_weaknesses: List[str] = Field(default_factory=list, description="Top overall pitch weaknesses observed")
    key_improvements: List[str] = Field(
        default_factory=list,
        description="Top 3 concrete, prioritized improvements the founder should practice next",
    )
    verdict: str = Field(description="Summary readiness verdict from the investor perspective")


def build_compact_plan_summary(plan: dict) -> str:
    """
    Construct a dense, well-structured summary of the startup plan.
    Covers problem, target audience, market gap, solution, features, revenue,
    pricing, financials, cap table, competitors, and red flags.
    """
    if not plan or not isinstance(plan, dict):
        return "Startup details unavailable."

    title = plan.get("startup_title") or plan.get("title") or plan.get("idea", "Startup")
    idea = plan.get("idea", "")
    problem = str(plan.get("problem_statement", ""))[:350].strip()
    audience = str(plan.get("target_audience", ""))[:250].strip()
    market_gap = str(plan.get("market_gap", ""))[:300].strip()
    solution = str(plan.get("solution_strategy") or plan.get("solution", ""))[:350].strip()
    features = str(plan.get("core_features", ""))[:450].strip()

    # Revenue & Pricing extraction
    revenue = str(plan.get("revenue_model") or plan.get("business_model", ""))[:350].strip()
    pricing_raw = plan.get("pricing_model", "")
    pricing_info = ""
    if pricing_raw:
        try:
            p_data = json.loads(pricing_raw) if isinstance(pricing_raw, str) else pricing_raw
            if isinstance(p_data, dict) and "tiers" in p_data:
                tier_strs = [
                    f"{t.get('name', 'Tier')}: ${t.get('monthly_price', 0)}/mo"
                    for t in p_data.get("tiers", [])[:3]
                ]
                pricing_info = f" [Tiers: {', '.join(tier_strs)}]"
        except Exception:
            pricing_info = f" [{str(pricing_raw)[:150]}]"

    # Financial & Funding extraction
    financials_raw = plan.get("financial_projection", "")
    fin_info = ""
    if financials_raw:
        try:
            f_data = json.loads(financials_raw) if isinstance(financials_raw, str) else financials_raw
            if isinstance(f_data, dict):
                fin_info = f" [Initial Cash: ${f_data.get('initial_cash', 'N/A')}, COGS: {f_data.get('cogs_pct', 'N/A')}]"
        except Exception:
            fin_info = f" [{str(financials_raw)[:100]}]"

    cap_raw = plan.get("cap_table", "")
    cap_info = ""
    if cap_raw:
        try:
            c_data = json.loads(cap_raw) if isinstance(cap_raw, str) else cap_raw
            if isinstance(c_data, dict):
                cap_info = f" [Funding Ask: ${c_data.get('funding_amount', 'N/A')}, Pre-Money Val: ${c_data.get('pre_money_valuation', 'N/A')}]"
        except Exception:
            cap_info = f" [{str(cap_raw)[:100]}]"

    competitors = str(plan.get("competitor_analysis", ""))[:250].strip()

    # Red flags from adversarial critique
    critique_raw = plan.get("critique", "")
    critique_info = ""
    if critique_raw:
        try:
            crit_data = json.loads(critique_raw) if isinstance(critique_raw, str) else critique_raw
            if isinstance(crit_data, dict):
                verdict = crit_data.get("final_verdict", {}).get("verdict", "")
                actions = [
                    act.get("problem", "")
                    for act in crit_data.get("action_plan", {}).get("priority_1", [])[:2]
                ]
                critique_info = f"Verdict: {verdict}. Key Risks: {'; '.join(actions)}"
        except Exception:
            critique_info = str(critique_raw)[:200]

    summary = f"""--- STARTUP PLAN CONTEXT ---
Startup Name: {title}
Core Idea: {idea}
Target Audience: {audience or 'Not specified'}
Problem Statement: {problem or 'Not specified'}
Market Gap Identified: {market_gap or 'Not specified'}
Solution Strategy: {solution or 'Not specified'}
Core Features: {features or 'Not specified'}
Revenue & Monetization: {revenue}{pricing_info}
Financials & Capital Structure:{fin_info}{cap_info}
Competitor Landscape: {competitors or 'Not specified'}
Investor Review Red Flags: {critique_info or 'None noted'}
---------------------------"""
    return summary


async def generate_pitch_question(
    plan: dict,
    persona_id: str,
    history: list,
    language: str = "en",
    turn_index: int = 1,
    total_turns: int = 5,
) -> str:
    """
    Generate an incisive investor question tailored to the startup plan and persona.
    """
    from agent.workflow import llm_invoke

    persona = resolve_persona(persona_id)
    canonical_lang = validate_language(language)
    plan_summary = build_compact_plan_summary(plan)

    # Format previous turns
    history_lines = []
    for msg in history:
        role = msg.get("role", "user").upper()
        content = msg.get("content", "")
        # Omit internal evaluator dumps from prompt history
        if role != "EVALUATOR":
            history_lines.append(f"{role}: {content}")
    history_text = "\n".join(history_lines) if history_lines else "No prior questions asked yet."

    prompt = f"""{persona['prompt']}

{plan_summary}

CONVERSATION HISTORY SO FAR:
{history_text}

INSTRUCTIONS FOR QUESTION #{turn_index} OF {total_turns}:
1. You are interviewing the founder. Ask exactly ONE concise, challenging, and insightful question based on your persona.
2. YOUR QUESTION MUST REFERENCE OR CHALLENGE SPECIFIC DETAILS FROM THE PLAN SUMMARY ABOVE (such as their pricing, specific features, stated market gap, target customers, unit economics, or architecture).
3. If there is conversation history, react directly to the founder's previous answer (e.g. push back on vague claims, probe deeper into risks, or demand concrete evidence).
4. Do NOT ask generic questions (e.g., avoid 'Tell me about yourself' or 'What is your vision?'). Be direct and demanding.
5. Do NOT repeat any questions already asked in the history.
6. CRITICAL LANGUAGE REQUIREMENT: Ask the question in {canonical_lang}. Do NOT mix other languages.
7. Return ONLY the question text. Do not include greetings, role prefixes ('Investor:'), or conversational filler.
"""

    system_prompt = f"You are {persona['name']}, a rigorous startup evaluator. Ask exactly one challenging question in {canonical_lang}."
    question = await llm_invoke(
        system_prompt,
        prompt,
        language=canonical_lang,
        max_tokens=MAX_TOKENS_QUESTION,
        node="pitch_question",
    )

    clean_q = question.strip().replace("Investor:", "").replace("Question:", "").strip()
    if clean_q.startswith('"') and clean_q.endswith('"'):
        clean_q = clean_q[1:-1].strip()

    if not clean_q:
        clean_q = f"Could you explain the defensible moat of {plan.get('startup_title', 'your startup')} against existing alternatives?"

    return clean_q


async def evaluate_pitch_answer(
    question: str,
    answer: str,
    plan: dict,
    language: str = "en",
) -> dict:
    """
    Rigorously evaluate a founder's answer against the actual business plan facts.
    Returns a Pydantic-validated dictionary.
    """
    from agent.workflow import safe_json_parse

    canonical_lang = validate_language(language)
    plan_summary = build_compact_plan_summary(plan)

    prompt = f"""You are an expert pitch coach and startup investor evaluating a founder's answer to an interview question.

{plan_summary}

QUESTION ASKED:
"{question}"

FOUNDER'S ANSWER:
"{answer}"

EVALUATION RUBRIC:
- 0 to 3 (Poor/Vague): Answer is generic, evasive, off-topic, buzzword-heavy, or contains no actionable plan specifics.
- 4 to 6 (Mediocre): Answer addresses the question generally, but lacks concrete metrics, pricing details, or plan citations.
- 7 to 8 (Good): Answer provides specific, realistic details directly referencing the business model, features, or go-to-market.
- 9 to 10 (Exceptional): Answer is concise, authoritative, deeply grounded in the plan's numbers/architecture, and addresses the investor's core doubt.

CRITICAL REQUIREMENTS:
1. Be rigorous and honest in scoring. Do not give inflated scores to superficial answers.
2. 'missed_points': List 2-3 specific facts, numbers, or features from the business plan summary above that the founder SHOULD have used in their answer.
3. 'better_answer': Provide a concise model answer (2-4 sentences) grounded STRICTLY in the facts from the plan summary. Do NOT invent new features, metrics, or partnerships; if you must make an assumption, explicitly mark it as '[Assumption]'.
4. 'follow_up_hint': Give 1 concrete tip on what the investor will look for next.
5. All JSON values (feedback, weaknesses, strengths, model answer, hint) MUST be written in {canonical_lang}.
6. Keep all JSON keys strictly in English.

Return ONLY valid JSON matching this schema:
{{
  "score": 6,
  "strengths": ["Clear communication of X", "Acknowledged the core issue"],
  "weaknesses": ["Did not mention specific pricing", "Vague on customer acquisition channels"],
  "missed_points": ["The plan states pricing starts at $49/mo for tier 1", "Did not reference the Pexels/GraphQL integration"],
  "better_answer": "Model answer in {canonical_lang}...",
  "follow_up_hint": "Prepare to explain your CAC payback period in months."
}}
"""

    system_prompt = (
        f"You are a startup pitch evaluator. Output valid JSON only. Keep analysis concise and direct without preamble. All feedback text must be in {canonical_lang}."
    )

    result = await safe_json_parse(
        prompt,
        language=canonical_lang,
        system_prompt=system_prompt,
        max_tokens=MAX_TOKENS_EVALUATION,
        model_cls=PitchEvaluation,
        node="pitch_evaluation",
    )

    # Ensure score bounds
    if "score" in result:
        try:
            result["score"] = max(0, min(10, int(result["score"])))
        except Exception:
            result["score"] = 5

    return result


async def generate_pitch_session_summary(
    history: list,
    plan: dict,
    language: str = "en",
) -> dict:
    """
    Generate an overarching performance summary at the conclusion of a pitch session.
    """
    from agent.workflow import safe_json_parse

    canonical_lang = validate_language(language)
    plan_summary = build_compact_plan_summary(plan)

    turns_transcript = []
    scores = []
    turn_num = 1

    for i in range(len(history)):
        msg = history[i]
        if msg.get("role") == "investor":
            q_text = msg.get("content", "")
            ans_text = ""
            eval_dict = {}
            if i + 1 < len(history) and history[i + 1].get("role") == "founder":
                ans_text = history[i + 1].get("content", "")
            if i + 2 < len(history) and history[i + 2].get("role") == "evaluator":
                try:
                    eval_raw = history[i + 2].get("content", "{}")
                    eval_dict = json.loads(eval_raw) if isinstance(eval_raw, str) else eval_raw
                    if "score" in eval_dict:
                        scores.append(int(eval_dict["score"]))
                except Exception:
                    pass

            turns_transcript.append(
                f"Turn {turn_num}:\nQ: {q_text}\nA: {ans_text}\nScore: {eval_dict.get('score', 'N/A')}\n"
            )
            turn_num += 1

    transcript_text = "\n".join(turns_transcript)
    calculated_avg = round(sum(scores) / len(scores), 1) if scores else 5.0

    prompt = f"""You are the lead partner conducting the final post-pitch evaluation debrief.

{plan_summary}

FULL SESSION TRANSCRIPT:
{transcript_text}

SCORES RECORDED: {scores} (Average: {calculated_avg})

INSTRUCTIONS:
1. Provide an objective summary of the founder's overall pitch performance across the entire interview.
2. 'overall_score': Set to {calculated_avg} (or adjust slightly based on holistic clarity).
3. 'scores_per_turn': {scores}.
4. 'top_strengths': 2-3 main strengths demonstrated across all turns.
5. 'top_weaknesses': 2-3 persistent weaknesses or blind spots observed.
6. 'key_improvements': Exactly 3 prioritized, highly actionable recommendations for the founder to practice before meeting real investors.
7. 'verdict': A crisp, realistic 1-2 sentence readiness verdict (e.g. 'Ready for angel syndicates with polished unit economics', 'Needs significant customer validation before approaching VCs').
8. All feedback text must be written in {canonical_lang}. Keep all JSON keys in English.

Return ONLY valid JSON matching this schema:
{{
  "overall_score": {calculated_avg},
  "scores_per_turn": {scores},
  "top_strengths": ["Clear passion and domain knowledge", "Grounded feature breakdown"],
  "top_weaknesses": ["Vague pricing strategy", "Incomplete defensibility answer"],
  "key_improvements": ["Memorize tier pricing and CAC numbers", "Prepare a clear 2-minute moat story", "Practice answering with concrete metrics"],
  "verdict": "Verdict in {canonical_lang}..."
}}
"""

    system_prompt = f"You are a venture capital debriefing coach. Output valid JSON only. All feedback must be in {canonical_lang}."
    summary = await safe_json_parse(
        prompt,
        language=canonical_lang,
        system_prompt=system_prompt,
        max_tokens=MAX_TOKENS_SUMMARY,
        model_cls=PitchSessionSummary,
        node="pitch_summary",
    )

    if not summary.get("scores_per_turn"):
        summary["scores_per_turn"] = scores
    if not summary.get("overall_score"):
        summary["overall_score"] = calculated_avg

    return summary


def export_simulation_transcript(
    session_id: str,
    plan_id: str,
    persona: dict,
    history: list,
    summary: Optional[dict] = None,
    language: str = "en",
) -> str:
    """
    Format and export simulation_transcript.json into both the plan directory and global pitch dir.
    Returns the absolute path of the generated transcript file.
    """
    out_dir_plan = os.path.abspath(f"./data/pitch/{plan_id}")
    out_dir_global = os.path.abspath("./data/pitch")
    os.makedirs(out_dir_plan, exist_ok=True)
    os.makedirs(out_dir_global, exist_ok=True)

    # Reconstruct turns
    turns = []
    turn_idx = 1
    i = 0
    while i < len(history):
        if history[i].get("role") == "investor":
            q = history[i].get("content", "")
            ans = ""
            ev = {}
            if i + 1 < len(history) and history[i + 1].get("role") == "founder":
                ans = history[i + 1].get("content", "")
            if i + 2 < len(history) and history[i + 2].get("role") == "evaluator":
                try:
                    raw_e = history[i + 2].get("content", "{}")
                    ev = json.loads(raw_e) if isinstance(raw_e, str) else raw_e
                except Exception:
                    ev = {}
            turns.append({
                "turn_index": turn_idx,
                "question": q,
                "answer": ans,
                "evaluation": ev,
            })
            turn_idx += 1
            i += 3
        else:
            i += 1

    transcript_data = {
        "session_id": session_id,
        "plan_id": plan_id,
        "persona": {
            "id": persona.get("id"),
            "name": persona.get("name"),
            "title": persona.get("title"),
        },
        "language": language,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "overall_score": summary.get("overall_score") if summary else None,
        "summary": summary,
        "total_turns": len(turns),
        "turns": turns,
    }

    # Save specific session transcript
    session_file = os.path.join(out_dir_plan, f"{session_id}_transcript.json")
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    # Save canonical simulation_transcript.json
    canonical_file = os.path.join(out_dir_plan, "simulation_transcript.json")
    with open(canonical_file, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    global_file = os.path.join(out_dir_global, "simulation_transcript.json")
    with open(global_file, "w", encoding="utf-8") as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    return session_file
