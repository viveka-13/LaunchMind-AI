import pytest
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from agent.pitch_practice import (
    MAX_TOKENS_QUESTION,
    MAX_TOKENS_EVALUATION,
    MAX_TOKENS_SUMMARY,
    build_compact_plan_summary,
    generate_pitch_question,
    evaluate_pitch_answer,
    generate_pitch_session_summary,
    export_simulation_transcript,
)
from agent.investor_personas import resolve_persona, INVESTOR_PERSONAS
from agent.memory import (
    init_db,
    save_startup_plan,
    create_pitch_session,
    get_pitch_session,
    update_pitch_session,
    save_practice_turn,
    get_session_turns,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def fixture_plan():
    plan_id = str(uuid.uuid4())
    plan_data = {
        "id": plan_id,
        "startup_title": "SafeShield AI",
        "idea": "AI app for female personal protection",
        "problem_statement": "Women traveling late night lack proactive, sensor-driven safety monitoring.",
        "target_audience": "Working women and college students in urban transit corridors.",
        "market_gap": "Current panic buttons require manual triggers during active duress.",
        "solution_strategy": "Autonomous edge acoustic anomaly detection and automated escort dispatch.",
        "core_features": "Sentinel-Audio-Defense real-time threat listener; Emergency Escort Drone dispatch.",
        "revenue_model": "Monthly tier subscriptions and emergency response dispatch fees.",
        "pricing_model": json.dumps({
            "tiers": [
                {"name": "Guardian Basic", "monthly_price": 29.0},
                {"name": "Sentinel Pro", "monthly_price": 199.0},
            ]
        }),
        "financial_projection": json.dumps({"initial_cash": 250000.0, "cogs_pct": 0.2}),
        "cap_table": json.dumps({"funding_amount": 750000.0, "pre_money_valuation": 3500000.0}),
        "competitor_analysis": "Legacy 911 dispatch, Life360, Noonlight",
        "critique": json.dumps({
            "final_verdict": {"verdict": "Promising but high liability risks"},
            "action_plan": {"priority_1": [{"problem": "False positive emergency dispatches"}]},
        }),
        "language": "en",
    }
    save_startup_plan(plan_id, plan_data["idea"], plan_data["startup_title"], plan_data)
    return plan_data


def test_token_limits_regression():
    """1. Regression test: ensure token limits are high enough to avoid truncated_response."""
    assert MAX_TOKENS_QUESTION >= 400, "MAX_TOKENS_QUESTION must be at least 400"
    assert MAX_TOKENS_EVALUATION >= 900, "MAX_TOKENS_EVALUATION must be at least 900"
    assert MAX_TOKENS_SUMMARY >= 700, "MAX_TOKENS_SUMMARY must be at least 700"


@pytest.mark.asyncio
async def test_question_generation_includes_plan_specific_details(fixture_plan):
    """2. Start returns a question that includes plan-specific terms from the fixture."""
    captured = {}

    async def mock_llm_invoke(system, prompt, language="English", max_tokens=600, node="test", session_id=None):
        captured["system"] = system
        captured["prompt"] = prompt
        return "Given your Sentinel-Audio-Defense feature and $199/mo Sentinel Pro price, how will you handle false positive audio triggers?"

    with patch("agent.workflow.llm_invoke", side_effect=mock_llm_invoke):
        question = await generate_pitch_question(
            plan=fixture_plan,
            persona_id="aggressive_vc",
            history=[],
            language="en",
            turn_index=1,
            total_turns=5,
        )

        assert "Sentinel-Audio-Defense" in captured["prompt"]
        assert "199" in captured["prompt"]
        assert "Aggressive VC" in captured["system"] or "Aggressive VC" in captured["prompt"]
        assert "Sentinel" in question


@pytest.mark.asyncio
async def test_persona_prompts_differ_and_used(fixture_plan):
    """3. Verify persona prompts differ and each persona's specific prompt is passed to the LLM."""
    captured_prompts = {}

    async def mock_llm_invoke(system, prompt, language="English", max_tokens=600, node="test", session_id=None):
        captured_prompts[captured_prompts.get("_curr_persona")] = prompt
        return "Sample question?"

    with patch("agent.workflow.llm_invoke", side_effect=mock_llm_invoke):
        for p_id in ["aggressive_vc", "technical_angel", "academic_examiner"]:
            captured_prompts["_curr_persona"] = p_id
            await generate_pitch_question(
                plan=fixture_plan,
                persona_id=p_id,
                history=[],
                language="en",
            )

    assert "billion-dollar" in captured_prompts["aggressive_vc"] or "TAM" in captured_prompts["aggressive_vc"]
    assert "architecture" in captured_prompts["technical_angel"] or "latency" in captured_prompts["technical_angel"]
    assert "methodology" in captured_prompts["academic_examiner"] or "benchmark" in captured_prompts["academic_examiner"]


def test_legacy_persona_mapping():
    """4. Verify legacy persona IDs are mapped correctly."""
    assert resolve_persona("seed_vc")["id"] == "aggressive_vc"
    assert resolve_persona("angel")["id"] == "technical_angel"
    assert resolve_persona("series_a")["id"] == "market_focused"
    assert resolve_persona("technical")["id"] == "technical_reviewer"


@pytest.mark.asyncio
async def test_answer_evaluation_required_fields_and_honest_scoring(fixture_plan):
    """5. Verify evaluation schema completeness and honest score variation."""
    async def mock_eval_parse(prompt, language="English", system_prompt=None, max_tokens=1200, model_cls=None, node=None, session_id=None):
        if "WEAK_TEST" in prompt:
            return {
                "score": 2,
                "strengths": ["Polite tone"],
                "weaknesses": ["Vague and completely dodged the question", "Zero metrics provided"],
                "missed_points": ["Did not mention the $199/mo pricing", "Ignored edge acoustic detection feature"],
                "better_answer": "Our Sentinel Pro tier is $199/mo and reduces false triggers through edge filtering [Assumption].",
                "follow_up_hint": "Prepare to explain audio false-positive rates.",
            }
        else:
            return {
                "score": 9,
                "strengths": ["Grounded in Sentinel-Audio-Defense specs", "Directly addressed unit economics"],
                "weaknesses": ["Could mention patent defensibility"],
                "missed_points": ["Could emphasize the $250k initial cash reserve"],
                "better_answer": "We utilize on-device acoustic models with a 99.2% precision threshold [Assumption].",
                "follow_up_hint": "Expect questions on enterprise partnerships next.",
            }

    with patch("agent.workflow.safe_json_parse", side_effect=mock_eval_parse):
        weak_eval = await evaluate_pitch_answer(
            question="How do you justify your $199 pricing?",
            answer="WEAK_TEST: We think people will just pay because safety is important.",
            plan=fixture_plan,
        )
        assert weak_eval["score"] == 2
        assert len(weak_eval["missed_points"]) >= 1
        assert "better_answer" in weak_eval
        assert "follow_up_hint" in weak_eval

        strong_eval = await evaluate_pitch_answer(
            question="How do you justify your $199 pricing?",
            answer="STRONG_TEST: Our $199 Sentinel Pro plan targets institutional security partnerships.",
            plan=fixture_plan,
        )
        assert strong_eval["score"] == 9
        assert strong_eval["score"] > weak_eval["score"]


def test_api_validation_and_lifecycle(fixture_plan):
    """6. Test API endpoints: 404 on bad plan/session, 422 on empty/long answers, 409 on finished."""
    client = TestClient(app)

    # 404 for unknown plan
    bad_plan_res = client.post("/api/practice/start/non-existent-id", json={"persona_id": "aggressive_vc"})
    assert bad_plan_res.status_code == 404

    # Start real session with mock
    with patch("main.generate_pitch_question", new=AsyncMock(return_value="How does your tech work?")):
        start_res = client.post(f"/api/practice/start/{fixture_plan['id']}", json={"persona": "aggressive_vc", "num_questions": 2})
        assert start_res.status_code == 200
        start_data = start_res.json()
        session_id = start_data["session_id"]
        assert start_data["question"] == "How does your tech work?"
        assert start_data["turn_index"] == 1

    # 422 for empty answer
    empty_ans_res = client.post("/api/practice/answer", json={"session_id": session_id, "answer": "   "})
    assert empty_ans_res.status_code == 422

    # 422 for over-long answer
    long_ans_res = client.post("/api/practice/answer", json={"session_id": session_id, "answer": "x" * 3001})
    assert long_ans_res.status_code == 422

    # 404 for unknown session
    unknown_sess_res = client.post("/api/practice/answer", json={"session_id": "bad-session-id", "answer": "Valid text"})
    assert unknown_sess_res.status_code == 404

    # Submit valid Turn 1 answer
    mock_eval = {
        "score": 7,
        "strengths": ["Clear explanation"],
        "weaknesses": ["Needs more data"],
        "missed_points": ["Point 1"],
        "better_answer": "Model answer",
        "follow_up_hint": "Next hint",
    }
    with patch("main.evaluate_pitch_answer", new=AsyncMock(return_value=mock_eval)), \
         patch("main.generate_pitch_question", new=AsyncMock(return_value="What is your CAC?")):
        turn1_res = client.post("/api/practice/answer", json={"session_id": session_id, "answer": "Our system detects anomalies on-device."})
        assert turn1_res.status_code == 200
        turn1_data = turn1_res.json()
        assert turn1_data["finished"] is False
        assert turn1_data["next_question"] == "What is your CAC?"
        assert turn1_data["turn_index"] == 2

    # Submit valid Turn 2 answer (Session finishes since num_questions=2)
    mock_summary = {
        "overall_score": 7.5,
        "scores_per_turn": [7, 8],
        "top_strengths": ["Sound technical grounding"],
        "top_weaknesses": ["Unit economics unclear"],
        "key_improvements": ["Refine CAC", "Practice moat", "Clarify distribution"],
        "verdict": "Seed investable with customer validation",
    }
    with patch("main.evaluate_pitch_answer", new=AsyncMock(return_value={**mock_eval, "score": 8})), \
         patch("main.generate_pitch_session_summary", new=AsyncMock(return_value=mock_summary)):
        turn2_res = client.post("/api/practice/answer", json={"session_id": session_id, "answer": "CAC is recovered in 3 months via university partnerships."})
        assert turn2_res.status_code == 200
        turn2_data = turn2_res.json()
        assert turn2_data["finished"] is True
        assert turn2_data["next_question"] is None
        assert turn2_data["summary"]["overall_score"] == 7.5
        assert "transcript_url" in turn2_data

    # 409 when submitting to finished session
    finished_res = client.post("/api/practice/answer", json={"session_id": session_id, "answer": "Another answer"})
    assert finished_res.status_code == 409

    # GET /api/practice/session/{session_id} returns all turns in order
    session_res = client.get(f"/api/practice/session/{session_id}")
    assert session_res.status_code == 200
    sess_data = session_res.json()
    assert sess_data["status"] == "completed"
    assert len(sess_data["turns"]) == 2
    assert sess_data["turns"][0]["turn_index"] == 1
    assert sess_data["turns"][1]["turn_index"] == 2

    # GET /api/practice/transcript/{session_id} serves transcript file
    trans_res = client.get(f"/api/practice/transcript/{session_id}")
    assert trans_res.status_code == 200
    trans_json = trans_res.json()
    assert trans_json["session_id"] == session_id
    assert len(trans_json["turns"]) == 2
