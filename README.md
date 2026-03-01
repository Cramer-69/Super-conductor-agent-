# Conductor Super Agent

A local-first AI system that aggregates conversations from **Grok**, **ChatGPT**, **Gemini**, and **Antigravity** into a unified knowledge base with persistent memory across all your AI interactions.

## 🎯 Features

- **Multi-Platform Aggregation**: Combine conversations from all major AI platforms
- **Semantic Search**: RAG-based retrieval using ChromaDB vector database
- **Persistent Memory**: Never lose context across conversations
- **Code Snippet Extraction**: Automatically extracts and indexes code from all conversations
- **Privacy First**: Runs 100% locally on your machine
- **Rich CLI Interface**: Beautiful terminal interface with search and filtering

## 🚀 Quick Start (Windows)

**Double-click `Start_Super_Agent.bat` on your Desktop.**

This will:

1. Auto-configure the environment
2. Install any missing dependencies (self-healing)
3. Launch the Multi-AI Super Agent interface

---

## 🤖 Supported Providers

- **Google Gemini** (Primary, Auto-configured)
- **Grok / xAI** (Added via Desktop key)
- **Perplexity** (Search enabled)
- **OpenAI** (Fallback)

## 🔐 API Key Setup (Important — Read First)

The app requires `OPENAI_API_KEY` at startup. **Never commit your key to Git.**

`.env` is listed in `.gitignore` so it will not be accidentally committed.
Use `.env.example` as the template — it contains only placeholder values and is safe to commit.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd conductor_agent
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and add your API keys:

```bash
# Linux / macOS
cp .env.example .env

# Windows
copy .env.example .env
```

Edit `.env` and replace the placeholder with your real key:

```
OPENAI_API_KEY=sk-your-key-here
```

If the key is missing or still set to the placeholder value, the app will refuse to start
with a clear error message pointing to these instructions.

### 3. Export Your Conversations

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

- Conversations are automatically available at:

  ```
  C:\Users\<username>\.gemini\antigravity\brain
  ```

### 4. Ingest Your Data

Run the ingestion script to process and index your conversations:

```bash
# Ingest all platforms
python ingest.py --chatgpt "path/to/conversations.json" --gemini "path/to/gemini_export" --grok "path/to/grok_export.zip" --antigravity "C:/Users/jjc29/.gemini/antigravity/brain"

# Or just Antigravity (default)
python ingest.py

# Reset database and re-ingest
python ingest.py --reset --antigravity "C:/Users/jjc29/.gemini/antigravity/brain"
```

### 5. Start the CLI

```bash
python -m cli.interactive
```

### 6. Start the API / Web Server (local)

```bash
uvicorn api.server:app --host 0.0.0.0 --port 8000
# or
python api/server.py
```

---

## 🐳 Running with Docker

Build the image once:

```bash
docker build -t conductor-agent .
```

Run — pass the key at runtime, **not** as a build argument:

```bash
# Option A: inline env var
docker run -e OPENAI_API_KEY=sk-your-key-here -p 8000:8000 conductor-agent

# Option B: use your local .env file (never committed to Git)
docker run --env-file .env -p 8000:8000 conductor-agent
```

---

## ☁️ Cloud Run Deployment (recommended for production)

Use **Google Cloud Secret Manager** so your key is never stored in plain text anywhere.

### 1. Store the secret

```bash
# Create the secret (one-time)
echo -n "sk-your-key-here" | \
  gcloud secrets create openai-api-key \
    --data-file=- \
    --replication-policy=automatic
```

### 2. Build and push the container

```bash
PROJECT_ID=$(gcloud config get-value project)

docker build -t gcr.io/$PROJECT_ID/conductor-agent .
docker push gcr.io/$PROJECT_ID/conductor-agent
```

### 3. Deploy to Cloud Run (mounts the secret as an env var)

```bash
gcloud run deploy conductor-agent \
  --image gcr.io/$PROJECT_ID/conductor-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest
```

Cloud Run injects the secret value into the `OPENAI_API_KEY` environment variable
automatically — no plain-text key ever touches a config file or the container image.

### 4. Rotate the key (when needed)

```bash
# Add a new version
echo -n "sk-new-key-here" | \
  gcloud secrets versions add openai-api-key --data-file=-

# Re-deploy to pick up the latest version
gcloud run deploy conductor-agent \
  --image gcr.io/$PROJECT_ID/conductor-agent \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest
```

---

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

- The app prints a clear error at startup if `OPENAI_API_KEY` is missing — follow its instructions.
- For **local** usage: ensure `.env` exists and contains your real key (not the placeholder).
- For **Docker**: pass `-e OPENAI_API_KEY=sk-...` or `--env-file .env` to `docker run`.
- For **Cloud Run**: use `--set-secrets OPENAI_API_KEY=openai-api-key:latest` (see *Cloud Run Deployment* above).
- Ensure the key has sufficient credits.

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
