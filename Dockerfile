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

# Default port (Cloud Run injects PORT at runtime)
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run with Gunicorn (shell form to allow $PORT substitution)
CMD gunicorn api.server:app --bind "0.0.0.0:${PORT}" --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120
