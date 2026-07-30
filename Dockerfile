# Build the React PWA separately so the runtime image contains only Python and
# the static production assets served by FastAPI.
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SCREENER_ENVIRONMENT=production \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py main.py ./
COPY screener/ ./screener/
COPY knowledge/ ./knowledge/
COPY knowledge_graph/ ./knowledge_graph/
COPY web/ ./web/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
RUN mkdir -p data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]