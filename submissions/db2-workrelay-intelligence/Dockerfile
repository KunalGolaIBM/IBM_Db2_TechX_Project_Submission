FROM python:3.10-slim

WORKDIR /app

# Install system dependencies needed for ibm_db and C compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["python", "-m", "app.main"]
