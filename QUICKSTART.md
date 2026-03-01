# Quick Start Guide

## 🚀 3-Minute Setup

### 1. Configure Your API Key

```bash
cp .env.example .env   # Linux/macOS
# or: copy .env.example .env  (Windows)
```

Open `.env` in your editor and add your API key:

```
OPENAI_API_KEY=sk-your-actual-key-here
```

Any of `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`, or `ANTHROPIC_API_KEY` will work.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Ingest Your Conversations

```bash
python ingest.py
```

Wait for processing... ☕ (first run takes ~5-10 minutes)

### 4. Start Chatting!

**CLI:**

```bash
python -m cli.interactive
```

**API server:**

```bash
uvicorn api.server:app --reload
# visit http://localhost:8000
```

## 📝 Example Commands

```
You: What projects have I worked on?
You: /code async patterns
You: /platform antigravity conductor agent
You: /stats
You: /help
You: /exit
```

## 🎯 Add More Platforms

### Export ChatGPT
1. Go to chat.openai.com → Settings → Data Controls
2. Click "Export Data" and wait for email
3. Download and extract `conversations.json`
4. Run: `python ingest.py --chatgpt "path/to/conversations.json"`

### Export Gemini
1. Visit [Google Takeout](https://takeout.google.com)
2. Select "Gemini Apps Activity"
3. Download and extract
4. Run: `python ingest.py --gemini "path/to/gemini_export"`

### Export Grok
1. Export from Grok settings (ZIP format)
2. Run: `python ingest.py --grok "path/to/grok_export.zip"`

### Antigravity
Set `ANTIGRAVITY_BRAIN_DIR` in your `.env` to the brain folder path, then run `python ingest.py`.

## 🔧 Troubleshooting

**No results found?**
- Run `/stats` to check if database has data
- Make sure you ran `python ingest.py` first

**API errors?**
- Check your `.env` file has a valid API key
- OpenAI keys start with `sk-`

**Installation issues?**
- Ensure Python 3.9+ is installed
- Run `pip install -r requirements.txt` again

## 📖 Full Documentation

See [README.md](README.md) for complete documentation including Render deployment.

## ✨ You're All Set!

Your conductor agent is ready to supercharge your AI workflow! 🎉

