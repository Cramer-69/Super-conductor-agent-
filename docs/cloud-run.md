# Google Cloud Run Deployment Guide

This guide covers deploying Conductor Agent to **Google Cloud Run** using Cloud Build,
including all required IAM permissions and Developer Connect setup.

---

## Prerequisites

### 1. Install and authenticate the Google Cloud CLI

```bash
# Install gcloud (if not already installed)
# https://cloud.google.com/sdk/docs/install

# Authenticate with your Google account
gcloud auth login

# Set application-default credentials (used by SDKs)
gcloud auth application-default login
```

### 2. Set your active project

```bash
export PROJECT_ID="your-project-id"          # e.g. my-project-123
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" \
  --format="value(projectNumber)")

gcloud config set project "$PROJECT_ID"
```

> **Tip:** Run `gcloud projects list` to find your project ID.

### 3. Enable required APIs

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  developerconnect.googleapis.com \
  --project="$PROJECT_ID"
```

---

## IAM Permissions for Cloud Build

### Cloud Build Service Account

Cloud Build runs as the service account:

```
PROJECT_NUMBER@cloudbuild.gserviceaccount.com
```

Retrieve your project number and construct the service account address:

```bash
export CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "Cloud Build SA: $CLOUD_BUILD_SA"
```

### Required roles

Grant the following roles so Cloud Build can build images, push to Artifact Registry,
and deploy to Cloud Run:

```bash
# Push images to Artifact Registry
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/artifactregistry.writer"

# Deploy to Cloud Run
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/run.admin"

# Allow Cloud Build to act as the Cloud Run runtime service account
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/iam.serviceAccountUser"

# Read secrets from Secret Manager (if using Secret Manager for API keys)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Developer Connect: Required Permissions

[Developer Connect](https://cloud.google.com/developer-connect/docs/overview) lets
Cloud Build access source repositories (GitHub, GitLab, etc.) through managed
connections.  The following role is required when Cloud Build triggers read tokens
from a Developer Connect connection.

### `roles/developerconnect.readTokenAccessor`

This role allows the bearer to exchange a Developer Connect connection token for
a short-lived read credential used to clone the source repository during a build.

**When you need this binding:**

- You have a Cloud Build trigger connected to a GitHub/GitLab repository via
  Developer Connect (not the legacy GitHub App).
- Build logs show: `PERMISSION_DENIED: caller does not have permission
  developerconnect.connections.fetchReadToken`.

**Grant the role to the Cloud Build service account:**

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$CLOUD_BUILD_SA" \
  --role="roles/developerconnect.readTokenAccessor"
```

### Set up a Developer Connect connection (first-time only)

```bash
# List existing connections
gcloud developer-connect connections list --project="$PROJECT_ID" --location=us-central1

# Create a new GitHub connection (follow the OAuth flow printed in the output)
gcloud developer-connect connections create github-conn \
  --project="$PROJECT_ID" \
  --location=us-central1 \
  --github-config-app=developer-connect
```

After creating the connection, link your repository:

```bash
gcloud developer-connect git-repository-links create conductor-agent \
  --project="$PROJECT_ID" \
  --location=us-central1 \
  --connection=github-conn \
  --clone-uri="https://github.com/YOUR_ORG/conductor-agent.git"
```

---

## Build and Deploy

### Create an Artifact Registry repository

```bash
export REGION="us-central1"
export AR_REPO="conductor-agent"

gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID"
```

### Build the container image with Cloud Build

```bash
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/conductor-agent:latest"

gcloud builds submit . \
  --tag="$IMAGE" \
  --project="$PROJECT_ID"
```

### Deploy to Cloud Run

```bash
gcloud run deploy conductor-agent \
  --image="$IMAGE" \
  --platform=managed \
  --region="$REGION" \
  --allow-unauthenticated \
  --set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest" \
  --project="$PROJECT_ID"
```

> **Security:** Use `--set-secrets` (Secret Manager) rather than `--set-env-vars` for
> sensitive values like API keys. Never pass secret values on the command line or
> commit them to source control.

---

## Troubleshooting

### `PERMISSION_DENIED: fetchReadToken`

```
ERROR: (gcloud.builds.submit) PERMISSION_DENIED: caller does not have permission
developerconnect.connections.fetchReadToken on resource ...
```

**Fix:** Grant `roles/developerconnect.readTokenAccessor` to the Cloud Build SA:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/developerconnect.readTokenAccessor"
```

---

### `PERMISSION_DENIED` pushing to Artifact Registry

```
denied: Permission "artifactregistry.repositories.uploadArtifacts" denied
```

**Fix:** Grant `roles/artifactregistry.writer` to the Cloud Build SA (see
[Required roles](#required-roles) above).

---

### `PERMISSION_DENIED` deploying to Cloud Run

```
ERROR: (gcloud.run.deploy) PERMISSION_DENIED: Permission 'run.services.create' denied
```

**Fix:** Grant `roles/run.admin` and `roles/iam.serviceAccountUser` to the Cloud Build
SA (see [Required roles](#required-roles) above).

---

### `The user-provided key is invalid` / missing API key at runtime

The container starts but returns 500 errors because an API key environment variable is
not set.

**Fix:** Store the key in Secret Manager and reference it in your Cloud Run service:

```bash
# Create the secret (run once)
echo -n "YOUR_KEY_VALUE" | gcloud secrets create OPENAI_API_KEY \
  --data-file=- \
  --project="$PROJECT_ID"

# Grant the Cloud Run runtime SA access to the secret
export RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
  --member="serviceAccount:$RUNTIME_SA" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID"
```

Then redeploy with `--set-secrets="OPENAI_API_KEY=OPENAI_API_KEY:latest"`.

---

### Cloud Run service is not accessible

- Ensure `--allow-unauthenticated` was passed (or grant
  `roles/run.invoker` to `allUsers` for public access).
- Check the Cloud Run logs:
  ```bash
  gcloud run services logs read conductor-agent \
    --region="$REGION" \
    --project="$PROJECT_ID"
  ```

---

## Security Best Practices

| Do | Don't |
|----|-------|
| Store API keys in Secret Manager | Hardcode keys in Dockerfile or source |
| Use `--set-secrets` in `gcloud run deploy` | Use `--set-env-vars` for sensitive values |
| Keep `.env` in `.gitignore` | Commit `.env` files |
| Rotate keys immediately if accidentally exposed | Leave exposed keys active |
| Use least-privilege IAM roles | Grant project `Owner` to service accounts |

---

## Further Reading

- [Cloud Build service account documentation](https://cloud.google.com/build/docs/cloud-build-service-account)
- [Developer Connect overview](https://cloud.google.com/developer-connect/docs/overview)
- [Cloud Run security best practices](https://cloud.google.com/run/docs/securing/security-overview)
- [Secret Manager quickstart](https://cloud.google.com/secret-manager/docs/quickstart)
