# LaunchMind-AI Comprehensive Audit Report

**Date:** October 23, 2026  
**Auditor:** Antigravity AI  
**Scope:** Repository audit against the 17-item requirement checklist across backend, agents, frontend, security, and tests.

---

## Audit Summary Table

| # | Item | Status | Primary Files & Lines | Summary / Defect Found |
|---|---|---|---|---|
| 1 | Real text-to-speech audio instead of placeholder MP3 files | **DONE** | `agent/tts_service.py` (L1-568), `agent/voice_generator.py` (L1-50), `tests/test_tts.py` | Real Edge-TTS and OpenAI TTS providers, natural speech figure expansion, mutagen validation, 0 mock audio bytes. Covered by 5 passing unit tests. |
| 2 | Real Google Docs export (Google Docs API) | **FAKE** | `agent/export/google_docs.py` (L3-5), `agent/export/export_manager.py` (L21-22) | Returns `"/api/download_word/" + plan_id` instead of integrating with Google Docs API or handling OAuth/service account credentials. |
| 3 | Real Google Slides export (Google Slides API) | **FAKE** | `agent/export/google_slides.py` (L3-5), `agent/export/export_manager.py` (L19-20) | Returns `"/api/download_ppt/" + plan_id` instead of integrating with Google Slides API. |
| 4 | Real Notion page export (Notion API) | **FAKE** | `agent/export/notion_export.py` (L3-5), `agent/export/export_manager.py` (L23-24) | Returns `"/api/download_pdf/" + plan_id` instead of creating pages via Notion REST API. |
| 5 | Real company research (Crunchbase or reliable source) | **FAKE** | `agent/tools.py` (L61-69), `agent/workflow.py` (L379) | `search_crunchbase` returns hardcoded string `f"Crunchbase funding data for {query} (stub)"`. Needs real API with free fallback (e.g. Wikidata / SEC EDGAR). |
| 6 | Real Google Trends data retrieval | **FAKE** | `agent/tools.py` (L71-79), `agent/workflow.py` (L380) | `search_google_trends` returns hardcoded stub string `f"Google Trends data for {query} (stub)"`. Needs `pytrends` with backoff and caching. |
| 7 | Real sentiment analysis of customer reviews/feedback | **FAKE** | `agent/tools.py` (L81-89), `agent/workflow.py` (L381) | `search_sentiment` returns hardcoded stub string `f"Sentiment analysis for {query} (stub)"`. Needs real search/Reddit client and sentiment analysis. |
| 8 | Startup-specific system architecture diagrams instead of generic flowcharts | **FAKE / PARTIAL** | `agent/image_service.py` (L80-106), `agent/architecture_service.py` (L1-167) | `generate_flowchart` used in Word/PDF documents hardcodes a generic Mermaid chart ("User Platform -> API Gateway -> Core Engine -> Database") regardless of startup idea. Studio HTML is startup-specific, but document embedding is generic. |
| 9 | Investor report improved with competitor analysis, market research, risks, financial assumptions | **PARTIAL** | `agent/investor_service.py` (L35-82), `agent/workflow.py` (L1160) | PDF report only renders idea, high-level score breakdown, and Priority 1 actions. Completely omits competitor SWOT, TAM/SAM/SOM sizing, financial assumptions, and data source status. |
| 10 | Error handling and retries for failed AI requests | **MISSING** | `agent/workflow.py` (L102-127), `agent/asset_manager.py` (L16-24) | LLM calls invoke `ChatGroq.ainvoke` directly without tenacity retries, without timeout overrides, without `Retry-After` header extraction, without circuit breakers, without provider fallback, and without node-level isolation (one failure aborts entire run). |
| 11 | Validation of LLM JSON responses; sanitizing of generated HTML and SVG | **MISSING / PARTIAL** | `agent/workflow.py` (L130-156), `agent/logo_service.py`, `agent/landing_service.py` | `safe_json_parse` performs simple `json.loads` without Pydantic schema enforcement or structured repair. SVG and HTML templates interpolate raw strings without allowlist sanitization. |
| 12 | Language parameter fixed in brand-kit generation | **PARTIAL / BROKEN** | `agent/brand_service.py` (L1-30), `agent/asset_manager.py` (L63) | `generate_brand_kit` takes `language: str` as an argument, but the parameter is completely ignored in the prompt and system prompt; brand kit always generates in English. |
| 13 | Database tables initialized properly; database errors handled | **PARTIAL** | `agent/memory.py` (L87-147), `agent/investor_database.py` | Tables are created but SQLite foreign keys are not enabled (`PRAGMA foreign_keys = ON`), connections lack transactional rollback context management, and `startup_plans` table is missing `run_summary`. |
| 14 | Automated tests for API endpoints, workflow nodes, database operations, asset generation | **PARTIAL** | `tests/test_tts.py` | Only 5 tests exist for TTS. Zero tests for FastAPI endpoints, LangGraph nodes, SQLite storage, or asset generation. |
| 15 | README updated to match real implementation and required API keys | **PARTIAL** | `README.md` (L241-256, L389-405) | Discrepancy between code and docs (claims `ANTHROPIC_API_KEY` is required while code uses `GROQ_API_KEY`); missing `TTS_PROVIDER`, `OPENAI_API_KEY`, reliability settings, and export credential guides. |
| 16 | Authentication, authorization, secure file downloads | **MISSING** | `main.py` (L172-234) | No authentication/authorization. File download routes directly interpolate `plan_id` into paths (`./data/.../{plan_id}.*`) without UUID validation or path traversal prevention. |
| 17 | Full workflow verified from idea submission to final assets | **PARTIAL** | `main.py`, `agent/workflow.py` | Pipeline has not been validated end-to-end with an automated integration test verifying all 19 steps and output assets. |

