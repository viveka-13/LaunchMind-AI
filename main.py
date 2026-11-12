# main.py
# AutoStartup AI — FastAPI Backend Server

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

AGENT_TIMEOUT_SECONDS = int(os.getenv("AGENT_TIMEOUT_SECONDS", "600"))

# Load environment variables
load_dotenv()

# Validate API key
if not os.getenv("GROQ_API_KEY"):
    print("[WARNING] GROQ_API_KEY not set. Please create a .env file.")

# Initialize database on startup via lifespan
from agent.memory import (
    init_database,
    get_all_plans,
    get_plan_by_id,
    delete_plan_by_id,
    deduplicate_history,
    DatabaseError,
)
from agent.investor_database import init_investor_db
from agent.pitch_practice import generate_pitch_question, evaluate_pitch_answer
from agent.language import validate_language

# Import agent components
from agent.workflow import run_agent, event_queues

import uuid

# ─────────────────────────────────────────────
# FastAPI App Setup with Lifespan
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    init_investor_db()
    yield

app = FastAPI(
    title="AutoStartup AI",
    description="Autonomous AI agent for complete startup plan generation",
    version="1.0.0",
    lifespan=lifespan,
)

@app.exception_handler(DatabaseError)
async def database_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "A database error occurred. Please try again later."}
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
    language: str = "en"
    doc_format: str = "ppt"

    @field_validator("language")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if not v:
            return "en"
        try:
            return validate_language(v)
        except ValueError as e:
            raise ValueError(str(e))

    model_config = {"json_schema_extra": {"example": {"idea": "AI app for farmers", "language": "en", "doc_format": "ppt"}}}


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


