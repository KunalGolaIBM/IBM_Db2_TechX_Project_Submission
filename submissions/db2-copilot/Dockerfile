FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache the fastembed model into the Docker image
RUN python -c "from fastembed import TextEmbedding; list(TextEmbedding().embed(['init']))"

COPY requirements-langchain.txt .
RUN pip install --no-cache-dir -r requirements-langchain.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

