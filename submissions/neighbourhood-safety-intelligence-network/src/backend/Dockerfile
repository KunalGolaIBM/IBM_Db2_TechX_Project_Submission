# Build context: src/  (the code is imported as the `backend` package)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HAYSTACK_TELEMETRY_ENABLED=False \
    HOME=/home/nsin

WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends curl libxml2 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# Run as an unprivileged user (with a home directory for library caches).
RUN useradd --system --uid 10001 --create-home --home-dir /home/nsin nsin \
    && chown -R nsin /srv
USER nsin

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
