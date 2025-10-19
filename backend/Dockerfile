# OfferI Backend Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for WeasyPrint (PDF generation)
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libcairo2-dev \
    libglib2.0-0 \
    libglib2.0-dev \
    libharfbuzz-dev \
    libpangocairo-1.0-0 \
    shared-mime-info \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN curl -fsSL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | bash

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code INCLUDING database.py
COPY database.py .
COPY api/ ./api/
COPY workers/ ./workers/
COPY utils/ ./utils/
COPY templates/ ./templates/

# Create necessary directories
RUN mkdir -p /app/outputs /app/logs /app/mcp

# Expose FastAPI port
EXPOSE 8000

# Set PYTHONPATH for absolute imports
ENV PYTHONPATH=/app

# Default command (run FastAPI server)
CMD ["python", "-m", "api.server"]
