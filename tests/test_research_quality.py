# tests/test_research_quality.py
# Offline unit tests for Idea Understanding, Query Routing, Relevance & Quality Filtering, and Subtask Filtering

import pytest
import json
import re
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models_pydantic import IdeaUnderstandingModel, TaskDecompositionModel
from agent.prompts import IDEA_UNDERSTANDING_PROMPT, DECOMPOSE_PROMPT
from agent.research_filter import (
    normalize_url,
    title_similarity,
    is_blacklisted_or_spam,
    is_stale_result,
    score_relevance,
    filter_and_rank_results,
)
from agent.workflow import (
    classify_subtask,
    create_desk_proxy_for_fieldwork,
    node_decompose_idea,
    node_understand_idea,
    node_research_market,
    node_research_competitors,
    StartupState,
)
from agent.tools import research_market, research_competitors, derive_market_keywords


# ─────────────────────────────────────────────
# 1. Idea Understanding Unit Tests
# ─────────────────────────────────────────────

def test_idea_understanding_named_product_schema():
    """Named product generates clean category queries without brand name and without hardcoded 2024."""
    current_year = datetime.now().year
    raw = {
        "idea_type": "named_product",
        "category": "AI precision agriculture and crop health diagnostics",
        "problem_domain": "Helping smallholder farmers detect crop diseases early using computer vision.",
        "target_customers": ["Commercial farm operators", "Agronomists"],
        "region_focus": "global",
        "market_queries": [
            f"precision agriculture market size {current_year}",
            "smart farming crop health monitoring market growth CAGR",
            "AI in agriculture market demand report",
        ],
        "competitor_queries": [
            "top smart farming crop diagnostics startups",
            "precision agriculture software alternatives",
            "AI agronomy tools competitors",
        ],
        "customer_voice_queries": [
            "crop monitoring app reddit complaints",
            "smart agriculture software farmer reviews",
        ],
        "trends_keywords": ["precision agriculture", "crop monitoring", "smart farming"],
        "competitor_name_check": "AgroMind AI",
        "known_company_with_same_name": None,
        "confidence": 0.95,
    }
    model = IdeaUnderstandingModel.model_validate(raw)
    dumped = model.model_dump()
    assert dumped["idea_type"] == "named_product"
    assert "AgroMind" not in " ".join(dumped["market_queries"])
    assert "AgroMind" not in " ".join(dumped["trends_keywords"])
    assert "2024" not in " ".join(dumped["market_queries"])
    assert str(current_year) in " ".join(dumped["market_queries"])


def test_idea_understanding_descriptive_idea_expansion():
    """Descriptive idea generates cleaned, expanded queries without noise words."""
    current_year = datetime.now().year
    raw = {
        "idea_type": "descriptive_idea",
        "category": "Women personal safety wearable and emergency alert mobile app",
        "problem_domain": "Immediate SOS and live location telemetry for women traveling alone.",
        "target_customers": ["Solo female commuters", "College students"],
        "region_focus": "global",
        "market_queries": [
            f"personal safety app market size {current_year}",
            "emergency alert software industry CAGR",
            "women safety tech sector valuation",
        ],
        "competitor_queries": [
            "top personal safety mobile apps",
            "women emergency response platforms competitors",
            "personal security wearables startups",
        ],
        "customer_voice_queries": [
            "safety alert apps battery drain user reviews",
            "women personal safety emergency app complaints reddit",
        ],
        "trends_keywords": ["personal safety app", "emergency alert", "women safety"],
        "competitor_name_check": "SafeHer",
        "known_company_with_same_name": None,
        "confidence": 0.9,
    }
    model = IdeaUnderstandingModel.model_validate(raw)
    assert model.idea_type == "descriptive_idea"
    assert len(model.market_queries) == 3
    assert len(model.trends_keywords) >= 2


# ─────────────────────────────────────────────
# 2. Relevance & Quality Filter Tests
# ─────────────────────────────────────────────

