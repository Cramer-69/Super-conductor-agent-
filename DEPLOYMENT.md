# 🚀 Deployment Guide – Conductor Voice Agent

> **Platform change:** This project has moved from Render.com to **Google Cloud Run**.  
> The `render.yaml` file is kept for reference only and is **deprecated**.

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker | <https://docs.docker.com/get-docker/> |
| Google Cloud CLI (`gcloud`) | <https://cloud.google.com/sdk/docs/install> |
| A GCP project with billing enabled | <https://console.cloud.google.com/> |

```bash
# Authenticate and set your project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID   # replace with your actual project ID

# Enable required APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
```

---

## 1 – Local Docker Test

Verify the image builds and runs before deploying to the cloud.

```bash
# Build
docker build -t conductor-agent .

# Run locally (replace with your real key)
docker run --rm \
  -e OPENAI_API_KEY=sk-... \
  -p 8080:8080 \
  conductor-agent

# Smoke-test
curl http://localhost:8080/health
```

Expected response:
```json
{"status":"healthy","service":"conductor-voice-agent","version":"1.0.0"}
```

---

## 2 – Store the API Key in Secret Manager (recommended)

Never pass secrets as plain environment variables in production.

```bash
# Create the secret (paste your key when prompted)
echo -n "sk-YOUR_REAL_KEY" | \
  gcloud secrets create OPENAI_API_KEY \
    --data-file=- \
    --replication-policy=automatic

# Grant Cloud Run's service account access
PROJECT_ID=$(gcloud config get-value project)   # or set: PROJECT_ID=your-project-id
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 3 – Build & Push the Container Image

```bash
# Create an Artifact Registry repository (one-time)
gcloud artifacts repositories create conductor-agent \
  --repository-format=docker \
  --location=us-central1

# Build and push
PROJECT_ID=$(gcloud config get-value project)   # or set: PROJECT_ID=your-project-id
IMAGE=us-central1-docker.pkg.dev/$PROJECT_ID/conductor-agent/conductor-agent:latest

gcloud builds submit --tag "$IMAGE"
```

---

## 4 – Deploy to Cloud Run

### Option A – With Secret Manager (recommended)

```bash
gcloud run deploy conductor-agent \
  --image "$IMAGE" \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest" \
  --set-env-vars "LOG_LEVEL=INFO,CHROMA_PERSIST_DIR=/app/data/chroma_db"
```

### Option B – Plain environment variable (dev/testing only)

```bash
gcloud run deploy conductor-agent \
  --image "$IMAGE" \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "OPENAI_API_KEY=sk-...,LOG_LEVEL=INFO"
```

After deployment you will receive a service URL such as  
`https://conductor-agent-xxxx-uc.a.run.app`

---

## 5 – Verify the Deployment

```bash
curl https://conductor-agent-xxxx-uc.a.run.app/health
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ (or one of the below) | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | optional | — | Anthropic / Claude API key |
| `GOOGLE_API_KEY` | optional | — | Google / Gemini API key |
| `PORT` | no | `8080` | Port the server listens on (Cloud Run sets this automatically) |
| `CONDUCTOR_MODEL` | no | `gpt-4o-mini` | LLM model name |
| `CHROMA_PERSIST_DIR` | no | `./data/chroma_db` | ChromaDB storage path |
| `LOG_LEVEL` | no | `INFO` | Logging verbosity |

> **Startup check:** The server validates that at least one API key is present on  
> startup and exits immediately with a descriptive error if none is found.

---

## ⚠️ Security Notes

- **Never commit API keys** to git.  Copy `.env.example` → `.env` for local use;  
  `.env` is listed in `.gitignore` and will not be committed.
- If an API key was accidentally committed or pasted in public, **rotate it immediately**:  
  <https://platform.openai.com/api-keys>
- Use **Secret Manager** (Option A above) for all production deployments.

---

## 🔧 Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ERROR: No LLM API key found` at startup | Set `OPENAI_API_KEY` (or another supported key) |
| `403 PERMISSION_DENIED` from Secret Manager | Run the `add-iam-policy-binding` command in Step 2 |
| Container keeps restarting | Check Cloud Run logs: `gcloud run services logs read conductor-agent` |
| Port mismatch | Ensure `--port 8080` matches `ENV PORT=8080` in the Dockerfile |

