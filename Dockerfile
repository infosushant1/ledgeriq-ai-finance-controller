# Production image: build React, then serve it from FastAPI.
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY scripts ./scripts
COPY .env.example ./.env.example
COPY data ./data
COPY --from=frontend /app/frontend/dist ./frontend/dist
RUN mkdir -p /app/data/generated
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
