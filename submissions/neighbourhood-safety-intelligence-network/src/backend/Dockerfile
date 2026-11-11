# Build context: src/  (the code is imported as the `backend` package)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_CACHE_DIR=/srv/models

WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends curl libxml2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Bake the embedding model into the image so Db2 vector search works offline from the first start.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/srv/models')"

COPY backend/ backend/

# Run as an unprivileged user.
RUN useradd --system --uid 10001 nsin && mkdir -p /data && chown -R nsin /srv /data
USER nsin

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
