# main.py
# AutoStartup AI — FastAPI Backend Server

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

AGENT_TIMEOUT_SECONDS = int(os.getenv("AGENT_TIMEOUT_SECONDS", "600"))

# Load environment variables
load_dotenv()

# Validate API key
if not os.getenv("GROQ_API_KEY"):
    print("⚠️  WARNING: GROQ_API_KEY not set. Please create a .env file.")

# Initialize database on startup
from agent.memory import init_database, get_all_plans, get_plan_by_id
init_database()

# Import agent components
from agent.workflow import run_agent, event_queues

import uuid

# ─────────────────────────────────────────────
# FastAPI App Setup
# ─────────────────────────────────────────────

app = FastAPI(
    title="AutoStartup AI",
    description="Autonomous AI agent for complete startup plan generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────

class IdeaRequest(BaseModel):
    idea: str

    model_config = {"json_schema_extra": {"example": {"idea": "AI app for farmers"}}}


# ─────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    """Serve the main frontend HTML."""
    html_path = Path("frontend/index.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse("<h1>AutoStartup AI — Frontend not found</h1>", status_code=404)


@app.post("/api/generate")
async def generate_startup_plan(request: IdeaRequest):
    """
    Main endpoint: Takes a startup idea and streams the agent's
    12-step autonomous workflow as Server-Sent Events (SSE).
    """
    idea = request.idea.strip()
    if not idea:
        raise HTTPException(status_code=400, detail="Startup idea cannot be empty.")
    if len(idea) > 500:
        raise HTTPException(status_code=400, detail="Idea too long (max 500 chars).")

    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    event_queues[session_id] = queue

    async def event_generator():
        """Async generator that yields SSE events from the agent."""
        # Emit initial event
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'idea': idea})}\n\n"

        # Start the agent workflow in the background
        task = asyncio.create_task(run_agent(idea, session_id))

        try:
            while True:
                try:
                    # Wait for next event (timeout = configured value)
                    event = await asyncio.wait_for(queue.get(), timeout=AGENT_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Agent timed out after {AGENT_TIMEOUT_SECONDS} seconds.'})}\n\n"
                    break

                if event is None:
                    # Sentinel: agent finished
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break

                yield f"data: {json.dumps(event)}\n\n"

        finally:
            # Clean up
            if session_id in event_queues:
                del event_queues[session_id]
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/history")
async def get_history():
    """Return all previously generated startup plans (summary list)."""
    plans = get_all_plans()
    return {"plans": plans, "count": len(plans)}


@app.get("/api/idea/{plan_id}")
async def get_idea(plan_id: str):
    """Return the full details of a specific startup plan."""
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return plan


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "AutoStartup AI",
        "groq_api_key_set": bool(os.getenv("GROQ_API_KEY")),
    }


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    print("\n" + "=" * 55)
    print("  🚀  AutoStartup AI — Starting Server")
    print(f"  🌐  Open: http://localhost:{port}")
    print(f"  📖  API Docs: http://localhost:{port}/docs")
    print("=" * 55 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
