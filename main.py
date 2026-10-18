# main.py
# AutoStartup AI — FastAPI Backend Server

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

AGENT_TIMEOUT_SECONDS = int(os.getenv("AGENT_TIMEOUT_SECONDS", "600"))

# Load environment variables
load_dotenv()

# Validate API key
if not os.getenv("GROQ_API_KEY"):
    print("[WARNING] GROQ_API_KEY not set. Please create a .env file.")

# Initialize database on startup
from agent.memory import init_database, get_all_plans, get_plan_by_id
from agent.investor_database import init_investor_db
from agent.pitch_practice import generate_pitch_question, evaluate_pitch_answer
init_database()
init_investor_db()

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
    language: str = "English"
    doc_format: str = "ppt"

    model_config = {"json_schema_extra": {"example": {"idea": "AI app for farmers", "language": "English", "doc_format": "ppt"}}}


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
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'idea': idea, 'language': request.language})}\n\n"

        # Start the agent workflow in the background
        task = asyncio.create_task(run_agent(idea, session_id, request.language, request.doc_format))

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


@app.get("/api/critique/{plan_id}")
async def get_critique(plan_id: str):
    """Return only the adversarial review (critique) for a plan."""
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")
    
    critique_data = plan.get("critique", "{}")
    if isinstance(critique_data, str):
        try:
            return json.loads(critique_data)
        except Exception:
            return {"raw_text": critique_data}
    return critique_data


@app.get("/api/download_ppt/{plan_id}")
async def download_ppt(plan_id: str):
    """Download the generated PowerPoint pitch deck."""
    file_path = f"./data/presentations/{plan_id}.pptx"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PPT not found.")
    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=f"Startup_Pitch_{plan_id}.pptx")


@app.get("/api/download_pdf/{plan_id}")
async def download_pdf(plan_id: str):
    """Download the generated PDF business plan."""
    file_path = f"./data/documents/{plan_id}.pdf"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(file_path, media_type="application/pdf", filename=f"Startup_Plan_{plan_id}.pdf")


@app.get("/api/download_word/{plan_id}")
async def download_word(plan_id: str):
    """Download the generated Word document business plan."""
    file_path = f"./data/documents/{plan_id}.docx"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Word Document not found.")
    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=f"Startup_Plan_{plan_id}.docx")


@app.get("/api/download_architecture/{plan_id}")
async def download_architecture(plan_id: str):
    """Download the generated System Architecture HTML graphic."""
    file_path = f"./data/architectures/{plan_id}.html"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Architecture Graphic not found.")
    return FileResponse(file_path, media_type="text/html", filename=f"System_Architecture.html")


@app.get("/api/download_roadmap/{plan_id}")
async def download_roadmap(plan_id: str):
    """Download the generated Business Roadmap SVG graphic."""
    file_path = f"./data/roadmaps/{plan_id}.html"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Roadmap Graphic not found.")
    return FileResponse(file_path, media_type="text/html", filename=f"Business_Roadmap_Workflow.html")


@app.get("/api/download_financial_model/{plan_id}")
async def download_financial_model(plan_id: str):
    """Download the generated Financial Model Excel workbook."""
    file_path = f"./data/financials/{plan_id}.xlsx"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Financial Model not found.")
    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"Financial_Model.xlsx")


@app.get("/api/download_investor_report/{plan_id}")
async def download_investor_report(plan_id: str):
    """Download the generated Investor Readiness Report PDF."""
    file_path = f"./data/documents/investor_report_{plan_id}.pdf"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Investor Report not found.")
    return FileResponse(file_path, media_type="application/pdf", filename=f"Investor_Report_{plan_id}.pdf")



# ─────────────────────────────────────────────
# Fundraising Platform APIs
# ─────────────────────────────────────────────

from pydantic import BaseModel
class PracticeStartReq(BaseModel):
    persona_id: str

class PracticeAnswerReq(BaseModel):
    session_id: str
    answer: str

@app.post("/api/practice/start/{plan_id}")
async def start_pitch_practice(plan_id: str, req: PracticeStartReq):
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    import uuid
    session_id = str(uuid.uuid4())
    
    # Generate first question
    history = []
    question = await generate_pitch_question(
        idea=plan.get("idea", ""),
        core_features=plan.get("core_features", ""),
        revenue_model=plan.get("revenue_model", ""),
        persona_id=req.persona_id,
        history=history
    )
    
    history.append({"role": "investor", "content": question})
    
    # Save to db
    import sqlite3
    conn = sqlite3.connect("./data/startup_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pitch_sessions (id, plan_id, persona, messages) VALUES (?, ?, ?, ?)",
        (session_id, plan_id, req.persona_id, __import__("json").dumps(history))
    )
    conn.commit()
    conn.close()
    
    return {"session_id": session_id, "question": question}