---

## Detailed Audit Findings

### 1. TTS Audio Generation (Item 1) - DONE
- **Implementation**: Located in `agent/tts_service.py` and `agent/voice_generator.py`.
- **Validation**: Full offline synthesis tested with Edge-TTS (`533 KB`, `88.9s`), mutagen header validation, and `tests/test_tts.py` passing.

### 2. Cloud Platform Exports (Items 2, 3, 4) - FAKE
- **Google Docs (`agent/export/google_docs.py`)**: Returns `/api/download_word/{plan_id}`.
- **Google Slides (`agent/export/google_slides.py`)**: Returns `/api/download_ppt/{plan_id}`.
- **Notion (`agent/export/notion_export.py`)**: Returns `/api/download_pdf/{plan_id}`.
- **Root Cause**: The endpoints pretend to export to cloud platforms but actually just redirect users to local file download routes. Needs status-based API integrations (`ok`, `skipped`, `failed`) that authenticate when credentials exist and report `skipped` honestly when missing.

### 3. Market Research & Validation Data (Items 5, 6, 7) - FAKE
- **Crunchbase (`agent/tools.py:61`)**: Hardcoded stub.
- **Google Trends (`agent/tools.py:71`)**: Hardcoded stub.
- **Sentiment (`agent/tools.py:81`)**: Hardcoded stub.
- **Root Cause**: The functions return stub JSON indicating success. Must be replaced with real data retrieval: `pytrends` with backoff/cache, free public company data fallback (Wikidata/SEC EDGAR), and real discussion sentiment.

### 4. Diagrams & Reports (Items 8, 9) - FAKE / PARTIAL
- **Architecture Flowchart**: `agent/image_service.py` uses a hardcoded static Mermaid string for all startups.
- **Investor PDF Report**: `agent/investor_service.py` renders only 3 sections and ignores competitor analysis, market sizing, financial projections, and data status.

### 5. AI Reliability, Retries & Validation (Items 10, 11) - MISSING
- Calls to `ChatGroq.ainvoke` in `agent/workflow.py` and `agent/asset_manager.py` are unprotected.
- A single rate limit (429) or server error (503/529) terminates the entire LangGraph workflow.
- JSON responses are parsed with raw `json.loads` without Pydantic validation schemas.
- Generated SVG/HTML are not sanitized against malicious injection.

### 6. Internationalization / Language (Item 12) - BROKEN
- In `agent/brand_service.py`, `language` is passed into `generate_brand_kit(idea, language, ...)` but omitted in the LLM prompt.

### 7. Database Integrity & File Download Security (Items 13, 16) - PARTIAL / MISSING
- Foreign keys not enabled in SQLite; transactions do not use safe rollback wrappers.
- File download endpoints in `main.py` take arbitrary `plan_id` string paths without sanitization, exposing potential path traversal vulnerabilities. No auth layer exists.

### 8. Testing & Documentation (Items 14, 15, 17) - PARTIAL
- Only 5 TTS tests exist. Entire workflow, API surface, and database layers lack automated test coverage.
- README is mismatched with active environment variables and features.
