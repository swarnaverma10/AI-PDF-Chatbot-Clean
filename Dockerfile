# =================================================================
# AI PDF Chatbot - Hugging Face Spaces Dockerfile
# =================================================================

# ---------- Builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Runtime ----------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/user/.local/bin:$PATH

RUN useradd -m -u 1000 user

USER user

WORKDIR /home/user/app

COPY --from=builder --chown=user:user /root/.local /home/user/.local

# Copy backend source code
COPY --chown=user:user backend/app/ ./app/

# Create empty knowledge base directory
RUN mkdir -p /home/user/app/knowledge_base

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]