# 🚀 LaunchMind-AI — Autonomous Startup Generator

An autonomous AI agent that takes a startup idea and generates a complete, professional business plan.
Built with **LangGraph**, **Claude AI**, **ChromaDB**, and **FastAPI**.

## ✨ Key Features

- **Autonomous Agent Workflow**: Decomposes an idea into multi-step execution tasks and researches them using web tools.
- **AI Investor Matching Engine**: Automatically finds suitable VC firms and angel investors tailored to your startup's sector, stage, and funding requirements.
- **Interactive Pitch Practice**: Chat with AI investor personas (e.g., Aggressive VC, Technical Angel) to practice your pitch and get real-time evaluations on your answers.
- **Brand Strategy Generation**: Automatically designs a brand identity including brand personas, taglines, color palettes, and generates high-converting marketing copy.
- **Multi-Format Export**: Instantly downloads generated professional documents in **PowerPoint (PPTX)**, **PDF**, and **Word (DOCX)** formats.
- **Graphical Business Roadmap**: Programmatically designs and generates a beautiful, 15-stage timeline SVG graphic visualizing your execution roadmap from idea to final outcome.
- **RAG Memory**: Uses ChromaDB to store and retrieve research context during generation.

---

## 📁 Project Structure

```
autostartup-ai/
├── main.py                 # FastAPI server with SSE streaming
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── agent/
│   ├── workflow.py         # LangGraph multi-node agent graph
│   ├── investor_matcher.py # AI VC and Angel matching engine
│   ├── pitch_practice.py   # AI interactive investor practice
│   ├── brand_service.py    # Generates Brand Guidelines & Personas
│   ├── landing_service.py  # Generates SEO-optimized landing copy
│   ├── memory.py           # ChromaDB (RAG) + SQLite memory
│   ├── export/             # Multi-format document export logic
│   └── prompts.py          # All LLM prompts
├── frontend/
│   └── index.html          # Complete web UI with dashboard
└── data/                   # Auto-created: databases, documents, audio
```

---

## ⚡ Quick Start

### Step 1 — Get API Keys
1. Get a free Groq or Anthropic API key at: https://console.groq.com
2. Get a free Pexels API key at: https://www.pexels.com/api/ *(Required for auto-embedding images)*

### Step 2 — Setup Environment
```bash
# Clone the repository
git clone https://github.com/yourusername/autostartup-ai.git
cd autostartup-ai

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env
```

### Step 3 — Add Your API Keys
Edit `.env` and add:
```env
GROQ_API_KEY=your_api_key_here
PEXELS_API_KEY=your_pexels_api_key_here
```

### Step 4 — Run the Server
```bash
python main.py
```

Visit `http://localhost:8000` to access the web interface.

---

## 🧠 The Agent Graph

```
User Idea
    │
    ▼
Node 1: Decompose Idea → Multi-step subtasks (LLM)
    │
    ▼
Node 2: Research Market & Competitors → DuckDuckGo search (Tool)
    │
    ▼
Node 3: Store in ChromaDB → RAG memory embeddings
    │
    ▼
Node 4: Identify Market Gaps & TAM/SAM/SOM Estimation (LLM)
    │
    ▼
Node 5: Generate Solution & Core Features → LLM
    │
    ▼
Node 6: Generate Revenue & Business Model → LLM
    │
    ▼
Node 7: Generate Brand Strategy → Personas, Copy, Aesthetics (LLM)
    │
    ▼
Node 8: Generate Pitch Deck Outline → LLM
    │
    ▼
Node 9: Generate Financial Projections & Cap Table → LLM
    │
    ▼
Node 10: Compile Full Plan → LLM synthesis
    │
    ▼
Node 11: Adversarial Review → Investor Devil's Advocate (LLM)
    │
    ▼
Node 12: Investor Matching → AI finds targeted VC / Angel matches
    │
    ▼
Node 13: Generate Assets → SVG Roadmaps, System Architecture, Pitch Narration
    │
    ▼
Complete Business Document & Dashboard → Ready for Pitch Practice!
```

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Server-Sent Events
- **AI Agent**: LangGraph (StateGraph), LangChain
- **LLM**: Groq / Anthropic Claude
- **Vector DB**: ChromaDB (local, persistent)
- **Web Search**: DuckDuckGo (free, no API key)
- **Memory**: SQLite (history) + ChromaDB (RAG)
- **Frontend**: Vanilla HTML/CSS/JS

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the web UI |
| `/api/generate` | POST | Start agent (SSE stream) |
| `/api/practice/start/{id}` | POST | Start an interactive pitch session |
| `/api/practice/answer` | POST | Submit pitch answer and get evaluation |
| `/api/download_ppt/{id}` | GET | Download generated PPTX |
| `/api/download_pdf/{id}` | GET | Download generated PDF |
| `/api/download_word/{id}` | GET | Download generated DOCX |

---

## 📝 License

MIT License - feel free to use this project for personal or commercial purposes.
