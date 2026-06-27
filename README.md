# 🚀 LaunchMind-AI— Autonomous Startup Generator

An autonomous AI agent that takes a startup idea and generates a complete business plan.
Built with **LangGraph**, **Claude AI**, **ChromaDB**, and **FastAPI**.

---

## ✅ Hackathon Requirements Satisfied

| Requirement | Implementation |
|---|---|
| Autonomous AI Agent | LangGraph 12-step workflow, zero human intervention |
| Task Decomposition | Node 1: breaks idea into 10 subtasks via LLM |
| Tool Selection | `select_tool()` in tools.py picks the right search tool |
| Contextual Memory | ChromaDB vector DB + SQLite persistent storage |
| Multi-step Workflow | 12 sequential LangGraph nodes |
| Minimal Human Intervention | User inputs idea → full plan auto-generated |
| LLM Usage | Anthropic Claude (claude-haiku) for reasoning |
| RAG Retrieval | ChromaDB stores research, retrieves context for each step |
| Tool Calling / Function Calling | DuckDuckGo search called as tools from agent nodes |
| Planning & Orchestration | LangGraph StateGraph orchestrates all steps |

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
│   └── prompts.py          # All LLM prompts
├── frontend/
│   └── index.html          # Complete web UI
└── data/                   # Auto-created: chroma_db + SQLite
```

---

## ⚡ Quick Start

### Step 1 — Get API Key
Get a free Anthropic API key at: https://console.anthropic.com

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
```
ANTHROPIC_API_KEY=your-api-key-here
```

### Step 4 — Run the Server
```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000` to access the web interface.

---

## 🔧 API Endpoints

- `POST /generate-startup` - Generate startup plan from idea
- `GET /` - Serve web UI
- Server-Sent Events (SSE) streaming for real-time updates

---

## 💡 How It Works

1. **User Input**: Submit a startup idea
2. **Task Decomposition**: AI breaks it into 10 subtasks
3. **Research Phase**: Agent researches each subtask using DuckDuckGo
4. **Vector DB Storage**: Results stored in ChromaDB for retrieval
5. **Plan Generation**: AI synthesizes research into comprehensive business plan
6. **Streaming Response**: Results streamed to frontend in real-time

---

## 📚 Dependencies Overview
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Step 3 — Install & Run
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
$env:GROQ_API_KEY='paste_your_new_key_here'
```

### Step 4 — Open Browser
```
http://localhost:8000
```

---

## 🧠 How the Agent Works

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
Node 12: Save to SQLite → persistent history
    │
    ▼
Complete Business Plan → displayed in UI
```

---

## 💡 Example Startup Ideas to Test

1. `AI app for farmers`
2. `smart waste management platform`
3. `AI career guidance for graduates`
4. `mental health app for teenagers`
5. `hyperlocal food delivery startup`
6. `EdTech platform for rural students`
7. `AI legal assistant for small businesses`
8. `sustainable fashion marketplace`

---

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Server-Sent Events
- **AI Agent**: LangGraph (StateGraph), LangChain
- **LLM**: Anthropic Claude (claude-haiku)
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
| `/api/history` | GET | All previous plans |
| `/api/idea/{id}` | GET | Specific plan details |
| `/api/health` | GET | Health check |
| `/docs` | GET | Interactive API docs |

---

## ❓ Troubleshooting

### Issue: "ANTHROPIC_API_KEY not found"
**Solution**: Make sure you've created `.env` file and added your API key:
```bash
cp .env.example .env
# Then edit .env and add your key
```

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

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

---

## 📧 Support

For issues or questions, please open a GitHub issue or reach out.

---

**Built with ❤️ for hackathons and startup builders**
