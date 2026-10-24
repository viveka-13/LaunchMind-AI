# tests/test_group2_integrations.py
# Comprehensive tests for Group 2: Items 5, 6, 7 and Items 2, 3, 4 (Real integrations)

import os
import sqlite3
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Item 5: Company Research
from agent.company_research import (
    CrunchbaseProvider,
    SecEdgarProvider,
    WikidataProvider,
    fetch_company_research,
)

# Item 6: Google Trends
from agent.trends_service import (
    calculate_direction,
    extract_keywords,
    fetch_google_trends,
    _get_cached_trends,
    _save_cached_trends,
)

# Item 7: Sentiment
from agent.sentiment_service import (
    RedditSentimentSource,
    WebSearchSentimentSource,
    analyze_sentiment,
)

# Items 2, 3, 4: Exporters
from agent.export.google_docs import export_to_google_docs
from agent.export.google_slides import export_to_google_slides
from agent.export.notion_export import export_to_notion
from agent.export.export_manager import handle_export


# ─────────────────────────────────────────────
# Item 5: Company Research Tests
# ─────────────────────────────────────────────

def test_crunchbase_skipped_when_no_key():
    with patch.dict(os.environ, {}, clear=True):
        cb = CrunchbaseProvider(api_key=None)
        res = cb.search_company("Stripe")
        assert res["status"] == "skipped"
        assert "CRUNCHBASE_API_KEY not configured" in res["reason"]
        assert res["data"] is None


def test_crunchbase_ok_when_data_returned():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "properties": {
            "name": "Stripe",
            "funding_total": {"value_usd": 2200000000},
            "num_funding_rounds": 14,
            "headquarters_address": "San Francisco, CA",
            "num_employees_enum": "c_01001_05000",
            "short_description": "Financial infrastructure for the internet",
        }
    }
    with patch("requests.get", return_value=mock_response):
        cb = CrunchbaseProvider(api_key="test-cb-key")
        res = cb.search_company("Stripe")
        assert res["status"] == "ok"
        assert res["data"]["name"] == "Stripe"
        assert res["data"]["source"] == "crunchbase"
        assert res["data"]["total_funding_usd"] == 2200000000


def test_sec_edgar_ambiguous_entity_resolution():
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Return 10 matching entries to simulate ambiguity
    mock_response.json.return_value = {
        str(i): {"title": f"ABC Technology Holdings {i}", "ticker": f"AB{i}", "cik_str": 1000 + i}
        for i in range(10)
    }
    with patch("requests.get", return_value=mock_response):
        edgar = SecEdgarProvider()
        res = edgar.search_company("technology")
        assert res["status"] == "ok"
        assert res["data"] is None
        assert "Ambiguous match" in res["reason"]


def test_sec_edgar_success():
    mock_tickers = MagicMock()
    mock_tickers.status_code = 200
    mock_tickers.json.return_value = {
        "0": {"title": "Apple Inc.", "ticker": "AAPL", "cik_str": 320193}
    }

    mock_sub = MagicMock()
    mock_sub.status_code = 200
    mock_sub.json.return_value = {
        "name": "Apple Inc.",
        "entityType": "operating",
        "sicDescription": "ELECTRONIC COMPUTERS",
        "fiscalYearEnd": "0930",
        "stateOfIncorporation": "CA",
    }

    with patch("requests.get", side_effect=[mock_tickers, mock_sub]):
        edgar = SecEdgarProvider()
        res = edgar.search_company("AAPL")
        assert res["status"] == "ok"
        assert res["data"]["ticker"] == "AAPL"
        assert res["data"]["sic_description"] == "ELECTRONIC COMPUTERS"
        assert res["data"]["source"] == "sec_edgar"


def test_wikidata_success():
    mock_search = MagicMock()
    mock_search.status_code = 200
    mock_search.json.return_value = {
        "search": [
            {"id": "Q312", "label": "Apple Inc.", "description": "American technology company"}
        ]
    }

    mock_wiki = MagicMock()
    mock_wiki.status_code = 200
    mock_wiki.json.return_value = {
        "extract": "Apple Inc. is an American multinational corporation and technology company."
    }

    with patch("requests.get", side_effect=[mock_search, mock_wiki]):
        wiki = WikidataProvider()
        res = wiki.search_company("Apple")
        assert res["status"] == "ok"
        assert res["data"]["wikidata_id"] == "Q312"
        assert "multinational" in res["data"]["summary"]
        assert res["data"]["source"] == "wikidata_wikipedia"