def test_relevance_filter_drops_tax_and_generic_ai():
    """Relevance filter drops tax filing, job boards, generic AI 50 listicles, and keeps vertical hits."""
    understanding = {
        "category": "AI precision agriculture crop diagnostics",
        "problem_domain": "Early detection of crop blight and plant diseases using mobile camera",
        "target_customers": ["Farmers", "Agronomists"],
    }

    raw_items = [
        {
            "query": "precision agriculture market size 2026",
            "title": "Quick ITR Filing Online 2024-25 - Tax2Win Income Tax Portal",
            "href": "https://tax2win.in/efile-income-tax-return?utm_source=google",
            "body": "File your income tax return ITR-1 and ITR-2 online in 4 minutes with maximum tax refund.",
        },
        {
            "query": "precision agriculture market size 2026",
            "title": "Forbes 2026 AI 50 List: The Top Artificial Intelligence Startups",
            "href": "https://www.forbes.com/lists/ai50/?utm_medium=cpc",
            "body": "Our annual list of the most promising artificial intelligence companies spanning robotics and LLMs.",
        },
        {
            "query": "precision agriculture market size 2026",
            "title": "Smart Agriculture Market Size to Hit $29.8 Billion by 2030, CAGR 12.4%",
            "href": "https://www.grandviewresearch.com/industry-analysis/smart-agriculture-market",
            "body": "The global smart agriculture market size was valued at USD 18.2 billion in 2025 and is projected to expand at a CAGR of 12.4% driven by precision crop diagnostics.",
        },
        {
            "query": "precision agriculture market size 2026",
            "title": "Smart Agriculture Market Size to Hit $29.8 Billion by 2030, CAGR 12.4%",
            "href": "https://www.grandviewresearch.com/industry-analysis/smart-agriculture-market?utm_source=twitter",
            "body": "Duplicate URL test with tracking parameters.",
        },
        {
            "query": "precision agriculture market size 2026",
            "title": "Agriculture AI Jobs - Indeed Careers",
            "href": "https://www.indeed.com/jobs/agriculture-ai",
            "body": "Search 450 Agriculture AI jobs on Indeed. Apply to Research Scientist, Agronomist, and more.",
        },
    ]

    filtered, is_thin, gaps = filter_and_rank_results(raw_items, understanding, max_keep=8)

    # Assertions
    titles = [f["title"] for f in filtered]
    assert not any("Quick ITR" in t for t in titles)
    assert not any("Forbes 2026 AI 50" in t for t in titles)
    assert not any("Indeed" in t for t in titles)
    assert any("Grandview" in f["url"].lower() or "smart agriculture" in t.lower() for t, f in zip(titles, filtered))
    assert len(filtered) == 1  # Grandview kept, duplicate removed, 3 rejected
    assert is_thin is True  # Only 1 survived, so < 2 means thin data flagged
    assert len(gaps) > 0


def test_relevance_filter_stale_detection():
    """Stale results clearly dated pre-2023 with no recent year are rejected."""
    assert is_stale_result("Report published in 2018 regarding outdated 2017 farm trends.", "https://example.com/2018/04/report") is True
    assert is_stale_result("Market sized in 2025 with forecasts through 2030.", "https://example.com/market-report") is False


def test_url_normalization_and_deduplication():
    """Normalized URLs strip tracking params, www, and trailing slashes."""
    u1 = "https://www.Example.com/research/crop-ai/?utm_source=newsletter&utm_medium=email"
    u2 = "http://example.com/research/crop-ai"
    assert normalize_url(u1) == normalize_url(u2)


# ─────────────────────────────────────────────
# 3. Subtask Classification & Proxy Tests
# ─────────────────────────────────────────────

def test_subtask_classification():
    """Classifies offline fieldwork vs analysis vs desk research accurately."""
    assert classify_subtask("Conduct primary research (surveys/interviews) with 30+ farmers") == "human_fieldwork"
    assert classify_subtask("In-person customer interviews with 15 local shopkeepers") == "human_fieldwork"
    assert classify_subtask("Door-to-door physical survey across rural districts") == "human_fieldwork"
    assert classify_subtask("Recommended Founder Validation Step (Post-AI): Sign 5 pilot LOIs") == "human_fieldwork"
    assert classify_subtask("TAM and SAM calculation with CAGR forecasting") == "desk_research"
    assert classify_subtask("Competitor pricing and feature matrix benchmarking") == "desk_research"
    assert classify_subtask("SWOT analysis and positioning strategy") == "analysis"
    assert classify_subtask("3-year pro-forma financial model and unit economics") == "analysis"


def test_subtask_proxy_substitution():
    """Human fieldwork is substituted with an executable autonomous desk research proxy."""
    fieldwork = "Conduct surveys and interviews with 30+ farmers across Maharashtra"
    proxy = create_desk_proxy_for_fieldwork(fieldwork, "smart farming agritech")
    assert "interview 30+" not in proxy.lower()
    assert "farmer" in proxy.lower() or "agricultural" in proxy.lower()
    assert any(term in proxy.lower() for term in ("analyze", "synthesize", "benchmark"))


