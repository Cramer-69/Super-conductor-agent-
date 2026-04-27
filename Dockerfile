
CMD gunicorn api.server:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 120
