# Conductor Super Agent

A local-first AI system that aggregates conversations from **Grok**, **ChatGPT**, **Gemini**, and **Antigravity** into a unified knowledge base with persistent memory across all your AI interactions.

## 🎯 Features

- **Multi-Platform Aggregation**: Combine conversations from all major AI platforms
- **Semantic Search**: RAG-based retrieval using ChromaDB vector database
- **Persistent Memory**: Never lose context across conversations
- **Code Snippet Extraction**: Automatically extracts and indexes code from all conversations
- **Privacy First**: Runs 100% locally on your machine
- **Rich CLI Interface**: Beautiful terminal interface with search and filtering

---

## 🖥️ Local Run

### 1. Clone & Install

```bash
git clone https://github.com/Cramer-69/conductor-agent.git
cd conductor-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env   # Linux/macOS
# or: copy .env.example .env  (Windows)
```

Edit `.env` and set **at least one** API key:

| Variable | Provider | Get a key |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI (GPT-4o-mini) | <https://platform.openai.com/api-keys> |
| `GOOGLE_API_KEY` | Google Gemini | <https://aistudio.google.com/app/apikey> |
| `XAI_API_KEY` | xAI / Grok | <https://console.x.ai/> |
| `ANTHROPIC_API_KEY` | Anthropic Claude | <https://console.anthropic.com/> |

> **Do you need a new key?** No — if you already have any of these keys, just paste it in. You only need one.

### 3. (Optional) Ingest Your Conversation Data

```bash
python ingest.py
```

### 4. Start the API Server

```bash
uvicorn api.server:app --reload
# visit http://localhost:8000
```

Or start the CLI:

```bash
python -m cli.interactive
```

---

## ☁️ Quick Deploy (Render)