@app.post("/api/practice/answer")
async def answer_pitch_question(req: PracticeAnswerReq):
    import sqlite3
    import json
    
    conn = sqlite3.connect("./data/startup_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT plan_id, persona, messages FROM pitch_sessions WHERE id = ?", (req.session_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
        
    plan_id, persona_id, messages_json = row
    history = json.loads(messages_json)
    
    # The last message was the investor's question
    last_question = history[-1]["content"] if history else ""
    
    # Evaluate answer
    evaluation = await evaluate_pitch_answer(last_question, req.answer)
    
    # Add answer to history
    history.append({"role": "founder", "content": req.answer})
    history.append({"role": "evaluator", "content": json.dumps(evaluation)})
    
    # Generate NEXT question
    plan = get_plan_by_id(plan_id)
    next_question = await generate_pitch_question(
        idea=plan.get("idea", ""),
        core_features=plan.get("core_features", ""),
        revenue_model=plan.get("revenue_model", ""),
        persona_id=persona_id,
        history=history
    )
    history.append({"role": "investor", "content": next_question})
    
    cursor.execute(
        "UPDATE pitch_sessions SET messages = ? WHERE id = ?",
        (json.dumps(history), req.session_id)
    )
    conn.commit()
    conn.close()
    
    return {
        "evaluation": evaluation,
        "next_question": next_question
    }

@app.get("/api/practice/report/{session_id}")
async def get_practice_report(session_id: str):
    import sqlite3
    import json
    conn = sqlite3.connect("./data/startup_history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT messages FROM pitch_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"history": json.loads(row[0])}

@app.post("/api/export/google-slides/{plan_id}")
async def export_google_slides(plan_id: str):
    from agent.export.export_manager import handle_export
    plan = get_plan_by_id(plan_id)
    url = handle_export(plan_id, plan, "google_slides")
    return {"status": "success", "url": url}

@app.post("/api/export/google-docs/{plan_id}")
async def export_google_docs(plan_id: str):
    from agent.export.export_manager import handle_export
    plan = get_plan_by_id(plan_id)
    url = handle_export(plan_id, plan, "google_docs")
    return {"status": "success", "url": url}

@app.post("/api/export/notion/{plan_id}")
async def export_notion(plan_id: str):
    from agent.export.export_manager import handle_export
    plan = get_plan_by_id(plan_id)
    url = handle_export(plan_id, plan, "notion")
    return {"status": "success", "url": url}

@app.post("/api/pitch/narration/{plan_id}")
async def generate_pitch_narration(plan_id: str):
    from agent.voice_generator import generate_voice_narration
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    result = generate_voice_narration(plan_id, plan)
    response_data = dict(result)
    if result.get("status") == "ok":
        response_data["audio_url"] = f"/api/pitch/audio/{plan_id}"
    else:
        response_data["audio_url"] = None
    return response_data


@app.get("/api/pitch/audio/{plan_id}")
async def get_pitch_audio(plan_id: str):
    from fastapi.responses import FileResponse
    from agent.memory import get_audio_generation
    
    # Resolve the path from the DB record for that idea ID, never from a user-supplied path
    rec = get_audio_generation(plan_id)
    if not rec or rec.get("status") != "ok" or not rec.get("file_path"):
        raise HTTPException(status_code=404, detail="Audio narration not available or not generated.")
    
    file_path = rec["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk.")
    
    plan = get_plan_by_id(plan_id)
    raw_title = plan.get("startup_title") if plan else "Pitch"
    clean_title = "".join(c for c in (raw_title or "Pitch") if c.isalnum() or c in (" ", "_", "-")).strip()
    safe_filename = f"{clean_title.replace(' ', '_')}_Narration.mp3"
    
    return FileResponse(file_path, media_type="audio/mpeg", filename=safe_filename)


@app.get("/api/pitch/narration/status/{plan_id}")
async def get_pitch_narration_status(plan_id: str):
    from agent.memory import get_audio_generation
    rec = get_audio_generation(plan_id)
    if not rec:
        return {"status": "none", "reason": "No narration generated yet"}
    res = dict(rec)
    if rec.get("status") == "ok":
        res["audio_url"] = f"/api/pitch/audio/{plan_id}"
    return res


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
    print("  [*]  AutoStartup AI -- Starting Server")
    print(f"  [>]  Open: http://localhost:{port}")
    print(f"  [?]  API Docs: http://localhost:{port}/docs")
    print("=" * 55 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