# ─────────────────────────────────────────────
# Item 6: Google Trends Tests
# ─────────────────────────────────────────────

def test_trends_direction_calculation():
    assert calculate_direction([10, 20, 30, 40, 50, 60]) == "growing"
    assert calculate_direction([90, 80, 70, 60, 50, 40]) == "declining"
    assert calculate_direction([50, 52, 49, 51, 50, 50]) == "flat"


def test_trends_caching(tmp_path):
    test_db = str(tmp_path / "trends_test.db")
    with patch("agent.trends_service.DB_PATH", test_db):
        cached_payload = {
            "keywords": ["ai", "agents"],
            "direction": "growing",
            "series_12m": {"ai": [20, 40, 60]},
        }
        _save_cached_trends("ai+agents", "12m_and_5y", cached_payload)
        retrieved = _get_cached_trends("ai+agents", "12m_and_5y")
        assert retrieved is not None
        assert retrieved["direction"] == "growing"


def test_trends_rate_limit_429():
    mock_trend = MagicMock()
    mock_trend.build_payload.side_effect = Exception("The request failed: Google returned a response with code 429")
    with patch("pytrends.request.TrendReq", return_value=mock_trend), \
         patch("agent.trends_service._get_cached_trends", return_value=None):
        res = fetch_google_trends("ai autonomous agent")
        assert res["status"] == "failed"
        assert "HTTP 429" in res["reason"]
        assert res["data"] is None


# ─────────────────────────────────────────────
# Item 7: Sentiment Analysis Tests
# ─────────────────────────────────────────────

def test_reddit_source_skipped_when_no_credentials():
    with patch.dict(os.environ, {}, clear=True):
        src = RedditSentimentSource()
        assert src.is_configured() is False
        assert src.fetch_posts("anything") == []


@pytest.mark.asyncio
async def test_sentiment_insufficient_data():
    # When fewer than 5 posts found
    with patch.object(RedditSentimentSource, "fetch_posts", return_value=[]), \
         patch.object(WebSearchSentimentSource, "fetch_posts", return_value=[{"text": "Sample 12345678901234567890", "url": "http://x.com", "source": "web"}]):
        res = await analyze_sentiment("niche startup")
        assert res["status"] == "ok"
        assert res["data"]["verdict"] == "insufficient data"
        assert res["data"]["sample_size"] == 1


@pytest.mark.asyncio
async def test_sentiment_vader_aggregation():
    sample_posts = [
        {"text": "I absolutely love this product, it is amazing and fantastic!", "url": "http://a.com", "source": "web"},
        {"text": "Great software with stellar features and great support.", "url": "http://b.com", "source": "web"},
        {"text": "Truly helpful and very reliable every single day.", "url": "http://c.com", "source": "web"},
        {"text": "Awful experience, constantly crashed and lost my data.", "url": "http://d.com", "source": "web"},
        {"text": "Standard tool, nothing special but works fine.", "url": "http://e.com", "source": "web"},
        {"text": "Highly recommended for all entrepreneurs and teams.", "url": "http://f.com", "source": "web"},
    ]

    mock_llm_res = MagicMock()
    mock_llm_res.text = json.dumps({
        "praise_themes": ["Great product and features"],
        "complaint_themes": ["Crashes and data loss"],
    })

    with patch.object(RedditSentimentSource, "fetch_posts", return_value=[]), \
         patch.object(WebSearchSentimentSource, "fetch_posts", return_value=sample_posts), \
         patch("agent.sentiment_service.llm_call", AsyncMock(return_value=mock_llm_res)):
        res = await analyze_sentiment("popular app")
        assert res["status"] == "ok"
        assert res["data"]["sample_size"] == 6
        assert res["data"]["counts"]["positive"] >= 3
        assert res["data"]["overall_sentiment"] == "positive"
        assert len(res["data"]["praise_themes"]) > 0


# ─────────────────────────────────────────────
# Items 2, 3, 4: Exporters Tests
# ─────────────────────────────────────────────

