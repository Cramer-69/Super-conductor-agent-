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

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd conductor_agent
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and add your API keys:

```bash
copy .env.example .env
```

Edit `.env` and add your OpenAI API key:

```
OPENAI_API_KEY=sk-your-key-here
```

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

## ☁️ Deploy to Google Cloud Run

Follow these steps to host Conductor on **Google Cloud Run** with your OpenAI API key stored securely in **Secret Manager** (recommended over plain environment variables).

---

### Step 1 – Open Secret Manager and create a secret

1. Go to **[Secret Manager](https://console.cloud.google.com/security/secret-manager)** in the Google Cloud Console.
2. Click **"+ Create secret"** (top toolbar).
3. **Name**: `OPENAI_API_KEY`
4. **Secret value**: paste your `sk-…` key.
5. Click **"Create secret"**.

> To update the key later: open the secret → **"+ Add new version"** → paste the new value → **"Add new version"**.

---

### Step 2 – Deploy or update your Cloud Run service

1. Go to **[Cloud Run](https://console.cloud.google.com/run)** in the Google Cloud Console.
2. Click your service name (or **"Create service"** for a first deploy).
3. Click **"Edit & deploy new revision"** (top toolbar).

#### Attach the secret as an environment variable (recommended)

4. Select the **"Variables & Secrets"** tab.
5. Scroll to the **"Secrets"** section and click **"Reference a secret"**.
6. Fill in:
   - **Environment variable name**: `OPENAI_API_KEY`
   - **Secret**: select `OPENAI_API_KEY` from the dropdown
   - **Version**: `latest`
7. Click **"Done"**, then **"Deploy"**.

The container will receive the secret value as the `OPENAI_API_KEY` environment variable at runtime — the value is never stored in plain text in your Cloud Run configuration.

#### Alternative: plain environment variable (not recommended)

If you prefer not to use Secret Manager, you can add the key directly:

4. Select the **"Variables & Secrets"** tab.
5. In the **"Environment variables"** section click **"+ Add variable"**.
6. Set **Name** = `OPENAI_API_KEY` and **Value** = your raw key.
7. Click **"Deploy"**.

> ⚠️ Plain environment variables are visible to anyone with `roles/run.developer` or higher and are stored unencrypted in the revision configuration. Prefer Secret Manager for any key with billing exposure.

---

### Step 3 – Find your service URL

After the deployment finishes, the service URL is shown at the top of the service detail page:

1. Go to **[Cloud Run](https://console.cloud.google.com/run)**.
2. Click your service name.
3. The URL is displayed under the service name — e.g. `https://conductor-agent-<hash>-uc.a.run.app`.

You can also copy it from the **"Triggers"** tab on the same page.

---

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
