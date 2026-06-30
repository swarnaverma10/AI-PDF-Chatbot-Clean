# ================================================================= #
# AI PDF Chatbot - Repository Root Hugging Face Spaces Dockerfile
# ================================================================= #

# Use a lightweight python base image
FROM python:3.11-slim as builder

# Set env vars to prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if any are needed (e.g., build-essential for compiling C deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements from the backend folder to leverage Docker cache
COPY backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/home/user/.local/bin:$PATH

# Create a non-root user "user" with UID 1000 (required for Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

# Copy installed python dependencies from builder stage
COPY --from=builder --chown=user:user /root/.local /home/user/.local

# Copy application source code and knowledge base PDF from backend directory
COPY --chown=user:user backend/app/ ./app/
COPY --chown=user:user backend/knowledge_base/ ./knowledge_base/

# Expose the default port for Hugging Face Spaces (7860)
EXPOSE 7860

# Start FastAPI application using Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