def test_google_docs_skipped_when_no_credentials():
    with patch("agent.export.google_docs.get_google_credentials", return_value=(None, None, "Credentials missing")):
        res = export_to_google_docs("plan-1", {"startup_title": "Test Plan"})
        assert res["status"] == "skipped"
        assert "Credentials missing" in res["reason"]
        assert res["url"] is None


def test_google_docs_success_with_mock():
    mock_docs = MagicMock()
    mock_docs.documents().create().execute.return_value = {"documentId": "mock-doc-123"}
    mock_docs.documents().batchUpdate().execute.return_value = {}

    with patch("agent.export.google_docs.get_google_credentials", return_value=(MagicMock(), "oauth2", None)), \
         patch("agent.export.google_docs.build", return_value=mock_docs):
        res = export_to_google_docs("plan-1", {"startup_title": "Test Plan"})
        assert res["status"] == "ok"
        assert "https://docs.google.com/document/d/mock-doc-123/edit" in res["url"]


def test_google_slides_skipped_when_no_credentials():
    with patch("agent.export.google_slides.get_google_credentials", return_value=(None, None, "Credentials missing")):
        res = export_to_google_slides("plan-1", {"startup_title": "Test Pitch"})
        assert res["status"] == "skipped"
        assert res["url"] is None


def test_google_slides_success_with_mock():
    mock_slides = MagicMock()
    mock_slides.presentations().create().execute.return_value = {"presentationId": "mock-pres-456"}
    mock_slides.presentations().batchUpdate().execute.return_value = {}

    with patch("agent.export.google_slides.get_google_credentials", return_value=(MagicMock(), "oauth2", None)), \
         patch("agent.export.google_slides.build", return_value=mock_slides):
        res = export_to_google_slides("plan-1", {"startup_title": "Test Pitch"})
        assert res["status"] == "ok"
        assert "https://docs.google.com/presentation/d/mock-pres-456/edit" in res["url"]


def test_notion_export_skipped_when_no_key():
    with patch.dict(os.environ, {}, clear=True):
        res = export_to_notion("plan-1", {"startup_title": "Test Notion"})
        assert res["status"] == "skipped"
        assert "NOTION_API_KEY" in res["reason"]
        assert res["url"] is None


def test_notion_export_unshared_parent_page_hint():
    class MockAPIError(Exception):
        def __init__(self):
            self.status = 404
            super().__init__("Could not find page with ID")

    mock_notion = MagicMock()
    mock_notion.pages.create.side_effect = MockAPIError()

    with patch.dict(os.environ, {"NOTION_API_KEY": "secret_key", "NOTION_PARENT_PAGE_ID": "page_123"}), \
         patch("notion_client.Client", return_value=mock_notion):
        res = export_to_notion("plan-1", {"startup_title": "Test Notion"})
        assert res["status"] == "failed"
        assert "Make sure the parent page is shared with the Notion integration" in res["reason"]


def test_notion_export_success_with_mock():
    mock_notion = MagicMock()
    mock_notion.pages.create.return_value = {"id": "page-notion-789", "url": "https://notion.so/page-notion-789"}

    with patch.dict(os.environ, {"NOTION_API_KEY": "secret_key", "NOTION_PARENT_PAGE_ID": "page_123"}), \
         patch("notion_client.Client", return_value=mock_notion):
        res = export_to_notion("plan-1", {"startup_title": "Test Notion"})
        assert res["status"] == "ok"
        assert res["url"] == "https://notion.so/page-notion-789"


def test_export_manager_logging_to_db(tmp_path):
    test_db = str(tmp_path / "export_db.db")
    with patch("agent.memory.DB_PATH", test_db):
        from agent.memory import init_db, save_startup_plan
        init_db()
        save_startup_plan("plan-db-test", "Test Idea", "Test Title", {})

        with patch("agent.export.google_docs.get_google_credentials", return_value=(None, None, "Credentials missing")):
            res = handle_export("plan-db-test", {"startup_title": "Test"}, "google_docs")
            assert res["status"] == "skipped"

        # Check export_history row
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT plan_id, export_type, status, reason FROM export_history WHERE plan_id = ?", ("plan-db-test",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "plan-db-test"
        assert row[1] == "google_docs"
        assert row[2] == "skipped"
        conn.close()
