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

# Expose default port (override at runtime with -e PORT=...)
EXPOSE 8080

# Run with Gunicorn – respect $PORT so Cloud Run / Render can inject it
# Exec form via sh -c keeps signal forwarding intact
CMD ["sh", "-c", "exec gunicorn api.server:app --bind \"0.0.0.0:${PORT:-8080}\" --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120"]
