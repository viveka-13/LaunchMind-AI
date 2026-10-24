# tests/test_group1_foundation.py
# Comprehensive tests for Group 1: Items 10, 11, 12, 13

import os
import sqlite3
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel, ValidationError

# Item 13: Database
from agent.memory import (
    init_db,
    get_db_connection,
    save_startup_plan,
    get_plan_by_id,
    DatabaseError,
)

# Item 10: LLM client & resilience
from agent.llm_client import (
    llm_call,
    LLMCallError,
    LLMResult,
    is_retryable,
    record_failure,
    record_success,
    get_consecutive_failures,
    reset_circuit_breaker,
)
from agent.workflow import node_boundary, safe_json_parse, StartupState

# Item 11: Validation & Sanitization
from agent.sanitizer import sanitize_html, sanitize_svg
from agent.models_pydantic import TaskDecompositionModel, ResearchBriefModel

# Item 12: Language
from agent.language import validate_language, SUPPORTED_LANGUAGES
from main import IdeaRequest


# ─────────────────────────────────────────────
# Item 13: Database Tests
# ─────────────────────────────────────────────

def test_database_init_and_migrations(tmp_path):
    test_db = str(tmp_path / "test_history.db")
    with patch("agent.memory.DB_PATH", test_db):
        init_db()

        # Connect and verify tables & columns
        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Check schema version
        cursor.execute("SELECT version FROM schema_version")
        versions = [r[0] for r in cursor.fetchall()]
        assert 3 in versions

        # Check columns on startup_plans
        cursor.execute("PRAGMA table_info(startup_plans)")
        cols = {r[1] for r in cursor.fetchall()}
        assert "run_summary" in cols
        assert "owner_id" in cols
        conn.close()


def test_database_context_rollback_on_error(tmp_path):
    test_db = str(tmp_path / "test_history.db")
    with patch("agent.memory.DB_PATH", test_db):
        init_db()

        with pytest.raises(DatabaseError):
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO startup_plans (id, idea, title) VALUES (?, ?, ?)",
                    ("plan-err", "Test", "Test"),
                )
                raise RuntimeError("Forced failure inside transaction")

        # Verify record was rolled back
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM startup_plans WHERE id = ?", ("plan-err",))
            assert cursor.fetchone() is None


def test_database_foreign_keys_and_wal(tmp_path):
    test_db = str(tmp_path / "test_history.db")
    with patch("agent.memory.DB_PATH", test_db):
        init_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            assert cursor.fetchone()[0] == 1
            cursor.execute("PRAGMA journal_mode")
            assert cursor.fetchone()[0].upper() == "WAL"


# ─────────────────────────────────────────────
# Item 10: LLM Client & Retries
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_call_success():
    mock_resp = MagicMock()
    mock_resp.content = "Successful response"
    mock_resp.response_metadata = {
        "model_name": "test-model",
        "token_usage": {"prompt_tokens": 10, "completion_tokens": 20},
        "finish_reason": "stop",
    }

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_resp)

    with patch("agent.llm_client._create_llm_client", return_value=mock_llm):
        result = await llm_call(
            [{"role": "user", "content": "hello"}],
            node="test_node",
        )
        assert isinstance(result, LLMResult)
        assert result.text == "Successful response"
        assert result.attempts == 1
        assert result.input_tokens == 10
        assert result.output_tokens == 20


@pytest.mark.asyncio
async def test_llm_call_retry_on_retryable_error():
    mock_resp = MagicMock()
    mock_resp.content = "Eventually succeeded"
    mock_resp.response_metadata = {"finish_reason": "stop"}

    class TransientError(Exception):
        pass

    mock_llm = MagicMock()
    # Fail twice with 503/timeout then succeed
    mock_llm.ainvoke = AsyncMock(side_effect=[
        TransientError("503 Service Unavailable"),
        TransientError("Connection timeout"),
        mock_resp,
    ])

    with patch("agent.llm_client._create_llm_client", return_value=mock_llm), \
         patch("agent.llm_client._get_backoff_base", return_value=0.01), \
         patch("agent.llm_client._get_max_attempts", return_value=4):
        result = await llm_call("test prompt", node="retry_node")
        assert result.text == "Eventually succeeded"
        assert result.attempts == 3


@pytest.mark.asyncio
async def test_llm_call_no_retry_on_auth_error():
    class AuthError(Exception):
        pass

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=AuthError("401 Unauthorized: Invalid API key"))

    with patch("agent.llm_client._create_llm_client", return_value=mock_llm):
        with pytest.raises(LLMCallError) as exc_info:
            await llm_call("test", node="auth_node")
        assert exc_info.value.retryable is False
        assert exc_info.value.attempts == 1


