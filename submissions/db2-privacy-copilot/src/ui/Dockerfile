FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ libxml2 libaio1t64 \
    && rm -rf /var/lib/apt/lists/*

# The UI uses the same CPU-only classifier dependencies as the API image.
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
    --index-url https://download.pytorch.org/whl/cpu torch

WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
COPY eval ./eval
COPY sql ./sql
COPY ui ./ui
RUN pip install --no-cache-dir --retries 10 --timeout 120 ".[ui]" \
    && useradd --create-home appuser \
    && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8501
CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