@pytest.mark.asyncio
async def test_node_decompose_fieldwork_substitution():
    """Workflow decomposition node extracts founder fieldwork and substitutes proxies."""
    mock_llm_tasks = {
        "tasks": [
            "Task 1: TAM and SAM market sizing",
            "Task 2: Competitor benchmarking",
            "Task 3: Conduct primary interviews with 30+ farmers",
            "Task 4: Unit economics and pricing strategy",
            "Task 5: SWOT analysis",
        ]
    }
    with patch("agent.workflow.safe_json_parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = mock_llm_tasks
        state: StartupState = {"idea": "AgroMind AI", "session_id": "test_s1", "language": "English"}
        out = await node_decompose_idea(state)

        tasks = out["tasks"]
        validation_steps = out["founder_validation_steps"]

        assert len(validation_steps) == 1
        assert "[Founder Fieldwork]" in validation_steps[0]
        assert "30+ farmers" in validation_steps[0]
        # Autonomous task 3 must be replaced by a desk proxy
        assert "interviews with 30+ farmers" not in tasks[2]
        assert "Task 3: Analyze" in tasks[2]


# ─────────────────────────────────────────────
# 4. Query Routing & Collision Check Tests
# ─────────────────────────────────────────────

def test_research_market_uses_understanding_queries():
    """research_market executes category queries when provided and filters output."""
    mock_queries = [
        "smart farming market size 2026",
        "precision agritech industry CAGR report",
    ]
    mock_understanding = {
        "category": "smart farming agritech",
        "problem_domain": "crop diagnostics",
        "target_customers": ["farmers"],
    }

    mock_search_items = [
        {
            "query": "smart farming market size 2026",
            "title": "Smart Farming Market Projected to Reach $32B by 2030",
            "url": "https://agritech-reports.com/smart-farming-2026",
            "snippet": "Valued at $14.5B in 2025, smart farming sector is growing at 11.8% CAGR.",
        }
    ]

    with patch("agent.tools.search_web_items", return_value=mock_search_items):
        formatted, is_thin, gaps = research_market(mock_queries, mock_understanding, return_meta=True)
        assert "32B" in formatted
        assert "Query: smart farming market size 2026" in formatted


def test_research_competitors_same_name_collision_note():
    """Same-name brand detection adds prominent notice to competitor analysis."""
    mock_queries = ["precision crop health competitors"]
    mock_understanding = {
        "category": "precision agriculture",
        "problem_domain": "crop diagnostics",
        "competitor_name_check": "AgroMind",
        "known_company_with_same_name": "AgroMind Ltd, an existing farm IoT software provider in Europe",
    }

    with patch("agent.tools.search_web_items", return_value=[]):
        formatted, is_thin, gaps = research_competitors(
            mock_queries, mock_understanding, competitor_name_check="AgroMind", return_meta=True
        )
        assert "Note: An existing company named 'AgroMind' already operates in this space" in formatted


# ─────────────────────────────────────────────
# 5. Error Tolerance & Graceful Degradation
# ─────────────────────────────────────────────

def test_single_search_query_exception_tolerance():
    """A single throwing query in research_market does not crash the node."""
    def side_effect_search(q, max_results=3):
        if "exploding_query" in q:
            raise RuntimeError("DuckDuckGo rate limit or network drop")
        return [
            {
                "query": q,
                "title": "Valid Market Size Report",
                "url": "https://validmarket.org/report",
                "snippet": "Global market stands at $10B with 15% CAGR.",
            }
        ]

    with patch("agent.tools.search_web_items", side_effect=side_effect_search):
        formatted, is_thin, gaps = research_market(
            ["exploding_query", "valid market report 2026"],
            {"category": "valid market", "problem_domain": "market size"},
            return_meta=True
        )
        assert "Valid Market Size Report" in formatted
        assert "10B" in formatted


@pytest.mark.asyncio
async def test_node_understand_idea_safe_repair_and_failure():
    """Idea understanding triggers safe_json_parse with IdeaUnderstandingModel and validates output."""
    valid_res = {
        "idea_type": "named_product",
        "category": "B2B accounts payable invoice automation SaaS",
        "problem_domain": "Automating supplier invoice matching and OCR extraction",
        "target_customers": ["Finance teams", "CFOs"],
        "region_focus": "global",
        "market_queries": ["accounts payable automation market size 2026", "invoice processing SaaS growth CAGR", "AP automation software demand"],
        "competitor_queries": ["top invoice automation startups", "accounts payable software competitors", "best invoice OCR tools"],
        "customer_voice_queries": ["invoice automation software reddit reviews", "AP processing complaints"],
        "trends_keywords": ["invoice automation", "accounts payable", "AP automation"],
        "competitor_name_check": "InvoiceFlow",
        "known_company_with_same_name": None,
        "confidence": 0.98,
    }

    with patch("agent.workflow.safe_json_parse", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = valid_res
        state: StartupState = {"idea": "InvoiceFlow", "session_id": "sess_inv", "language": "English"}
        out = await node_understand_idea(state)

        assert "idea_understanding" in out
        assert out["idea_understanding"]["category"] == "B2B accounts payable invoice automation SaaS"
        assert out["research_plan"]["idea_type"] == "named_product"

