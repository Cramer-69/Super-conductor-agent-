# 🚀 Deployment Guide – Conductor Voice Agent on Google Cloud Run

This guide covers deploying the Conductor Voice Agent to **Google Cloud Run** using
Docker, with proper secret handling via Secret Manager and CI/CD via Cloud Build.

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| [gcloud CLI](https://cloud.google.com/sdk/docs/install) | Interact with Google Cloud |
| [Docker](https://docs.docker.com/get-docker/) | Build images locally |
| A Google Cloud project with billing enabled | Hosting |

```bash
# Authenticate and set your project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

---

## 1 – Artifact Registry Setup

Cloud Run pulls images from Artifact Registry (the modern replacement for Container Registry).

```bash
# Enable the Artifact Registry API (one-time)
gcloud services enable artifactregistry.googleapis.com

# Create a Docker repository in your chosen region
gcloud artifacts repositories create conductor-agent \
  --repository-format=docker \
  --location=us-central1 \
  --description="Conductor Voice Agent images"

# Allow the gcloud Docker credential helper to push to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## 2 – Store Secrets in Secret Manager

Never bake API keys into your image or pass them as plain env vars in Cloud Run.

```bash
# Enable the Secret Manager API (one-time)
gcloud services enable secretmanager.googleapis.com

# Create the secret (interactive – paste your key when prompted)
echo -n "sk-YOUR_OPENAI_KEY" | \
  gcloud secrets create OPENAI_API_KEY \
    --data-file=- \
    --replication-policy=automatic

# Add a new version later:
# echo -n "sk-NEW_KEY" | gcloud secrets versions add OPENAI_API_KEY --data-file=-
```

---

## 3 – IAM Roles

### Cloud Run service account

Cloud Run uses a service account to access other GCP resources.  
Grant it permission to read the secret you created:

```bash
# Identify the Cloud Run service account (default is the Compute default SA)
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Allow it to read secret values
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/secretmanager.secretAccessor"
```

### Cloud Build service account

Cloud Build needs to push images to Artifact Registry and deploy to Cloud Run:

```bash
BUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/iam.serviceAccountUser"
```

### Developer Connect (optional – only for GitHub-connected triggers)

If you connect Cloud Build to GitHub via **Developer Connect**, you must grant the
Cloud Build service account the token-accessor role so it can clone your repository:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$BUILD_SA" \
  --role="roles/developerconnect.readTokenAccessor"
```

---

## 4 – Deploy from Local Machine

```bash
PROJECT_ID=YOUR_PROJECT_ID
REGION=us-central1
IMAGE=us-central1-docker.pkg.dev/$PROJECT_ID/conductor-agent/conductor-agent

# Build and push
docker build -t $IMAGE .
docker push $IMAGE

# Deploy to Cloud Run (PORT is injected automatically; secret is mounted as env var)
gcloud run deploy conductor-agent \
  --image=$IMAGE \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" \
  --set-env-vars="LOG_LEVEL=INFO"
```

Cloud Run injects the `PORT` environment variable automatically; the Dockerfile and
Gunicorn start command already honour it (default **8080**).

---

## 5 – Deploy via Cloud Build (CI/CD)

The repository includes a `cloudbuild.yaml` file that builds the Docker image, pushes
it to Artifact Registry, and deploys the new revision to Cloud Run.

```bash
# Enable Cloud Build and Cloud Run APIs (one-time)
gcloud services enable cloudbuild.googleapis.com run.googleapis.com

# Trigger a manual build (substitute your values)
gcloud builds submit . \
  --config=cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_SERVICE=conductor-agent
```

To run builds automatically on every push to `main`, create a Cloud Build trigger in
the console or via:

```bash
gcloud builds triggers create github \
  --repo-name=conductor-agent \
  --repo-owner=YOUR_GITHUB_USER \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --substitutions='_REGION=us-central1,_SERVICE=conductor-agent'
```

---

## 6 – Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | **Yes** | OpenAI API key (use Secret Manager on Cloud Run) |
| `PORT` | No | HTTP port (Cloud Run injects this; default **8080**) |
| `CONDUCTOR_MODEL` | No | LLM model name (default `gpt-4o-mini`) |
| `LOG_LEVEL` | No | Logging verbosity (default `INFO`) |
| `CHROMA_PERSIST_DIR` | No | ChromaDB path (not used in cloud/minimal mode) |

See `.env.example` for a full list of configurable variables.

---

## 7 – Local Development with Docker

```bash
# Build
docker build -t conductor-agent .

# Run (pass your key as an env var)
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=sk-your-key \
  conductor-agent

# Open in browser
open http://localhost:8080
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Missing required environment variable(s): OPENAI_API_KEY` | Set the secret in Secret Manager and attach it with `--set-secrets` |
| `permission denied` on secret access | Grant `roles/secretmanager.secretAccessor` to the Cloud Run SA |
| `403` on Cloud Build GitHub trigger | Grant `roles/developerconnect.readTokenAccessor` to the Cloud Build SA |
| Container exits immediately | Check Cloud Run logs: `gcloud run services logs read conductor-agent` |

