# Conductor Voice Agent
# Production deployment with Gunicorn

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

# Expose default port (Cloud Run / other platforms override via PORT env var)
EXPOSE 8080

# Run with Gunicorn – respects PORT env var (default 8080 for Google Cloud Run)
CMD gunicorn api.server:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120