You can host the API server for free on [Render](https://render.com). You **do not** need a new API key — use your existing one.

### Steps

1. **Fork / push this repo to GitHub** (must be public or Render must have access).
2. Go to [render.com](https://render.com) → **New + → Web Service**.
3. Connect your GitHub repository. Render will detect `render.yaml` automatically.
4. In the **Environment** tab add **at least one** of these keys:

   | Key | Value |
   |---|---|
   | `OPENAI_API_KEY` | `sk-…` your existing key |
   | `GOOGLE_API_KEY` | your existing key |
   | `XAI_API_KEY` | your existing key |

5. Click **Deploy**. Build takes ~5 minutes.
6. Your service URL will be `https://<name>.onrender.com`. Test it:

   ```bash
   curl https://<name>.onrender.com/health
   # {"status":"healthy","api_keys_configured":true,"mode":"minimal"}
   ```

   Post a chat message:

   ```bash
   curl -X POST https://<name>.onrender.com/api/chat \
     -H "Content-Type: application/json" \
     -d '{"query": "Hello!"}'
   ```

> **Tip:** The free Render tier sleeps after 15 minutes of inactivity. Upgrade to a paid plan ($7/month) for always-on hosting.

### Common Render Problems

| Symptom | Cause | Fix |
|---|---|---|
| Build fails | Missing `PYTHON_VERSION` | Already set in `render.yaml` (3.11.0) |
| 502 on startup | Wrong port binding | Fixed — `render.yaml` uses `$PORT` |
| "minimal mode" response | No API key set | Add key in Render **Environment** tab |
| Logs show "No LLM API keys" | Key not saved | Re-save in Render dashboard and redeploy |

---

## 🤖 Supported Providers

- **Google Gemini** (`GOOGLE_API_KEY`)
- **Grok / xAI** (`XAI_API_KEY`)
- **OpenAI** (`OPENAI_API_KEY`) — default
- **Anthropic Claude** (`ANTHROPIC_API_KEY`)


### Export Your Conversations (Optional)

#### ChatGPT

1. Go to [chat.openai.com](https://chat.openai.com)
2. Click your profile → Settings → Data Controls
3. Click "Export Data"
4. Download the ZIP file (you'll receive an email)
5. Extract `conversations.json`

#### Gemini

- **Method 1**: Use [Google Takeout](https://takeout.google.com)
  - Select "Gemini Apps Activity"
  - Download and extract
- **Method 2**: Save conversations as HTML
  - Open conversation in browser
  - Right-click → Save As → HTML

#### Grok/xAI

- Export from Grok settings (ZIP format)

#### Antigravity

- Point `ANTIGRAVITY_BRAIN_DIR` in your `.env` to the brain folder (e.g. `~/.gemini/antigravity/brain`).

### Ingest Your Data

```bash
# Ingest all platforms
python ingest.py --chatgpt "path/to/conversations.json" --gemini "path/to/gemini_export_folder/" --grok "path/to/grok_export.zip"

# Or just Antigravity (requires ANTIGRAVITY_BRAIN_DIR set in .env)
python ingest.py

# Reset database and re-ingest
python ingest.py --reset
```

### Start the CLI

```bash
python -m cli.interactive
```

## 💡 Usage Examples

### Basic Search

```
You: How did I implement authentication in previous projects?
```

### Search Code

```
You: /code python async patterns
```

### Platform-Specific Search

```
You: /platform chatgpt explain RAG architecture
```

### View Statistics

```
You: /stats
```

## 📁 Project Structure

```
conductor_agent/
├── config/              # Configuration management
│   └── settings.py
├── data_processors/     # Platform-specific processors
│   ├── base_processor.py
│   ├── chatgpt_processor.py
│   ├── gemini_processor.py
│   ├── grok_processor.py
│   └── antigravity_processor.py
├── knowledge_base/      # Vector store and retrieval
│   ├── embeddings.py
│   ├── vector_store.py
│   └── retrieval.py
├── cli/                 # Command-line interface
│   └── interactive.py
├── utils/               # Utilities
│   └── logger.py
├── data/                # Data storage
│   ├── raw/            # Raw exports
│   ├── processed/      # Processed conversations
│   └── chroma_db/      # Vector database
├── ingest.py           # Data ingestion script
├── requirements.txt     # Python dependencies
└── .env.example        # Environment template
```

## 🔧 Configuration

All settings can be configured in `.env`:

```env
# LLM Configuration
CONDUCTOR_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Vector Database
CHROMA_PERSIST_DIR=./data/chroma_db

# Search Parameters
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K=5

# Data Paths
ANTIGRAVITY_BRAIN_DIR=C:/Users/jjc29/.gemini/antigravity/brain
```

## 🎨 CLI Commands

| Command | Description |
|---------|-------------|
| `<query>` | Ask any question |
| `/search <query>` | Search conversations |
| `/code <query>` | Search code snippets |
| `/platform <name> <query>` | Search specific platform |
| `/stats` | Show database statistics |
| `/clear` | Clear screen |
| `/help` | Show help |
| `/exit` | Exit application |

## 🔍 How It Works

1. **Data Processing**: Platform-specific processors parse and standardize conversations
2. **Embedding Generation**: Text is chunked and converted to semantic embeddings (OpenAI)
3. **Vector Storage**: Embeddings stored in ChromaDB for fast similarity search
4. **Retrieval**: Hybrid search with re-ranking by recency and relevance
5. **Context**: Retrieved conversations provide context for queries

## 🛠️ Troubleshooting

### "No relevant conversations found"

- Ensure you've run `ingest.py` to load your data
- Check that your export files are in the correct format
- Run `/stats` to verify database has content

### API Key Errors

- Verify `OPENAI_API_KEY` is set in `.env`
- Ensure the key has sufficient credits

### Import Errors

- Run `pip install -r requirements.txt`
- Ensure Python 3.9+ is installed

## 📊 Performance

- **Embedding Generation**: ~1000 tokens/second with caching
- **Search Speed**: <500ms for most queries
- **Storage**: ~1MB per 100 conversations
- **Cost**: ~$0.10 per 1000 conversations (embeddings)

## 🔐 Privacy

- **100% Local**: All data stays on your machine
- **No Telemetry**: ChromaDB telemetry disabled
- **API Calls**: Only for embeddings (text only, no PII)

## 🚧 Future Enhancements

- [x ] LangGraph conductor orchestration with specialized sub-agents
- [ x] Web UI interface
- [x ] Support for more platforms (Claude, Perplexity)
- [ x] Real-time conversation sync
- [x ] Export to NotebookLM format
- [x ] Conversation analytics and insights

## 📝 License

MIT License - Feel free to use and modify

## 🤝 Contributing

This is a personal project, but feel free to fork and adapt for your needs!

---

**Built with**: Python, ChromaDB, OpenAI, LangChain, Rich CLI
