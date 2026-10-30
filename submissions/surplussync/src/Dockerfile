FROM node:20-alpine AS frontend-build
WORKDIR /workspace
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend ./frontend
ENV VITE_API_BASE_URL=/api
RUN npm run build --prefix frontend

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /var/data /app/backend
COPY backend/__init__.py backend/auth.py backend/create_admin.py backend/database.py backend/feasibility.py backend/main.py backend/models.py backend/seed_demo_accounts.py backend/seed_demo_workflows.py backend/seed_presentation_demo.py ./backend/
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist
ENV SURPLUSSYNC_DB_PATH=/var/data/surplussync.db \
    SURPLUSSYNC_UPLOAD_DIR=/var/data/private_uploads \
    SURPLUSSYNC_COOKIE_SECURE=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
