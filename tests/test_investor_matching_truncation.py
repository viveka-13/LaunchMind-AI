import pytest
import json
from unittest.mock import AsyncMock, patch
from agent.llm_client import LLMResult
from agent.workflow import safe_json_parse, SafeJsonParseError
from agent.investor_matcher import match_investors, InvestorMatchModel

@pytest.mark.asyncio
async def test_truncation_triggers_retry_with_higher_limit():
    """Verify that a length-truncated response causes safe_json_parse to retry once with higher limit."""
    call_records = []

    async def mock_llm_call(messages, node=None, max_tokens=1500, session_id=None, retry_callback=None):
        call_records.append({"node": node, "max_tokens": max_tokens})
        if len(call_records) == 1:
            # First call is truncated mid-string
            return LLMResult(
                text='{"matched_investors": [{"investor_name": "Sequoia Capital", "match_percentage": 90, "why_this_investor_matches": "Great f',
                attempts=1,
                latency_ms=100.0,
                model="mock-model",
                finish_reason="length",
            )
        else:
            # Retry call succeeds with higher token limit
            valid_json = json.dumps({
                "matched_investors": [{
                    "investor_name": "Sequoia Capital",
                    "match_percentage": 90,
                    "investment_stage": "Seed",
                    "sector_focus": "AI / AgTech",
                    "why_this_investor_matches": "Strong portfolio fit and seed stage focus.",
                    "portfolio_examples": "AgroTech Inc",
                    "expected_cheque_size": "$500K"
                }]
            })
            return LLMResult(
                text=valid_json,
                attempts=1,
                latency_ms=80.0,
                model="mock-model",
                finish_reason="stop",
            )

    with patch("agent.workflow.llm_call", side_effect=mock_llm_call):
        res = await match_investors(
            idea="AgroMind AI",
            revenue_model="SaaS $30/mo",
            core_features="Crop AI",
            initial_cash="$150,000",
        )

    assert len(call_records) == 2
    assert call_records[0]["node"] == "investor_matching"
    assert call_records[1]["node"] == "investor_matching_truncation_retry"
    assert call_records[1]["max_tokens"] > call_records[0]["max_tokens"]
    assert "matched_investors" in res
    assert len(res["matched_investors"]) == 1
    assert res["matched_investors"][0]["investor_name"] == "Sequoia Capital"


@pytest.mark.asyncio
async def test_truncation_raises_error_if_unresolvable():
    """Verify that if even after retry the JSON cannot be parsed, SafeJsonParseError is raised."""
    async def mock_always_truncated(messages, node=None, max_tokens=1500, session_id=None, retry_callback=None):
        return LLMResult(
            text='{"matched_investors": [{"investor_name": "Incomplete',
            attempts=1,
            latency_ms=50.0,
            model="mock-model",
            finish_reason="length",
        )

    with patch("agent.workflow.llm_call", side_effect=mock_always_truncated):
        with pytest.raises(SafeJsonParseError):
            await match_investors(
                idea="AgroMind AI",
                revenue_model="SaaS",
                core_features="AI",
                initial_cash="$100k",
            )

