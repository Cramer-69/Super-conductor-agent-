# Build context is the REPO ROOT (this service imports as `semantic_wall.*`,
# not bare module names, to avoid colliding with the sibling app's own
# top-level `config`/`api` packages). `gcloud run deploy --source` only
# looks for a Dockerfile at the root of the given source dir, so it can't
# point at this file directly with repo-root context — build explicitly
# instead (from the repo root):
#   docker build -f semantic_wall/Dockerfile -t semantic-wall .
#   docker push <your-registry>/semantic-wall
#   gcloud run deploy semantic-wall --image <your-registry>/semantic-wall
# See semantic_wall/README.md for the full deploy walkthrough.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY semantic_wall/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY semantic_wall/ ./semantic_wall/

EXPOSE 8080

CMD ["sh", "-c", "gunicorn semantic_wall.api.main:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --worker-class uvicorn.workers.UvicornWorker --timeout 120"]
