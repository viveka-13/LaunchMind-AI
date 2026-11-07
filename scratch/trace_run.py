import asyncio
import json
import os
import sys
import sqlite3
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

from agent.workflow import run_agent, event_queues
from agent.memory import get_db_connection

async def trace_workflow():
    session_id = f"trace_{uuid.uuid4().hex[:8]}"
    queue = asyncio.Queue()
    event_queues[session_id] = queue

    events = []
    
    print(f"[*] Starting trace for 'AI Career Guidance' with session_id: {session_id}")
    task = asyncio.create_task(run_agent("AI Career Guidance", session_id, language="en", doc_format="ppt"))

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=120)
            if event is None or (isinstance(event, dict) and event.get("type") == "done"):
                events.append(event)
                break
            events.append(event)
            t = event.get("type")
            if t == "step":
                print(f"[STEP {event.get('step')}] {event.get('title')}")
            elif t == "node_skipped":
                print(f"[SKIPPED] {event.get('node')}: {event.get('reason')}")
            elif t == "node_error":
                print(f"[ERROR] {event.get('node')}: {event.get('reason')}")
        except asyncio.TimeoutError:
            print("[TIMEOUT] Workflow timed out waiting for event")
            break

    await task

    print("\n" + "="*60)
    print("SSE EVENTS CAPTURED:")
    for e in events:
        if isinstance(e, dict):
            etype = e.get("type")
            if etype in ("step", "node_skipped", "node_error", "section", "tasks", "dashboard"):
                print(f" - {etype}: {e.get('title') or e.get('node') or e.get('label') or e.get('message')}")
    print("="*60)

    # Inspect SQLite database
    print("\nSQLITE ROW DUMP:")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, idea, title, plan_data, run_summary, created_at FROM startup_plans ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            plan_id, idea, title, plan_data_str, run_summary_str, created_at = row
            print(f"ID: {plan_id}")
            print(f"Idea: {idea}")
            print(f"Title: {title}")
            print(f"Created At: {created_at}")
            try:
                pd = json.loads(plan_data_str) if plan_data_str else {}
                print("\nPlan Data Fields & Lengths:")
                for k, v in pd.items():
                    print(f"  {k}: {type(v).__name__} (len={len(v) if hasattr(v, '__len__') else 'N/A'})")
            except Exception as e:
                print(f"Plan data parse error: {e}")
                
            try:
                rs = json.loads(run_summary_str) if run_summary_str else {}
                print("\nRun Summary:")
                print(json.dumps(rs, indent=2))
            except Exception as e:
                print(f"Run summary parse error: {e}")

if __name__ == "__main__":
    asyncio.run(trace_workflow())