@app.delete("/api/history/{plan_id}")
async def delete_history_plan(plan_id: str):
    """Delete a generated startup plan by its ID."""
    deleted = delete_plan_by_id(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found or could not be deleted.")
    return {"status": "ok", "deleted_id": plan_id}


@app.post("/api/history/deduplicate")
async def deduplicate_history_plans():
    """Remove redundant test duplicate plans, keeping the most recent copy."""
    deleted_count = deduplicate_history()
    return {"status": "ok", "deleted_count": deleted_count}


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
# Fundraising Platform & Pitch Simulator APIs
# ─────────────────────────────────────────────

from typing import Optional
from pydantic import BaseModel, Field
from agent.investor_personas import resolve_persona, INVESTOR_PERSONAS
from agent.pitch_practice import (
    generate_pitch_question,
    evaluate_pitch_answer,
    generate_pitch_session_summary,
    export_simulation_transcript,
)
from agent.memory import (
    create_pitch_session,
    get_pitch_session,
    update_pitch_session,
    save_practice_turn,
    get_session_turns,
)


class PracticeStartReq(BaseModel):
    persona_id: Optional[str] = None
    persona: Optional[str] = None
    num_questions: Optional[int] = Field(default=5, ge=1, le=10)
    language: Optional[str] = None


class PracticeAnswerReq(BaseModel):
    session_id: str
    answer: str


@app.get("/api/practice/personas")
async def list_practice_personas():
    """Return all available investor & evaluator personas for pitch practice."""
    return {"personas": list(INVESTOR_PERSONAS.values())}


@app.post("/api/practice/start/{plan_id}")
async def start_pitch_practice(plan_id: str, req: PracticeStartReq):
    """
    Start an interactive pitch practice simulation session against an AI investor persona.
    """
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found.")

    # Accept persona or persona_id, supporting legacy aliases
    raw_persona = req.persona or req.persona_id or "aggressive_vc"
    persona = resolve_persona(raw_persona)
    num_questions = req.num_questions or 5
    lang = req.language or plan.get("language") or "en"

    session_id = str(uuid.uuid4())
    history = []

    # Generate first question grounded in the full plan
    question = await generate_pitch_question(
        plan=plan,
        persona_id=persona["id"],
        history=history,
        language=lang,
        turn_index=1,
        total_turns=num_questions,
    )

    history.append({"role": "investor", "content": question})

    success = create_pitch_session(
        session_id=session_id,
        plan_id=plan_id,
        persona=persona["id"],
        messages=history,
        num_questions=num_questions,
        language=lang,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to initialize practice session in database.")

    return {
        "session_id": session_id,
        "persona": persona["id"],
        "persona_name": persona["name"],
        "persona_title": persona.get("title", ""),
        "question": question,
        "turn_index": 1,
        "total_turns": num_questions,
        "language": lang,
    }


@app.post("/api/practice/answer")
async def answer_pitch_question(req: PracticeAnswerReq):
    """
    Submit a founder's answer, receive a rigorous evaluation, and either get the next question
    or the final session summary if all questions are completed.
    """
    raw_ans = req.answer.strip() if req.answer else ""
    if not raw_ans:
        raise HTTPException(status_code=422, detail="Answer cannot be empty or whitespace only.")
    if len(raw_ans) > 3000:
        raise HTTPException(status_code=422, detail="Answer too long (maximum 3000 characters allowed).")

    session = get_pitch_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Practice session not found.")

    if session.get("status") == "completed":
        raise HTTPException(status_code=409, detail="This practice session has already been completed.")

    plan_id = session["plan_id"]
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Associated startup plan not found.")

    persona_dict = resolve_persona(session.get("persona", "aggressive_vc"))
    history = session.get("messages", [])
    lang = session.get("language", "en")
    total_turns = session.get("num_questions", 5)

    # Last question was the most recent investor message
    last_question = ""
    for msg in reversed(history):
        if msg.get("role") == "investor":
            last_question = msg.get("content", "")
            break

    if not last_question:
        last_question = f"Could you pitch the core value proposition of {plan.get('startup_title', 'your startup')}?"

    # Evaluate the founder's answer
    evaluation = await evaluate_pitch_answer(
        question=last_question,
        answer=raw_ans,
        plan=plan,
        language=lang,
    )

    turn_score = int(evaluation.get("score", 5))

    # Calculate turn index
    past_turns_count = sum(1 for m in history if m.get("role") == "founder")
    current_turn_index = past_turns_count + 1

    # Record turn into practice_turns
    turn_id = str(uuid.uuid4())
    save_practice_turn(
        turn_id=turn_id,
        session_id=req.session_id,
        turn_index=current_turn_index,
        question=last_question,
        answer=raw_ans,
        evaluation=evaluation,
        score=turn_score,
    )

    # Append to history
    history.append({"role": "founder", "content": raw_ans})
    history.append({"role": "evaluator", "content": json.dumps(evaluation, ensure_ascii=False)})

    is_finished = current_turn_index >= total_turns

    if is_finished:
        from datetime import datetime
        finished_at = datetime.utcnow().isoformat() + "Z"

        summary = await generate_pitch_session_summary(
            history=history,
            plan=plan,
            language=lang,
        )

        overall_score = int(round(summary.get("overall_score", turn_score)))

        # Export simulation_transcript.json
        transcript_path = export_simulation_transcript(
            session_id=req.session_id,
            plan_id=plan_id,
            persona=persona_dict,
            history=history,
            summary=summary,
            language=lang,
        )

        update_pitch_session(
            session_id=req.session_id,
            messages=history,
            score=overall_score,
            status="completed",
            summary=summary,
            transcript_path=transcript_path,
            finished_at=finished_at,
        )

        return {
            "evaluation": evaluation,
            "next_question": None,
            "finished": True,
            "summary": summary,
            "turn_index": current_turn_index,
            "total_turns": total_turns,
            "transcript_url": f"/api/practice/transcript/{req.session_id}",
        }

    # Generate NEXT question
    next_question = await generate_pitch_question(
        plan=plan,
        persona_id=persona_dict["id"],
        history=history,
        language=lang,
        turn_index=current_turn_index + 1,
        total_turns=total_turns,
    )

    history.append({"role": "investor", "content": next_question})

    update_pitch_session(
        session_id=req.session_id,
        messages=history,
        score=turn_score,
        status="active",
    )

    return {
        "evaluation": evaluation,
        "next_question": next_question,
        "finished": False,
        "summary": None,
        "turn_index": current_turn_index + 1,
        "total_turns": total_turns,
    }


@app.get("/api/practice/session/{session_id}")
async def get_practice_session_details(session_id: str):
    """Return full session transcript, scores, and summary."""
    session = get_pitch_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Practice session not found.")

    turns = get_session_turns(session_id)
    persona = resolve_persona(session.get("persona", "aggressive_vc"))

    return {
        "session_id": session["id"],
        "plan_id": session["plan_id"],
        "persona": persona,
        "status": session["status"],
        "overall_score": session["score"],
        "summary": session.get("summary"),
        "total_turns": session.get("num_questions", 5),
        "created_at": session["created_at"],
        "finished_at": session.get("finished_at"),
        "turns": turns,
        "transcript_url": f"/api/practice/transcript/{session_id}" if session.get("status") == "completed" else None,
    }


@app.get("/api/practice/report/{session_id}")
async def get_practice_report(session_id: str):
    """Legacy backward-compatible endpoint for practice report."""
    session = get_pitch_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session_id,
        "history": session.get("messages", []),
        "summary": session.get("summary"),
    }


@app.get("/api/practice/transcript/{session_id}")
async def download_simulation_transcript(session_id: str):
    """Safely download the exported simulation_transcript.json for a session."""
    session = get_pitch_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    path = session.get("transcript_path")
    if not path or not os.path.exists(path):
        # Fallback to standard convention
        plan_id = session.get("plan_id", "unknown")
        fallback_path = os.path.abspath(f"./data/pitch/{plan_id}/{session_id}_transcript.json")
        canonical_fallback = os.path.abspath(f"./data/pitch/{plan_id}/simulation_transcript.json")
        if os.path.exists(fallback_path):
            path = fallback_path
        elif os.path.exists(canonical_fallback):
            path = canonical_fallback
        else:
            raise HTTPException(status_code=404, detail="Simulation transcript not yet generated.")

    return FileResponse(
        path,
        media_type="application/json",
        filename="simulation_transcript.json",
    )

@app.post("/api/export/{plan_id}/{target}")
async def export_target(plan_id: str, target: str):
    from agent.export.export_manager import handle_export
    plan = get_plan_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    normalized_target = target.replace("-", "_").lower()
    res = handle_export(plan_id, plan, normalized_target)
    return res

@app.post("/api/export/google-slides/{plan_id}")
async def export_google_slides(plan_id: str):
    return await export_target(plan_id, "google_slides")

@app.post("/api/export/google-docs/{plan_id}")
async def export_google_docs(plan_id: str):
    return await export_target(plan_id, "google_docs")

@app.post("/api/export/notion/{plan_id}")
async def export_notion(plan_id: str):
    return await export_target(plan_id, "notion")

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
