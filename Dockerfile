FROM python:3.11-slim

# System deps needed by sentence-transformers, pymupdf, psycopg2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Render injects PORT env var; default to 8000 for local use
ENV PORT=8000

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
