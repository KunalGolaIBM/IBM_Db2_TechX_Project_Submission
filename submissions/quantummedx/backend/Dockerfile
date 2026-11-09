FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpam0g libxml2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV STORAGE_DIR=/app/backend/storage
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
