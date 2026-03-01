# Conductor Voice Agent
# Production deployment with Gunicorn
#
# ⚠️  SECRETS: Do NOT bake OPENAI_API_KEY into the image.
#     • Local Docker  : docker run -e OPENAI_API_KEY=sk-... ...
#                       OR  docker run --env-file .env ...
#     • Cloud Run     : gcloud run deploy ... \
#                         --set-secrets OPENAI_API_KEY=openai-api-key:latest
#     See README.md for full instructions.

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p temp_audio logs data/chroma_db

# Expose port
EXPOSE 8000

# Run with Gunicorn
CMD ["gunicorn", "api.server:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120"]