@pytest.mark.asyncio
async def test_llm_call_circuit_breaker():
    sid = "session-cb-test"
    reset_circuit_breaker(sid)

    # Record 5 consecutive failures
    for _ in range(5):
        record_failure(sid)

    assert get_consecutive_failures(sid) == 5

    with pytest.raises(LLMCallError) as exc_info:
        await llm_call("test", node="cb_node", session_id=sid)
    assert exc_info.value.reason == "provider_unavailable"
    reset_circuit_breaker(sid)


@pytest.mark.asyncio
async def test_node_boundary_isolation():
    @node_boundary("failing_node")
    async def failing_node(state: StartupState) -> dict:
        raise LLMCallError("failing_node", "Simulated failure", retryable=False, attempts=1)

    initial_state = {"session_id": "s1", "errors": [], "failed_nodes": []}
    output = await failing_node(initial_state)

    assert "errors" in output
    assert len(output["errors"]) == 1
    assert output["errors"][0]["node"] == "failing_node"
    assert "failing_node" in output["failed_nodes"]


@pytest.mark.asyncio
async def test_node_boundary_skips_missing_dependency():
    @node_boundary("dependent_node", required_fields=["solution_strategy"])
    async def dependent_node(state: StartupState) -> dict:
        return {"features": "won't run"}

    # Pass state without solution_strategy
    state = {"session_id": "s2", "solution_strategy": ""}
    output = await dependent_node(state)

    assert "skipped_nodes" in output
    assert "dependent_node" in output["skipped_nodes"]


# ─────────────────────────────────────────────
# Item 11: Validation and Sanitization
# ─────────────────────────────────────────────

def test_sanitize_html_xss():
    dirty = '<p>Safe Text</p><script>alert("xss")</script><a href="javascript:steal()">Click</a><img src="x" onerror="boom()">'
    cleaned = sanitize_html(dirty)
    assert "<script>" not in cleaned
    assert "alert" not in cleaned
    assert "javascript:" not in cleaned
    assert "onerror" not in cleaned
    assert "Safe Text" in cleaned


def test_sanitize_svg_strips_scripts_and_events():
    malicious_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        '<script>alert("bad")</script>'
        '<foreignObject><body><script>nested()</script></body></foreignObject>'
        '<rect width="100" height="100" fill="blue"/>'
        '</svg>'
    )
    cleaned = sanitize_svg(malicious_svg)
    assert "<script>" not in cleaned
    assert "onload" not in cleaned
    assert "<foreignObject>" not in cleaned
    assert '<rect width="100" height="100" fill="blue"/>' in cleaned or 'fill="blue"' in cleaned


def test_sanitize_svg_rejects_xxe_entity():
    xxe_svg = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE svg ['
        '<!ENTITY xxe SYSTEM "file:///etc/passwd">'
        ']>'
        '<svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>'
    )
    # defusedxml will raise an entity forbidden error, sanitize_svg rejects it
    with pytest.raises(ValueError) as exc:
        sanitize_svg(xxe_svg)
    assert "EntitiesForbidden" in str(exc.value) or "Failed to parse SVG" in str(exc.value)


@pytest.mark.asyncio
async def test_safe_json_parse_repair():
    # First response invalid JSON, second repair response valid JSON
    bad_json = '{"tasks": ["Task 1", broken json...'
    good_json = '{"tasks": ["Task 1: Market Research", "Task 2: Competitor Analysis"]}'

    with patch("agent.workflow.llm_invoke", AsyncMock(side_effect=[bad_json, good_json])):
        result = await safe_json_parse(
            "dummy prompt",
            model_cls=TaskDecompositionModel,
            node="test_repair",
        )
        assert "tasks" in result
        assert len(result["tasks"]) == 2
        assert result["tasks"][0] == "Task 1: Market Research"


# ─────────────────────────────────────────────
# Item 12: Language
# ─────────────────────────────────────────────

def test_language_validation_supported():
    assert validate_language("en") == "English"
    assert validate_language("English") == "English"
    assert validate_language("es") == "Spanish"
    assert validate_language("Telugu") == "Telugu"
    assert validate_language("hi") == "Hindi"


def test_language_validation_unsupported():
    with pytest.raises(ValueError):
        validate_language("klingon")


def test_idea_request_model_validation():
    # Valid
    req = IdeaRequest(idea="My startup", language="Spanish", doc_format="pdf")
    assert req.language == "Spanish"

    # Invalid raises ValidationError (which FastAPI turns into HTTP 422)
    with pytest.raises(ValidationError):
        IdeaRequest(idea="My startup", language="non_existent_lang")
