# 🚀 LaunchMind-AI — Autonomous Startup Generator

An autonomous AI agent that takes a startup idea and generates a complete, professional business plan.
Built with **LangGraph**, **Claude AI**, **ChromaDB**, and **FastAPI**.

## ✨ Key Features

- **Autonomous Agent Workflow**: Decomposes an idea into 10 subtasks and researches them using web tools.
- **RAG Memory**: Uses ChromaDB to store and retrieve research context during generation.
- **Multi-Format Export**: Generates professional documents in **PowerPoint (PPTX)**, **PDF**, and **Word (DOCX)** formats.
- **Auto-Embedded Images**: Integrates with the **Pexels API** to automatically find and embed high-quality, relevant images into your generated documents.
- **System Architecture Flowcharts**: Automatically designs and generates a system architecture flowchart for your app/startup using Mermaid.ink.

---

## 📁 Project Structure

```
autostartup-ai/
├── main.py                 # FastAPI server with SSE streaming
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
├── agent/
│   ├── __init__.py
│   ├── workflow.py         # LangGraph 12-node agent graph
│   ├── tools.py            # DuckDuckGo search tools
│   ├── memory.py           # ChromaDB (RAG) + SQLite memory
│   ├── image_service.py    # Pexels API & Mermaid flowchart generator
│   ├── ppt_generator.py    # Generates PPTX pitch decks
│   ├── pdf_generator.py    # Generates PDF business plans
│   ├── word_generator.py   # Generates DOCX business plans
│   └── prompts.py          # All LLM prompts
├── frontend/
│   └── index.html          # Complete web UI with format selector
└── data/                   # Auto-created: chroma_db + SQLite + images
```

---

## ⚡ Quick Start

### Step 1 — Get API Keys
1. Get a free Anthropic API key at: https://console.anthropic.com
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
ANTHROPIC_API_KEY=your_anthropic_api_key_here
PEXELS_API_KEY=your_pexels_api_key_here
```

### Step 4 — Run the Server
```bash
python main.py
```

Visit `http://localhost:8000` to access the web interface.

---

## 💡 How It Works

1. **User Input**: Submit a startup idea and select your desired output format (PPT, PDF, Word).
2. **Task Decomposition**: AI breaks the idea into 10 subtasks.
3. **Research Phase**: Agent researches each subtask using DuckDuckGo.
4. **Vector DB Storage**: Results stored in ChromaDB for retrieval.
5. **Asset Generation**: Fetches relevant images via Pexels and generates a system flowchart.
6. **Plan Generation**: AI synthesizes research into a comprehensive business plan document.
7. **Streaming Response**: Progress is streamed to the frontend in real-time until the download is ready.

---

## 🧠 The Agent Graph

```
User Idea
    │
    ▼
Node 1: Decompose Idea → 10 subtasks (LLM)
    │
    ▼
Node 2: Research Market → DuckDuckGo search (Tool)
    │
    ▼
Node 3: Research Competitors → DuckDuckGo search (Tool)
    │
    ▼
Node 4: Store in ChromaDB → RAG memory embeddings
    │
    ▼
Node 5: Identify Market Gaps → RAG retrieval + LLM
    │
    ▼
Node 6: Generate Solution → LLM
    │
    ▼
Node 7: Generate Features → LLM
    │
    ▼
Node 8: Generate Revenue Model → LLM
    │
    ▼
Node 9: Generate Roadmap → LLM
    │
    ▼
Node 10: Generate Pitch Deck → LLM
    │
    ▼
Node 11: Compile Full Plan → LLM synthesis
    │
    ▼
Node 12: Save Plan & Assets → Fetch Images, Generate Flowchart, Create PPT/PDF/Word
    │
    ▼
Complete Business Document → Ready for download!
```

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Server-Sent Events
- **AI Agent**: LangGraph (StateGraph), LangChain
- **LLM**: Anthropic Claude
- **Vector DB**: ChromaDB (local, persistent)
- **Web Search**: DuckDuckGo (free, no API key)
- **Memory**: SQLite (history) + ChromaDB (RAG)
- **Asset APIs**: Pexels API (Images), Mermaid.ink (Flowcharts)
- **Document Gen**: `python-pptx`, `fpdf2`, `python-docx`
- **Frontend**: Vanilla HTML/CSS/JS

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Serves the web UI |
| `/api/generate` | POST | Start agent (SSE stream) |
| `/api/history` | GET | All previous plans |
| `/api/idea/{id}` | GET | Specific plan details |
| `/api/download_ppt/{id}` | GET | Download generated PPTX |
| `/api/download_pdf/{id}` | GET | Download generated PDF |
| `/api/download_word/{id}` | GET | Download generated DOCX |
| `/docs` | GET | Interactive API docs |

---

## ❓ Troubleshooting

### Issue: Images aren't showing up in my documents
**Solution**: Ensure you have added `PEXELS_API_KEY` to your `.env` file. If the key is missing or invalid, the app will gracefully skip image generation.

### Issue: "Port 8000 is already in use"
**Solution**: Run on a different port:
```bash
uvicorn main:app --reload --port 8001
```

### Issue: ChromaDB errors
**Solution**: Delete the `data/` folder and restart (it will recreate):
```bash
rm -rf data/
# Restart the server
```

---

## 📝 License

MIT License - feel free to use this project for personal or commercial purposes.
