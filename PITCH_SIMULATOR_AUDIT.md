# Pitch Simulator Audit Report (AutoStartup AI)

**Date**: 2026-11-08  
**Scope**: Verification of the Interactive Pitch Simulator across backend, data layer, workflow, prompts, frontend, and live runtime behavior.

---

## 1. Audit Table

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Routes `POST /api/practice/start/{plan_id}` and `POST /api/practice/answer` | **PARTIAL** | Defined in `LaunchMind-AI/main.py:272-353`. Uses `PracticeStartReq(persona_id: str)` and `PracticeAnswerReq(session_id: str, answer: str)`. Endpoint path uses `{plan_id}` instead of `{id}`. Missing `GET /api/practice/session/{session_id}` (only has `/api/practice/report/{session_id}`). |
| 2 | Question generation from plan context | **PARTIAL** | `LaunchMind-AI/agent/pitch_practice.py:4-26`. Reads ONLY `idea`, `core_features[:300]`, and `revenue_model[:300]`. Lacks `problem_statement`, `target_audience`, `market_gap`, `pricing_model`, `financial_projection`, `cap_table`, and `critique`. Questions are dynamically LLM-generated, but shallow due to sparse context. |
| 3 | Personas defined with distinct prompts | **PARTIAL** | `LaunchMind-AI/agent/investor_personas.py:1-22`. Defines 4 legacy personas (`seed_vc`, `series_a`, `angel`, `technical`). Lacks the specified personas (`Aggressive VC`, `Technical Angel`, `Market-Focused Investor`, `Skeptical Generalist`, and new `Academic Examiner`, `Technical Reviewer`). |
| 4 | Answer-evaluation step | **PARTIAL** | `LaunchMind-AI/agent/pitch_practice.py:28-46`. Returns `score` (0-10), `strengths`, `weaknesses`, `suggested_improved_answer`. Lacks `missed_points` grounded in plan facts, `follow_up_hint`, Pydantic output contract validation, and session summary aggregation. |
| 5 | Conversation state & transcript storage | **PARTIAL** | Stored in SQLite table `pitch_sessions` (`id`, `plan_id`, `persona`, `messages`, `score`, `created_at`) defined in `LaunchMind-AI/agent/memory.py:155-164`. Messages stored as raw JSON string. No normalized `practice_turns` table, no session status/completion tracking, and no `simulation_transcript.json` file export. |
| 6 | Shared LLM client usage | **YES** | `LaunchMind-AI/agent/pitch_practice.py:5, 43` routes through `llm_invoke` and `safe_json_parse` in `agent/workflow.py`, which use `llm_call` in `agent/llm_client.py` with Tenacity retries. |
| 7 | Input validation & error guards | **NO** | `LaunchMind-AI/main.py:273-353`. Only checks `if not plan: 404` and `if not session: 404`. Does NOT validate persona IDs, does NOT reject empty or whitespace-only answers, does NOT enforce the 3,000-character answer cap, and does NOT return HTTP 409 for finished sessions. |
| 8 | Frontend UI implementation | **PARTIAL** | `LaunchMind-AI/frontend/index.html:2407-2437` has `#practiceModal` and JS calls `openPitchPractice`, `startPractice`, `sendPracticeAnswer`. However, it lacks question counters, session summary view, voice input fallback, and DOM sanitization. |
| 9 | Visible link from History and Final Results | **PARTIAL** | History view (`viewPlan()` in `LaunchMind-AI/frontend/index.html:2258`) has a "🎤 Pitch Practice" button. The live generation results view (`renderFinalPlan()` in `frontend/index.html:1769-1776`) **completely omits the button**, so users completing a run never see Pitch Practice. |
| 10 | Runtime Execution Test | **BROKEN (500)** | Calling `POST /api/practice/start/271bf37d-6b75-4118-8582-5e9e9b9342b6` with `{"persona_id": "seed_vc"}` failed with **HTTP 500**. Root cause: `agent/pitch_practice.py:25` hardcodes `max_tokens=200`, causing `LLMCallError: truncated_response: token limit (200) reached`. |

---

## 2. Verdict

**EXISTS BUT BROKEN AND PARTIALLY INVISIBLE**

The Interactive Pitch Simulator exists in proto-form in the codebase (`pitch_practice.py`, `pitch_sessions` table, modal in `index.html`), but is currently **broken at runtime** (HTTP 500 due to a 200-token limit in question generation) and **invisible on the main results page** (the button was only wired into the history view, not `renderFinalPlan`). Furthermore, it only injects 300 characters of features/revenue into the prompt, uses legacy persona keys, lacks input validation guards (422/409), lacks Pydantic evaluation schema with grounded missed points, lacks session summaries, and does not export `simulation_transcript.json`.

---

## 3. Recommended Implementation (Branch 2)

Because the backend is partially missing required schemas, personas, guards, and endpoints, and is failing at runtime:
1. **Database**: Add `practice_sessions` and `practice_turns` tables with guarded migration.
2. **Personas**: Implement all 6 personas (`Aggressive VC`, `Technical Angel`, `Market-Focused Investor`, `Skeptical Generalist`, `Academic Examiner`, `Technical Reviewer`) with rich, distinct prompt styles.
3. **Comprehensive Context**: Feed rich plan context (title, problem, audience, market sizing, solution, features, revenue, pricing, financials, cap table, critique risks) to generate truly plan-grounded questions and evaluations.
4. **Validation & Endpoints**:
   - `POST /api/practice/start/{plan_id}`: `{persona, num_questions?, language?}` (returns 404 on bad plan).
   - `POST /api/practice/answer`: `{session_id, answer}` with length validation (422), finished session check (409), evaluation with `score`, `strengths`, `weaknesses`, `missed_points`, `better_answer`, `follow_up_hint`, next question, and end-of-session summary.
   - `GET /api/practice/session/{session_id}`: full transcript and scores, plus `simulation_transcript.json` file export.
5. **Frontend**: Add "🎤 Pitch Practice" to `renderFinalPlan`, enhance modal with persona selector, turn indicator (e.g. 1/5), audio/voice input using Web Speech API, structured evaluation cards, and final session summary.

