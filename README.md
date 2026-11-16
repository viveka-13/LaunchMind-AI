# 🚀 LaunchMind-AI — Autonomous Startup Generator & Pitch Simulator

<div align="center">

**[ 23-Node LangGraph State Machine ] • [ FastAPI & SSE Streaming ] • [ ChromaDB RAG Vector Store ] • [ Python 3.11+ ]**

[![Tests](https://img.shields.io/badge/tests-89%20passed-brightgreen.svg)](#-testing--quality-assurance)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## 🚀 Overview

**LaunchMind-AI** is an autonomous, research-driven AI platform built with **LangGraph** and **FastAPI** that transforms a single raw startup idea into an investor-ready business platform.

It autonomously conducts real-time web research, synthesizes market intelligence using **Retrieval-Augmented Generation (RAG)** in **ChromaDB**, computes synchronized financial models and cap tables, matches suitable investors, and programmatically generates comprehensive deliverables:
- **Slide Pitch Decks** (`.pptx`) with relevant photography auto-embedded via Pexels
- **Business Plans** (`.docx` & `.pdf`)
- **Financial Projections & Cap Tables** (`.xlsx`)
- **System Architecture Diagrams** (Mermaid & SVG)
- **Voice Pitch Narration** (`.mp3`) via Edge Neural TTS or OpenAI TTS
- **Interactive Pitch Practice Simulator** against adversarial AI investor personas

---

## ✨ Key Capabilities & Architectural Innovations

### 🧠 23-Node Autonomous LangGraph State Machine
An end-to-end cyclic graph coordinating research, quantitative modeling, narrative synthesis, adversarial critique, and consistency validation.

```text
                            User Startup Idea
                                   │
                                   ▼
                        1. Decompose Subtasks
                                   │
                                   ▼
                       2. Understand Idea & Category
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          3. Market Web Research        4. Competitor Intelligence
             & Google Trends               & SEC EDGAR / Wikidata
                    └──────────────┬──────────────┘
                                   ▼
                         5. Synthesize Research
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
          6. Competitor SWOT             7. ChromaDB RAG Storage
                    └──────────────┬──────────────┘
                                   ▼
                        8. Calculate Market Size
                                   │
                                   ▼
                          9. Analyze Market Gaps
                                   │
                                   ▼
                        10. Generate Solution
                                   │
                                   ▼
                        11. Define Core Features
                                   │
                                   ▼
                        12. Build Pricing Model
                                   │
                                   ▼
                        13. Financial Projections
                                   │
                                   ▼
                        14. Cap Table & Funding Ask
                                   │
                                   ▼
                     15. Build Canonical Facts (SSOT)
                                   │
                                   ▼
                        16. Generate Revenue Model
                                   │
                                   ▼
                        17. AI Investor Matching
                                   │
                                   ▼
                        18. Implementation Roadmap
                                   │
                                   ▼
                        19. Pitch Deck Structure
                                   │
                                   ▼
                        20. Compile Final Plan & Brand
                                   │
                                   ▼
                        21. Adversarial VC Review
                                   │
                                   ▼
                    22. Cross-Section Consistency Check
                                   │
                                   ▼
                          23. Save Plan & Assets
```

### 🔍 Category-Aware Research & Relevance Filtering
* **Brand Name Translation**: Converts arbitrary brand names (e.g., *"AgroMind AI"*, *"InvoiceFlow"*) into clean, dynamic search queries targeting the true industry category rather than literal brand text.
* **Intelligent Relevance Filter**: Automatically removes tax filing portals, generic listicles, job boards, and stale data using title deduplication and semantic scoring.
* **Separation of Concerns**: Identifies physical fieldwork (e.g., *"interview 30 farmers"*) and routes it to an explicit founder validation checklist while substituting autonomous desk research proxies.

### 📐 Single Source of Truth & Consistency Validator
* **Zero Contradictions**: Node 15 (`build_canonical_facts`) establishes a single canonical record of all pricing tiers, ARPU, funding asks, valuations, use of funds, TAM/SAM/SOM metrics, and CAGR.
* **Cross-Section Audit**: Node 22 (`validate_consistency`) verifies that numbers cited across the **Pricing Model**, **Revenue Narrative**, **Cap Table**, **Pitch Deck**, and **Executive Summary** match exactly, preventing hallucinated or conflicting figures.

### 💼 AI Investor Matching & Truncation Recovery
* Evaluates startup stage, sector, and ticket size against real investor personas (accelerators like Techstars and Y Combinator, sector-specific seed funds, and leading VCs).
* Includes **truncation-aware LLM retry logic**: detects `finish_reason == "length"` or `"max_tokens"` and automatically retries with an expanded token budget and concise constraints.

### 🎤 Interactive Pitch Practice Simulator
* Founders can rehearse their pitch directly from the dashboard against distinct AI investor personas:
  * **Aggressive VC**: Focuses on competition, defensibility, and market timing.
  * **Technical Angel**: Drills down into architecture, unit economics, and scalability.
  * **Market-Focused Investor**: Evaluates TAM, CAC/LTV, and customer acquisition channels.
  * **Skeptical Generalist**: Probes regulatory risks, churn, and team capability.
* Evaluates answers on relevance, persuasiveness, and confidence with actionable coaching tips.

### 🗑️ Safe Plan Management & Cascading History Deletions
* SQLite database with **WAL mode** and foreign key cascades (`PRAGMA foreign_keys = ON`).
* Deleting a plan cleanly purges child pitch sessions, practice turns, and asset records in a single transaction, and deletes generated files (audio, presentation, docs) from disk without path traversal risk.
* Built-in **Deduplicate History** feature cleans up accidental double submissions.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/), Uvicorn, Python 3.11+ |
| **Agent Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph), LangChain |
| **Primary LLM** | [Groq](https://groq.com/) (`openai/gpt-oss-20b`, `llama-3.3-70b-versatile`) |
| **Fallback LLM** | [Anthropic](https://www.anthropic.com/) (`claude-3-5-sonnet`) |
| **Vector Database & RAG** | [ChromaDB](https://www.trychroma.com/) with Sentence Transformers |
| **Relational Storage** | SQLite 3 (WAL mode, foreign key cascading constraints) |
| **Asset Generation** | `python-pptx`, `python-docx`, `fpdf2`, `openpyxl`, `matplotlib` |
| **Voice Narration (TTS)** | `edge-tts` (Microsoft Edge Neural Voices), OpenAI TTS |
| **Data Enrichment** | Google Trends (`pytrends`), SEC EDGAR, Wikidata, Pexels API |
| **Frontend** | Responsive Vanilla JS, Server-Sent Events (SSE), Web Speech API |

---

## 🚀 Quick Start Guide

### Prerequisites
* **Python 3.11+** installed
* A free **Groq API key** from [console.groq.com](https://console.groq.com)
* (Optional) A free **Pexels API key** from [pexels.com/api](https://www.pexels.com/api/) for pitch deck photography

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/yourusername/autostartup-ai.git
cd autostartup-ai/LaunchMind-AI

# Create virtual environment
python -m venv .venv

# Activate on Windows:
.venv\Scripts\activate
# Activate on macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the provided example file:

```bash
cp .env.example .env
```

Edit `.env` and provide your credentials:

```env
# Primary LLM Provider (Groq)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b

# Optional: Presentation Photography
PEXELS_API_KEY=your_pexels_key_here

# Voice Narration (Default is free Edge TTS)
TTS_PROVIDER=edge
```

### 3. Run the Application

```bash
python main.py
```

Open your browser at:
- **Application UI**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/generate` | `POST` | Initiates autonomous startup generation; streams 23-node progress via **SSE** |
| `/api/health` | `GET` | Health check and Groq API status |
| `/api/history` | `GET` | Lists all historical startup plans with summaries |
| `/api/idea/{plan_id}` | `GET` | Retrieves complete data, financial metrics, and assets for a plan |
| `/api/critique/{plan_id}` | `GET` | Retrieves the adversarial VC critique for a plan |
| `/api/history/{plan_id}` | `DELETE` | Atomically deletes a plan, all child sessions, and disk assets |
| `/api/history/deduplicate` | `POST` | Removes duplicate plans generated within a short time window |
| `/api/practice/start/{plan_id}` | `POST` | Starts an interactive pitch practice session with chosen VC persona |
| `/api/practice/answer` | `POST` | Submits an answer for real-time AI scoring and coaching |
| `/api/download_deck/{plan_id}` | `GET` | Downloads generated PowerPoint pitch deck (`.pptx`) |
| `/api/download_pdf/{plan_id}` | `GET` | Downloads generated PDF business report (`.pdf`) |
| `/api/download_word/{plan_id}` | `GET` | Downloads generated Word business plan (`.docx`) |
| `/api/download_financials/{plan_id}` | `GET` | Downloads generated financial model spreadsheet (`.xlsx`) |
| `/api/export/notion/{plan_id}` | `POST` | Exports business plan to connected Notion workspace |
| `/api/export/google-docs/{plan_id}` | `POST` | Exports business plan to Google Docs |
| `/api/export/google-slides/{plan_id}` | `POST` | Exports pitch presentation to Google Slides |

---

## 🧪 Testing & Quality Assurance

The test suite covers schema validation, unit math calculations, truncation recovery, database migrations, audio generation, and research filtering:

```bash
# Run all unit and integration tests
python -m pytest tests/ -v
```

Current test status: **89 passed, 0 failed**.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
