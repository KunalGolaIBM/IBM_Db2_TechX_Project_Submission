# Hotel Ops Copilot app image: Streamlit UI + agents + setup, talking to the db2 service.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONWARNINGS=ignore \
    FASTEMBED_CACHE_PATH=/opt/fastembed
WORKDIR /app
# libxml2 is needed by the Db2 CLI driver that ibm_db bundles
RUN apt-get update && apt-get install -y --no-install-recommends libxml2 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# bake the 384-d embedding model into the image so the first start is offline-friendly
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
COPY . .
EXPOSE 8501
CMD ["bash", "scripts/docker-entrypoint.sh"]
