FROM python:3.11-slim

# Install system dependencies including ffmpeg for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# System deps (keep minimal; add build tools only if needed)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p temp_audio logs data/chroma_db

# Expose port (Cloud platforms commonly use 8080)
EXPOSE 8080

# Run with Gunicorn (bind to platform-provided PORT; default to 8080 for local runs)
CMD ["sh", "-c", "gunicorn api.server:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 120"]
