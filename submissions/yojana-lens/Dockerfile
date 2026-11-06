# YojanaLens application image.
# Python 3.11 is pinned deliberately: the ibm_db wheel set is reliable there.

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates libaio1 libstdc++6 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Bake the embedding model into the image so runtime inference is fully offline.
RUN python -c "from fastembed import TextEmbedding; \
TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')"

COPY . .

EXPOSE 8000

# init is idempotent; seed only when the corpus table is empty.
CMD ["sh", "-c", "python -m src.cli init && python -m src.cli seed --if-empty && exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000"]
