import os
import shutil
import sqlite3
import pytest
from starlette.testclient import TestClient

from main import app, event_queues
from agent.memory import (
    get_db_connection,
    delete_plan_by_id,
    deduplicate_history,
    cleanup_plan_files,
    save_startup_plan,
)

client = TestClient(app)


def test_delete_plan_cascades_children_and_files(tmp_path):
    """Test that deleting a plan deletes practice sessions, turns, audio records, and disk files."""
    plan_id = "test-cascade-plan-123"
    
    # Setup test plan in DB
    save_startup_plan(plan_id, "Test Cascade Idea", "Test Cascade Title", {"summary": "test"})
    
    # Insert child rows
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pitch_sessions (id, plan_id, persona, messages, score)
            VALUES (?, ?, ?, ?, ?)
        """, ("session-123", plan_id, "sarah_chen", "[]", 85))
        cursor.execute("""
            INSERT INTO practice_turns (id, session_id, turn_index, question, answer, score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("turn-123", "session-123", 1, "What is your moat?", "Network effects", 90))
        cursor.execute("""
            INSERT INTO audio_generations (id, plan_id, file_path, status)
            VALUES (?, ?, ?, ?)
        """, ("audio-123", plan_id, f"./data/audio/{plan_id}_narration.mp3", "completed"))
        cursor.execute("""
            INSERT INTO export_history (id, plan_id, export_type, export_url)
            VALUES (?, ?, ?, ?)
        """, ("export-123", plan_id, "google_docs", "https://docs.google.com/test"))

    # Create dummy files on disk inside data/
    data_dir = os.path.abspath("./data")
    os.makedirs(os.path.join(data_dir, "presentations"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "documents"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "pitch", plan_id), exist_ok=True)

    dummy_ppt = os.path.join(data_dir, "presentations", f"{plan_id}.pptx")
    dummy_pdf = os.path.join(data_dir, "documents", f"{plan_id}.pdf")
    dummy_audio = os.path.join(data_dir, "audio", f"{plan_id}_narration.mp3")
    dummy_transcript = os.path.join(data_dir, "pitch", plan_id, "simulation_transcript.json")

    with open(dummy_ppt, "w") as f: f.write("ppt content")
    with open(dummy_pdf, "w") as f: f.write("pdf content")
    with open(dummy_audio, "w") as f: f.write("audio content")
    with open(dummy_transcript, "w") as f: f.write("{}")

    assert os.path.exists(dummy_ppt)
    assert os.path.exists(dummy_pdf)
    assert os.path.exists(dummy_audio)
    assert os.path.exists(dummy_transcript)

    # Perform deletion
    success, msg = delete_plan_by_id(plan_id)
    assert success is True

    # Verify DB rows are all deleted
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM startup_plans WHERE id = ?", (plan_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM pitch_sessions WHERE plan_id = ?", (plan_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM practice_turns WHERE session_id = 'session-123'")
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM audio_generations WHERE plan_id = ?", (plan_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM export_history WHERE plan_id = ?", (plan_id,))
        assert cursor.fetchone()[0] == 0

    # Verify files on disk are removed
    assert not os.path.exists(dummy_ppt)
    assert not os.path.exists(dummy_pdf)
    assert not os.path.exists(dummy_audio)
    assert not os.path.exists(dummy_transcript)
    assert not os.path.exists(os.path.join(data_dir, "pitch", plan_id))


def test_delete_nonexistent_plan_returns_404():
    """Verify that deleting a nonexistent plan returns 404."""
    resp = client.delete("/api/history/non-existent-uuid-99999")
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"] == "Plan not found."


def test_delete_in_flight_plan_returns_409():
    """Verify that deleting a plan whose generation is currently in-flight returns 409."""
    in_flight_id = "in-flight-session-888"
    event_queues[in_flight_id] = "dummy_queue"
    try:
        resp = client.delete(f"/api/history/{in_flight_id}")
        assert resp.status_code == 409
        assert "currently running" in resp.json()["detail"].lower()
    finally:
        if in_flight_id in event_queues:
            del event_queues[in_flight_id]


def test_path_traversal_protection():
    """Verify that cleanup_plan_files never deletes files outside the data directory."""
    outside_file = os.path.abspath("./tests/safe_test_marker.tmp")
    with open(outside_file, "w") as f:
        f.write("DO NOT DELETE")

    try:
        # Attempt path traversal via extra_paths
        traversal_attempts = [
            "../../etc/passwd",
            outside_file,
            f"../{os.path.basename(outside_file)}",
        ]
        removed = cleanup_plan_files("any-plan-id", extra_paths=traversal_attempts)
        assert outside_file not in removed
        assert os.path.exists(outside_file), "File outside data/ was deleted by path traversal!"
    finally:
        if os.path.exists(outside_file):
            os.remove(outside_file)


def test_delete_plan_owner_isolation():
    """Verify that a plan owned by user_a cannot be deleted by user_b."""
    plan_id = "owner-test-plan-456"
    save_startup_plan(plan_id, "Owner Test Idea", "Owner Title", {}, owner_id="user_a")

    # user_b attempts delete -> 404 (does not disclose plan exists)
    resp = client.delete(f"/api/history/{plan_id}", headers={"X-User-Id": "user_b"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Plan not found."

    # user_a attempts delete -> 200 success
    resp_owner = client.delete(f"/api/history/{plan_id}", headers={"X-User-Id": "user_a"})
    assert resp_owner.status_code == 200
    assert resp_owner.json()["status"] == "ok"


def test_frontend_contract_matches_api():
    """Verify that the frontend's fetch contract (URL /api/history/{id}, method DELETE) succeeds on API."""
    plan_id = "contract-test-plan-789"
    save_startup_plan(plan_id, "Contract Test", "Contract Title", {})

    resp = client.delete(f"/api/history/{plan_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["deleted_id"] == plan_id
