# 🚀 Deployment Guide - Conductor Voice Agent

> **Note:** Render.com is no longer the recommended deployment platform.  
> This guide covers **Google Cloud Run** (Docker-based, serverless) as the primary target.  
> The legacy `render.yaml` file is kept for reference only and is **deprecated**.

---

## ⚠️ API Key Security

**Never commit API keys to source control.**  
If a key was accidentally shared or committed, rotate it immediately:

1. Go to <https://platform.openai.com/api-keys>
2. Delete the exposed key and create a new one
3. Update the new key in your secret store (see below)
4. Search your git history for the old key and purge it if necessary

---

## 🐳 Local Development with Docker

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
- A valid `OPENAI_API_KEY` (or other supported provider key)

### 1. Create your `.env` file

```bash
cp .env.example .env
# Edit .env and set your API key – do NOT commit this file
```

`.env` example:
```env
OPENAI_API_KEY=sk-...           # required
CONDUCTOR_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
```

### 2. Build and run the container

```bash
docker build -t conductor-agent .
docker run --rm -p 8080:8080 --env-file .env conductor-agent
```

The app will be available at <http://localhost:8080>.

> The container respects the `PORT` environment variable (defaults to `8080`).

---

## ☁️ Google Cloud Run Deployment

### Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- A Google Cloud project with billing enabled
- APIs enabled: **Cloud Run**, **Artifact Registry**, **Secret Manager**

```bash
gcloud services enable run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com
```

### 1. Store your API key in Secret Manager

```bash
# Create the secret (run once)
echo -n "sk-your-real-key" | gcloud secrets create OPENAI_API_KEY \
    --data-file=- \
    --replication-policy=automatic

# Grant the Cloud Run service account access
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

To rotate a key later:
```bash
echo -n "sk-new-key" | gcloud secrets versions add OPENAI_API_KEY --data-file=-
```

### 2. Create an Artifact Registry repository

```bash
REGION=us-central1   # change to your preferred region
gcloud artifacts repositories create conductor-agent \
    --repository-format=docker \
    --location=$REGION
```

### 3. Build and push the container image

```bash
PROJECT_ID=$(gcloud config get-value project)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/conductor-agent/conductor-agent:latest"

gcloud builds submit --tag "$IMAGE"
```

### 4. Deploy to Cloud Run

```bash
gcloud run deploy conductor-agent \
    --image "$IMAGE" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest" \
    --set-env-vars "LOG_LEVEL=INFO,CONDUCTOR_MODEL=gpt-4o-mini"
```

Cloud Run automatically injects `PORT` and the app binds to it.

### 5. View logs

```bash
gcloud run services logs read conductor-agent --region $REGION
```

---

## 🔑 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes (or another provider key) | OpenAI API key |
| `ANTHROPIC_API_KEY` | No | Anthropic Claude key |
| `GOOGLE_API_KEY` | No | Google Gemini key |
| `CONDUCTOR_MODEL` | No (default: `gpt-4o-mini`) | LLM model to use |
| `EMBEDDING_MODEL` | No (default: `text-embedding-3-small`) | Embedding model |
| `LOG_LEVEL` | No (default: `INFO`) | Logging verbosity |
| `PORT` | No (default: `8080`) | Port the server listens on |
| `CHROMA_PERSIST_DIR` | No | ChromaDB data directory (local/full mode only) |

---

## 🔧 Troubleshooting

### "CONFIGURATION ERROR: No LLM API key found"
- Ensure at least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY` is set.
- In Cloud Run, verify the secret is attached via `--set-secrets`.

### "CONFIGURATION ERROR: OPENAI_API_KEY appears to be a placeholder"
- You have a template value in your env. Set a real API key.

### Container does not start on Cloud Run
- Cloud Run requires the app to bind on `0.0.0.0:$PORT`.
  The Dockerfile already handles this (`${PORT:-8080}`).
- Check logs: `gcloud run services logs read conductor-agent --region $REGION`

### "API error" in the web UI
- Confirm the secret version is active: `gcloud secrets versions list OPENAI_API_KEY`
- Ensure the service account has `secretmanager.secretAccessor` role.

---

## 💰 Cost Estimates (Google Cloud Run)

- **Compute**: ~$0 for low traffic (generous free tier: 2M requests/month, 360k CPU-seconds)
- **Artifact Registry**: ~$0.10/GB/month for the container image
- **Secret Manager**: ~$0.06/month per secret
- **OpenAI API**: ~$0.01–$0.03 per voice conversation

---

## 🎊 You're Done!

Your conductor agent is deployed on Google Cloud Run:
- ✅ Secure API keys via Secret Manager (never in source code)
- ✅ Auto-scaling, serverless – no idle costs
- ✅ Accessible from any device with the Cloud Run URL
- ✅ Key rotation without redeployment

