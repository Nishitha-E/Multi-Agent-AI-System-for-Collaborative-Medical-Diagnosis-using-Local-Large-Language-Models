# Dockerfile for Aegis Medical Triage System
FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies: build tools, git, and ffmpeg for Whisper / PyDub audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY rag/ rag/

ENV PYTHONPATH=/workspace

RUN mkdir -p frontend/reports

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
